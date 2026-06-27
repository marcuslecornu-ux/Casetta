from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
import csv
import io
from datetime import datetime, date
from database import get_db, init_db, ROOMS, DRINK_CATEGORIES, EXPENSE_CATEGORIES, BOOKING_SOURCES

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "casetta-secret-2026-change-in-production")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access Casetta."


class User(UserMixin):
    def __init__(self, id, username, role, display_name):
        self.id = id
        self.username = username
        self.role = role
        self.display_name = display_name

    @property
    def is_admin(self):
        return self.role == "admin"


@login_manager.user_loader
def load_user(user_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    if row:
        return User(row["id"], row["username"], row["role"], row["display_name"])
    return None


def generate_uid(prefix=""):
    now = datetime.now()
    return f"{now.strftime('%Y%m%d-%H%M%S')}-{prefix}"


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if row and check_password_hash(row["password_hash"], password):
            user = User(row["id"], row["username"], row["role"], row["display_name"])
            login_user(user, remember=True)
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.", "danger")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@app.route("/")
@login_required
def dashboard():
    conn = get_db()
    today = date.today().isoformat()
    year = date.today().year

    sales_today = conn.execute(
        "SELECT COALESCE(SUM(total_sale),0) FROM drink_sales WHERE date=?", (today,)
    ).fetchone()[0]

    month_start = f"{year}-{date.today().month:02d}-01"
    sales_month = conn.execute(
        "SELECT COALESCE(SUM(total_sale),0) FROM drink_sales WHERE date >= ?", (month_start,)
    ).fetchone()[0]

    expenses_month = conn.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date >= ?", (month_start,)
    ).fetchone()[0]

    recent_sales = conn.execute(
        "SELECT * FROM drink_sales ORDER BY created_at DESC LIMIT 8"
    ).fetchall()

    recent_expenses = conn.execute(
        "SELECT * FROM expenses ORDER BY created_at DESC LIMIT 8"
    ).fetchall()

    upcoming_bookings = conn.execute(
        "SELECT * FROM bookings WHERE arrival >= ? ORDER BY arrival LIMIT 6", (today,)
    ).fetchall()

    low_stock = conn.execute(
        "SELECT * FROM stock_items WHERE current_stock <= 3 AND active=1 ORDER BY current_stock"
    ).fetchall()

    conn.close()
    return render_template("dashboard.html",
        sales_today=sales_today,
        sales_month=sales_month,
        expenses_month=expenses_month,
        recent_sales=recent_sales,
        recent_expenses=recent_expenses,
        upcoming_bookings=upcoming_bookings,
        low_stock=low_stock,
        today=today
    )


# ─── DRINK SALES ──────────────────────────────────────────────────────────────

@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    if request.method == "POST":
        conn = get_db()
        data = request.form

        item_id = data.get("item_id")
        item_row = conn.execute("SELECT * FROM stock_items WHERE id=?", (item_id,)).fetchone()
        item_name = item_row["name"] if item_row else data.get("item_name", "")
        category = item_row["category"] if item_row else data.get("category", "")

        unit_type = data.get("unit_type", "Bottle")
        is_hosted = 1 if data.get("is_hosted") else 0
        quantity = int(data.get("quantity", 1))
        discount_pct = float(data.get("discount_pct", 0))

        if item_row:
            unit_price = item_row["selling_price_glass"] if unit_type == "Glass" else item_row["selling_price_bottle"]
        else:
            unit_price = float(data.get("unit_price", 0))

        if is_hosted:
            total_sale = 0
            discount_pct = 100
        else:
            total_sale = unit_price * quantity * (1 - discount_pct / 100)

        uid = generate_uid("SALE")
        sale_date = data.get("date", date.today().isoformat())

        conn.execute("""
            INSERT INTO drink_sales
            (uid, date, room, item_id, item_name, category, quantity, unit_type,
             unit_price, discount_pct, is_hosted, total_sale, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (uid, sale_date, data.get("room"), item_id, item_name, category,
              quantity, unit_type, unit_price, discount_pct, is_hosted, total_sale,
              data.get("notes", "")))

        # Update stock
        conn.execute(
            "UPDATE stock_items SET current_stock = MAX(0, current_stock - ?) WHERE id=?",
            (quantity, item_id)
        )

        conn.commit()
        conn.close()
        flash(f"Sale recorded: {quantity}x {item_name} — €{total_sale:.2f}", "success")
        return redirect(url_for("sales"))

    conn = get_db()
    stock_items = conn.execute(
        "SELECT * FROM stock_items WHERE active=1 ORDER BY category, name"
    ).fetchall()
    recent = conn.execute(
        "SELECT * FROM drink_sales ORDER BY date DESC, created_at DESC"
    ).fetchall()
    conn.close()

    return render_template("sales.html",
        rooms=ROOMS,
        categories=DRINK_CATEGORIES,
        stock_items=stock_items,
        recent=recent,
        today=date.today().isoformat()
    )


@app.route("/api/items/<category>")
@login_required
def items_by_category(category):
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM stock_items WHERE category=? AND active=1 ORDER BY name",
        (category,)
    ).fetchall()
    conn.close()
    return jsonify([dict(i) for i in items])


@app.route("/stock/update_prices", methods=["POST"])
@login_required
def update_prices():
    conn = get_db()
    item_id = request.form.get("item_id")
    conn.execute("""
        UPDATE stock_items
        SET purchase_price=?, selling_price_bottle=?, selling_price_glass=?
        WHERE id=?
    """, (
        float(request.form.get("purchase_price", 0)),
        float(request.form.get("selling_price_bottle", 0)),
        float(request.form.get("selling_price_glass", 0)),
        item_id
    ))
    conn.commit()
    conn.close()
    flash(f"Prices updated for {item_id}.", "success")
    return redirect(url_for("stock") + "#tabInventory")


# ─── STOCK ────────────────────────────────────────────────────────────────────

@app.route("/stock", methods=["GET", "POST"])
@login_required
def stock():
    conn = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add_movement":
            item_id = request.form.get("item_id")
            item_row = conn.execute("SELECT * FROM stock_items WHERE id=?", (item_id,)).fetchone()
            qty = int(request.form.get("quantity", 0))
            mov_type = request.form.get("movement_type", "Purchase")
            unit_cost = float(request.form.get("unit_cost", 0))

            conn.execute("""
                INSERT INTO stock_movements (date, item_id, item_name, movement_type, quantity, unit_cost, total_cost, notes)
                VALUES (?,?,?,?,?,?,?,?)
            """, (request.form.get("date", date.today().isoformat()),
                  item_id, item_row["name"] if item_row else item_id,
                  mov_type, qty, unit_cost, qty * unit_cost,
                  request.form.get("notes", "")))

            # Positive = stock in, negative = adjustment down
            if mov_type in ("Purchase", "Adjustment +"):
                conn.execute("UPDATE stock_items SET current_stock = current_stock + ? WHERE id=?", (qty, item_id))
            else:
                conn.execute("UPDATE stock_items SET current_stock = MAX(0, current_stock - ?) WHERE id=?", (qty, item_id))

            conn.commit()
            flash("Stock movement recorded.", "success")

        elif action == "add_item":
            new_id = request.form.get("new_id", "").strip().upper()
            if new_id and not conn.execute("SELECT id FROM stock_items WHERE id=?", (new_id,)).fetchone():
                conn.execute("""
                    INSERT INTO stock_items (id, category, name, purchase_price, selling_price_bottle, selling_price_glass, current_stock)
                    VALUES (?,?,?,?,?,?,?)
                """, (new_id,
                      request.form.get("new_category"),
                      request.form.get("new_name"),
                      float(request.form.get("new_purchase_price", 0)),
                      float(request.form.get("new_selling_bottle", 0)),
                      float(request.form.get("new_selling_glass", 0)),
                      int(request.form.get("new_stock", 0))))
                conn.commit()
                flash(f"New item {new_id} added.", "success")
            else:
                flash("Item ID already exists or is blank.", "warning")

        return redirect(url_for("stock"))

    items = conn.execute(
        "SELECT * FROM stock_items WHERE active=1 ORDER BY category, name"
    ).fetchall()
    movements = conn.execute(
        "SELECT * FROM stock_movements ORDER BY created_at DESC LIMIT 30"
    ).fetchall()
    conn.close()

    return render_template("stock.html",
        items=items,
        movements=movements,
        categories=DRINK_CATEGORIES,
        today=date.today().isoformat()
    )


# ─── EXPENSES ─────────────────────────────────────────────────────────────────

@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    if request.method == "POST":
        conn = get_db()
        exp_date = request.form.get("date", date.today().isoformat())
        dt = datetime.strptime(exp_date, "%Y-%m-%d")

        uid = generate_uid("EXP")
        conn.execute("""
            INSERT INTO expenses (uid, date, category, sub_category, comments, amount, status, month, year)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (uid, exp_date,
              request.form.get("category"),
              request.form.get("sub_category", ""),
              request.form.get("comments", ""),
              float(request.form.get("amount", 0)),
              request.form.get("status", "Paid"),
              dt.strftime("%b"), dt.year))
        conn.commit()
        conn.close()
        flash("Expense recorded.", "success")
        return redirect(url_for("expenses"))

    conn = get_db()
    # Filter by year
    year_filter = request.args.get("year", str(date.today().year))
    recent = conn.execute(
        "SELECT * FROM expenses WHERE year=? ORDER BY date DESC",
        (year_filter,)
    ).fetchall()
    totals = conn.execute(
        "SELECT category, SUM(amount) as total FROM expenses WHERE year=? GROUP BY category ORDER BY total DESC",
        (year_filter,)
    ).fetchall()
    years = conn.execute(
        "SELECT DISTINCT year FROM expenses ORDER BY year DESC"
    ).fetchall()
    conn.close()

    return render_template("expenses.html",
        categories=EXPENSE_CATEGORIES,
        recent=recent,
        totals=totals,
        years=[r["year"] for r in years] or [date.today().year],
        year_filter=int(year_filter),
        today=date.today().isoformat()
    )


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────

@app.route("/bookings", methods=["GET", "POST"])
@login_required
def bookings():
    if request.method == "POST":
        conn = get_db()
        arrival = request.form.get("arrival")
        num_nights = int(request.form.get("num_nights", 1))

        # Calculate departure
        arr_dt = datetime.strptime(arrival, "%Y-%m-%d")
        from datetime import timedelta
        dep_dt = arr_dt + timedelta(days=num_nights)
        departure = dep_dt.date().isoformat()

        conn.execute("""
            INSERT INTO bookings
            (entry_date, guest_name, room, arrival, num_nights, departure,
             source, source_code, confirmed, rate_type, total_cost, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (date.today().isoformat(),
              request.form.get("guest_name"),
              request.form.get("room"),
              arrival, num_nights, departure,
              request.form.get("source"),
              request.form.get("source_code"),
              request.form.get("confirmed", "Yes"),
              request.form.get("rate_type", "RACK"),
              float(request.form.get("total_cost", 0)),
              request.form.get("notes", "")))
        conn.commit()
        conn.close()
        flash("Booking recorded.", "success")
        return redirect(url_for("bookings"))

    conn = get_db()
    year_filter = request.args.get("year", str(date.today().year))
    all_bookings = conn.execute(
        "SELECT * FROM bookings WHERE arrival LIKE ? ORDER BY arrival",
        (f"{year_filter}%",)
    ).fetchall()
    conn.close()

    return render_template("bookings.html",
        rooms=ROOMS,
        sources=BOOKING_SOURCES,
        all_bookings=all_bookings,
        year_filter=int(year_filter),
        today=date.today().isoformat()
    )


# ─── ADMIN ────────────────────────────────────────────────────────────────────

@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        flash("Admin access only.", "danger")
        return redirect(url_for("dashboard"))
    conn = get_db()
    stats = {
        "drink_sales":      conn.execute("SELECT COUNT(*) FROM drink_sales").fetchone()[0],
        "expenses":         conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0],
        "bookings":         conn.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
        "stock_items":      conn.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0],
        "stock_movements":  conn.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0],
        "total_sales_rev":  conn.execute("SELECT COALESCE(SUM(total_sale),0) FROM drink_sales WHERE is_hosted=0").fetchone()[0],
        "total_expenses":   conn.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0],
        "total_bookings_rev": conn.execute("SELECT COALESCE(SUM(total_cost),0) FROM bookings").fetchone()[0],
    }
    users = conn.execute("SELECT id, username, display_name, role FROM users").fetchall()
    conn.close()
    return render_template("admin.html", stats=stats, users=users)


@app.route("/admin/export/<table>")
@login_required
def export_csv(table):
    if not current_user.is_admin:
        return "Forbidden", 403
    allowed = {"drink_sales", "expenses", "bookings", "stock_items", "stock_movements"}
    if table not in allowed:
        return "Not found", 404
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    conn.close()
    if not rows:
        flash(f"No data in {table}.", "warning")
        return redirect(url_for("admin"))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(rows[0].keys())
    writer.writerows(rows)
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv"}
    )


@app.route("/admin/change_password", methods=["POST"])
@login_required
def change_password():
    if not current_user.is_admin:
        return "Forbidden", 403
    user_id = request.form.get("user_id")
    new_pw  = request.form.get("new_password", "").strip()
    if len(new_pw) < 6:
        flash("Password must be at least 6 characters.", "warning")
        return redirect(url_for("admin"))
    conn = get_db()
    conn.execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (generate_password_hash(new_pw), user_id)
    )
    conn.commit()
    conn.close()
    flash("Password updated.", "success")
    return redirect(url_for("admin"))


if __name__ == "__main__":
    init_db()
    print("\n  Casetta App running at http://localhost:5050\n")
    app.run(debug=True, port=5050)
