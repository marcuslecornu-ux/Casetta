from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os
import csv
import io
import json
from datetime import datetime, date
from database import (get_db, init_db, ROOMS, DRINK_CATEGORIES, EXPENSE_CATEGORIES,
                       BOOKING_SOURCES, CASETTA_ROOMS, PROPERTIES, LOCATIONS, CATEGORY_CODE_PREFIX)

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    _limiter_available = True
except ImportError:
    _limiter_available = False

app = Flask(__name__)
_secret = os.environ.get("SECRET_KEY")
if not _secret:
    import warnings
    warnings.warn(
        "SECRET_KEY environment variable is not set. "
        "Using insecure fallback — set SECRET_KEY in PythonAnywhere environment variables.",
        stacklevel=2
    )
app.secret_key = _secret or "casetta-secret-2026-change-in-production"

# Rate limiter — brute-force protection on /login (5 attempts / 15 min / IP)
if _limiter_available:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=[],          # no global limit; only apply to /login
        storage_uri="memory://",
    )
    _login_limit = limiter.limit("5 per 15 minutes")
else:
    def _login_limit(f): return f  # no-op when flask-limiter not installed

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


def check_double_booking(conn, property_name, room, arrival, departure, exclude_id=None):
    """Return list of conflicting confirmed/provisional bookings."""
    query = """
        SELECT * FROM bookings
        WHERE confirmed != 'CXL' AND arrival < ? AND departure > ?
    """
    params = [departure, arrival]
    if exclude_id:
        query += " AND id != ?"
        params.append(exclude_id)
    existing = conn.execute(query, params).fetchall()
    conflicts = []
    for b in existing:
        b_prop = b["property"] or "Casetta"
        b_room = b["room"]
        if property_name == "Folegandros":
            if b_prop == "Folegandros":
                conflicts.append(b)
        elif property_name == "Casetta":
            if b_prop == "Casetta":
                # Whole house conflicts with everything; individual rooms only conflict with whole house
                if room == "Whole House" or b_room == "Whole House":
                    conflicts.append(b)
    return conflicts


def generate_uid(prefix="", suffix=""):
    now = datetime.now()
    s = f"{now.strftime('%Y%m%d-%H%M%S%f')}-{prefix}"
    if suffix:
        s += f"-{suffix}"
    return s


def log_action(conn, action_type, entity_type, entity_id, description, detail=None):
    """Insert one row into audit_log. Call this before conn.commit()."""
    user_id   = current_user.id           if current_user.is_authenticated else None
    user_name = current_user.display_name if current_user.is_authenticated else "system"
    ip        = request.remote_addr
    conn.execute("""
        INSERT INTO audit_log (user_id, user_name, action_type, entity_type, entity_id, description, detail, ip_address)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_id, user_name, action_type, entity_type, str(entity_id) if entity_id is not None else None,
          description, json.dumps(detail) if detail else None, ip))


# ─── AUTH ─────────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
@_login_limit
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

        log_action(conn, "CREATE", "drink_sale", uid,
                   f"Sold {quantity}x {item_name} ({unit_type}) to {data.get('room')} — €{total_sale:.2f}",
                   {"item_id": item_id, "room": data.get("room"), "quantity": quantity,
                    "unit_type": unit_type, "unit_price": unit_price, "total": total_sale,
                    "hosted": bool(is_hosted), "date": sale_date})

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


@app.route("/sales/edit/<uid>", methods=["POST"])
@login_required
def edit_sale(uid):
    conn = get_db()
    # Get original sale to calculate stock diff
    original = conn.execute("SELECT item_id, quantity FROM drink_sales WHERE uid=?", (uid,)).fetchone()
    old_item_id  = original["item_id"]  if original else None
    old_quantity = original["quantity"] if original else 0

    unit_type  = request.form.get("unit_type", "Bottle")
    is_hosted  = 1 if request.form.get("is_hosted") else 0
    quantity   = int(request.form.get("quantity", 1))
    new_item_id = request.form.get("item_id", "")
    unit_price = float(request.form.get("unit_price", 0))
    discount_pct = float(request.form.get("discount_pct", 0))

    if is_hosted:
        total_sale   = 0
        discount_pct = 100
    else:
        total_sale = unit_price * quantity * (1 - discount_pct / 100)

    conn.execute("""
        UPDATE drink_sales SET
            date=?, room=?, item_id=?, item_name=?, category=?,
            quantity=?, unit_type=?, unit_price=?, discount_pct=?,
            is_hosted=?, total_sale=?, notes=?
        WHERE uid=?
    """, (
        request.form.get("date"),
        request.form.get("room"),
        new_item_id,
        request.form.get("item_name"),
        request.form.get("category"),
        quantity, unit_type, unit_price, discount_pct,
        is_hosted, total_sale,
        request.form.get("notes", ""),
        uid
    ))

    # Adjust stock: restore old, deduct new
    if old_item_id:
        if old_item_id == new_item_id:
            # Same item — just apply the difference
            diff = quantity - old_quantity
            if diff > 0:
                conn.execute("UPDATE stock_items SET current_stock = MAX(0, current_stock - ?) WHERE id=?", (diff, new_item_id))
            elif diff < 0:
                conn.execute("UPDATE stock_items SET current_stock = current_stock + ? WHERE id=?", (-diff, new_item_id))
        else:
            # Item changed — restore old item stock, deduct new item stock
            conn.execute("UPDATE stock_items SET current_stock = current_stock + ? WHERE id=?", (old_quantity, old_item_id))
            conn.execute("UPDATE stock_items SET current_stock = MAX(0, current_stock - ?) WHERE id=?", (quantity, new_item_id))

    log_action(conn, "UPDATE", "drink_sale", uid,
               f"Edited sale: {quantity}x {request.form.get('item_name')} — €{total_sale:.2f}",
               {"room": request.form.get("room"), "quantity": quantity, "total": total_sale,
                "stock_adjusted": f"{old_item_id} qty {old_quantity} → {new_item_id} qty {quantity}"})
    conn.commit()
    conn.close()
    flash("Sale updated.", "success")
    return redirect(url_for("sales"))


@app.route("/sales/delete/<uid>", methods=["POST"])
@login_required
def delete_sale(uid):
    conn = get_db()
    row = conn.execute("SELECT item_id, item_name, quantity, room FROM drink_sales WHERE uid=?", (uid,)).fetchone()
    if row:
        # Restore stock
        conn.execute("UPDATE stock_items SET current_stock = current_stock + ? WHERE id=?",
                     (row["quantity"], row["item_id"]))
        log_action(conn, "DELETE", "drink_sale", uid,
                   f"Deleted sale: {row['item_name']} x{row['quantity']} ({row['room']})",
                   {"item_id": row["item_id"], "quantity": row["quantity"], "stock_restored": True})
    else:
        log_action(conn, "DELETE", "drink_sale", uid, f"Deleted sale {uid}")
    conn.execute("DELETE FROM drink_sales WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    flash("Sale deleted. Stock restored.", "success")
    return redirect(url_for("sales"))


@app.route("/api/next_code/<category>")
@login_required
def next_code(category):
    info = CATEGORY_CODE_PREFIX.get(category)
    if not info:
        return jsonify({"code": ""})
    prefix, start = info
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM stock_items WHERE id LIKE ?", (f"{prefix}%",)
    ).fetchall()
    conn.close()
    nums = set()
    for row in existing:
        try:
            nums.add(int(row["id"][len(prefix):]))
        except ValueError:
            pass
    n = start
    while n in nums:
        n += 1
    return jsonify({"code": f"{prefix}{n}"})


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
    item = conn.execute("SELECT name FROM stock_items WHERE id=?", (item_id,)).fetchone()
    new_buy  = float(request.form.get("purchase_price", 0))
    new_sell = float(request.form.get("selling_price_bottle", 0))
    new_gls  = float(request.form.get("selling_price_glass", 0))
    conn.execute("""
        UPDATE stock_items
        SET purchase_price=?, selling_price_bottle=?, selling_price_glass=?, location=?
        WHERE id=?
    """, (new_buy, new_sell, new_gls, request.form.get("location", ""), item_id))
    log_action(conn, "UPDATE", "stock_item", item_id,
               f"Prices updated: {item['name'] if item else item_id} — buy €{new_buy:.2f} / sell €{new_sell:.2f}",
               {"purchase_price": new_buy, "selling_price_bottle": new_sell, "selling_price_glass": new_gls})
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
                if mov_type == "Purchase" and unit_cost > 0:
                    # Weighted average cost: blend old stock price with new purchase price
                    row = conn.execute(
                        "SELECT current_stock, purchase_price FROM stock_items WHERE id=?", (item_id,)
                    ).fetchone()
                    old_qty   = row["current_stock"] if row else 0
                    old_price = row["purchase_price"] if row else 0
                    total_qty = old_qty + qty
                    blended   = ((old_qty * old_price) + (qty * unit_cost)) / total_qty if total_qty else unit_cost
                    conn.execute(
                        "UPDATE stock_items SET current_stock = current_stock + ?, purchase_price = ? WHERE id=?",
                        (qty, round(blended, 4), item_id)
                    )
                else:
                    conn.execute("UPDATE stock_items SET current_stock = current_stock + ? WHERE id=?", (qty, item_id))
            else:
                conn.execute("UPDATE stock_items SET current_stock = MAX(0, current_stock - ?) WHERE id=?", (qty, item_id))

            log_action(conn, "CREATE", "stock_movement", item_id,
                       f"{mov_type}: {qty}x {item_row['name'] if item_row else item_id} @ €{unit_cost:.2f}",
                       {"item_id": item_id, "movement_type": mov_type, "quantity": qty,
                        "unit_cost": unit_cost, "total": qty * unit_cost,
                        "notes": request.form.get("notes", "")})
            conn.commit()
            flash("Stock movement recorded.", "success")

        elif action == "add_item":
            new_id = request.form.get("new_id", "").strip().upper()
            if new_id and not conn.execute("SELECT id FROM stock_items WHERE id=?", (new_id,)).fetchone():
                conn.execute("""
                    INSERT INTO stock_items
                    (id, category, name, purchase_price, selling_price_bottle, selling_price_glass,
                     current_stock, location, winery, region, grape, bottle_size)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (new_id,
                      request.form.get("new_category"),
                      request.form.get("new_name"),
                      float(request.form.get("new_purchase_price", 0)),
                      float(request.form.get("new_selling_bottle", 0)),
                      float(request.form.get("new_selling_glass", 0)),
                      int(request.form.get("new_stock", 0)),
                      request.form.get("new_location", ""),
                      request.form.get("new_winery", ""),
                      request.form.get("new_region", ""),
                      request.form.get("new_grape", ""),
                      request.form.get("new_bottle_size", "")))
                conn.commit()

                # Auto-log initial stock as a movement entry for the audit trail
                new_stock = int(request.form.get("new_stock", 0))
                new_pp    = float(request.form.get("new_purchase_price", 0))
                new_name  = request.form.get("new_name", "")
                if new_stock > 0:
                    conn.execute("""
                        INSERT INTO stock_movements
                        (date, item_id, item_name, movement_type, quantity, unit_cost, total_cost, notes)
                        VALUES (?,?,?,?,?,?,?,?)
                    """, (date.today().isoformat(), new_id, new_name,
                          "New Item", new_stock, new_pp, new_stock * new_pp,
                          "Auto-logged: new item added to system"))
                    conn.commit()

                log_action(conn, "CREATE", "stock_item", new_id,
                           f"New stock item: {request.form.get('new_name')} ({new_id})",
                           {"category": request.form.get("new_category"),
                            "purchase_price": float(request.form.get("new_purchase_price", 0)),
                            "selling_price": float(request.form.get("new_selling_bottle", 0)),
                            "initial_stock": int(request.form.get("new_stock", 0))})
                conn.commit()
                flash(f"New item {new_id} added.", "success")
            else:
                flash("Item ID already exists or is blank.", "warning")

        return redirect(url_for("stock"))

    items = conn.execute(
        "SELECT * FROM stock_items WHERE active=1 ORDER BY category, name"
    ).fetchall()
    mvt_type   = request.args.get("mvt_type", "")
    mvt_search = request.args.get("mvt_search", "")
    mvt_query  = "SELECT * FROM stock_movements WHERE 1=1"
    mvt_params = []
    if mvt_type:
        mvt_query += " AND movement_type=?"; mvt_params.append(mvt_type)
    if mvt_search:
        mvt_query += " AND item_name LIKE ?"; mvt_params.append(f"%{mvt_search}%")
    mvt_query += " ORDER BY created_at DESC LIMIT 200"
    movements = conn.execute(mvt_query, mvt_params).fetchall()
    conn.close()

    return render_template("stock.html",
        items=items,
        movements=movements,
        categories=DRINK_CATEGORIES,
        locations=LOCATIONS,
        today=date.today().isoformat(),
        mvt_type=mvt_type,
        mvt_search=mvt_search,
    )


@app.route("/stock/delete/<item_id>", methods=["POST"])
@login_required
def delete_stock_item(item_id):
    conn = get_db()
    item = conn.execute("SELECT * FROM stock_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        flash("Item not found.", "warning")
    elif item["current_stock"] != 0:
        flash(f"Cannot delete {item_id} — stock level must be zero first.", "warning")
    else:
        log_action(conn, "DELETE", "stock_item", item_id,
                   f"Deleted stock item: {item['name']} ({item_id})",
                   {"name": item["name"], "category": item["category"]})
        conn.execute("DELETE FROM stock_items WHERE id=?", (item_id,))
        conn.commit()
        flash(f"Item {item_id} removed.", "success")
    conn.close()
    return redirect(url_for("stock") + "#tabInventory")


# ─── GLOBAL CONTEXT ──────────────────────────────────────────────────────────

@app.context_processor
def inject_manager_count():
    """Make manager action count available in all templates for sidebar badge."""
    if not current_user.is_authenticated:
        return {"manager_action_count": 0}
    try:
        conn = get_db()
        today = date.today()
        _month_num = """CASE TRIM(UPPER(month))
            WHEN 'JAN' THEN 1 WHEN 'FEB' THEN 2 WHEN 'MAR' THEN 3
            WHEN 'APR' THEN 4 WHEN 'MAY' THEN 5 WHEN 'JUN' THEN 6
            WHEN 'JUL' THEN 7 WHEN 'AUG' THEN 8 WHEN 'SEP' THEN 9
            WHEN 'OCT' THEN 10 WHEN 'NOV' THEN 11 WHEN 'DEC' THEN 12 ELSE 0 END"""
        count = conn.execute(f"""
            SELECT COUNT(*) FROM expenses
            WHERE status='Forecast'
            AND (year < ? OR (year = ? AND ({_month_num}) < ?))
        """, (today.year, today.year, today.month)).fetchone()[0]
        conn.close()
        return {"manager_action_count": count}
    except Exception:
        return {"manager_action_count": 0}


# ─── MANAGER ACTIONS ──────────────────────────────────────────────────────────

@app.route("/manager")
@login_required
def manager():
    today = date.today()
    conn  = get_db()
    _month_num = """CASE TRIM(UPPER(month))
        WHEN 'JAN' THEN 1 WHEN 'FEB' THEN 2 WHEN 'MAR' THEN 3
        WHEN 'APR' THEN 4 WHEN 'MAY' THEN 5 WHEN 'JUN' THEN 6
        WHEN 'JUL' THEN 7 WHEN 'AUG' THEN 8 WHEN 'SEP' THEN 9
        WHEN 'OCT' THEN 10 WHEN 'NOV' THEN 11 WHEN 'DEC' THEN 12 ELSE 0 END"""

    # Year / month filters
    filter_year  = request.args.get("filter_year",  "all")
    filter_month = request.args.get("filter_month", "all")

    where  = ["status='Forecast'",
              f"(year < ? OR (year = ? AND ({_month_num}) < ?))"]
    params = [today.year, today.year, today.month]

    if filter_year != "all":
        where.append("year = ?")
        params.append(int(filter_year))
    if filter_month != "all":
        where.append(f"TRIM(UPPER(month)) = ?")
        params.append(filter_month.upper())

    overdue = conn.execute(f"""
        SELECT *, ({_month_num}) AS month_num
        FROM expenses
        WHERE {' AND '.join(where)}
        ORDER BY year, ({_month_num}), category
    """, params).fetchall()

    # Available years for filter (all overdue years, unfiltered)
    all_years = conn.execute(f"""
        SELECT DISTINCT year FROM expenses
        WHERE status='Forecast'
          AND (year < ? OR (year = ? AND ({_month_num}) < ?))
        ORDER BY year
    """, (today.year, today.year, today.month)).fetchall()

    total = sum(r["amount"] for r in overdue)
    suppliers = conn.execute(
        "SELECT DISTINCT name FROM expense_suppliers WHERE active=1 ORDER BY name"
    ).fetchall()
    conn.close()
    from database import EXPENSE_CATEGORIES
    _months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    return render_template("manager.html",
        overdue=overdue,
        total=total,
        today=today.isoformat(),
        categories=EXPENSE_CATEGORIES,
        suppliers=[r["name"] for r in suppliers],
        all_years=[r["year"] for r in all_years],
        filter_year=filter_year,
        filter_month=filter_month,
        month_names=_months,
    )


@app.route("/manager/mark-all-paid", methods=["POST"])
@login_required
def manager_mark_all_paid():
    today = date.today()
    conn  = get_db()
    _month_num = """CASE TRIM(UPPER(month))
        WHEN 'JAN' THEN 1 WHEN 'FEB' THEN 2 WHEN 'MAR' THEN 3
        WHEN 'APR' THEN 4 WHEN 'MAY' THEN 5 WHEN 'JUN' THEN 6
        WHEN 'JUL' THEN 7 WHEN 'AUG' THEN 8 WHEN 'SEP' THEN 9
        WHEN 'OCT' THEN 10 WHEN 'NOV' THEN 11 WHEN 'DEC' THEN 12 ELSE 0 END"""
    filter_year  = request.form.get("filter_year",  "all")
    filter_month = request.form.get("filter_month", "all")
    where  = ["status='Forecast'",
              f"(year < ? OR (year = ? AND ({_month_num}) < ?))"]
    params = [today.year, today.year, today.month]
    if filter_year != "all":
        where.append("year = ?")
        params.append(int(filter_year))
    if filter_month != "all":
        where.append(f"TRIM(UPPER(month)) = ?")
        params.append(filter_month.upper())
    result = conn.execute(
        f"UPDATE expenses SET status='Paid' WHERE {' AND '.join(where)}", params)
    count = result.rowcount
    log_action(conn, "UPDATE", "expense", None,
               f"Manager: bulk marked {count} forecast expense(s) as Paid"
               + (f" — year {filter_year}" if filter_year != "all" else "")
               + (f" {filter_month}" if filter_month != "all" else ""))
    conn.commit()
    conn.close()
    flash(f"{count} expense(s) marked as Paid.", "success")
    return redirect(url_for("manager", filter_year=filter_year, filter_month=filter_month))


@app.route("/manager/mark-paid/<uid>", methods=["POST"])
@login_required
def manager_mark_paid(uid):
    conn = get_db()
    row = conn.execute("SELECT category, amount FROM expenses WHERE uid=?", (uid,)).fetchone()
    conn.execute("UPDATE expenses SET status='Paid' WHERE uid=?", (uid,))
    log_action(conn, "UPDATE", "expense", uid,
               f"Manager: marked as Paid — {row['category']} €{row['amount']:.2f}" if row else f"Manager: marked {uid} as Paid")
    conn.commit()
    conn.close()
    return ("", 204)


@app.route("/manager/edit/<uid>", methods=["POST"])
@login_required
def manager_edit_expense(uid):
    expense_month = request.form.get("expense_month", date.today().strftime("%Y-%m"))
    exp_date   = expense_month + "-01"
    entry_date = request.form.get("entry_date", date.today().isoformat())
    dt = datetime.strptime(exp_date, "%Y-%m-%d")
    conn = get_db()
    conn.execute("""
        UPDATE expenses
        SET date=?,entry_date=?,category=?,sub_category=?,comments=?,amount=?,status=?,month=?,year=?
        WHERE uid=?
    """, (exp_date, entry_date, request.form.get("category"),
          request.form.get("sub_category",""), request.form.get("comments",""),
          float(request.form.get("amount",0)), request.form.get("status","Paid"),
          dt.strftime("%b"), dt.year, uid))
    log_action(conn, "UPDATE", "expense", uid,
               f"Manager action — edited: {request.form.get('category')} €{float(request.form.get('amount',0)):.2f} ({dt.strftime('%b %Y')})")
    conn.commit()
    conn.close()
    flash("Expense updated.", "success")
    return redirect(url_for("manager"))


@app.route("/manager/delete/<uid>", methods=["POST"])
@login_required
def manager_delete_expense(uid):
    conn = get_db()
    row  = conn.execute("SELECT category, amount FROM expenses WHERE uid=?", (uid,)).fetchone()
    log_action(conn, "DELETE", "expense", uid,
               f"Manager action — deleted: {row['category']} €{row['amount']:.2f}" if row else f"Deleted expense {uid}")
    conn.execute("DELETE FROM expenses WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    flash("Expense deleted.", "success")
    return redirect(url_for("manager"))


# ─── EXPENSES ─────────────────────────────────────────────────────────────────

@app.route("/expenses", methods=["GET", "POST"])
@login_required
def expenses():
    if request.method == "POST":
        conn = get_db()
        try:
            category     = request.form.get("category")
            sub_cat      = request.form.get("sub_category", "")
            comments     = request.form.get("comments", "")
            amount       = float(request.form.get("amount", 0))
            if amount <= 0:
                flash("Amount must be greater than zero.", "warning")
                conn.close()
                return redirect(url_for("expenses", tab="expenses", year=date.today().year))
            status       = request.form.get("status", "Paid")
            entry_date   = request.form.get("entry_date", date.today().isoformat())
            is_recurring = request.form.get("is_recurring") == "1"

            if is_recurring:
                # Selected months from the checkbox grid e.g. ["2025-07", "2025-08"]
                selected_months = request.form.getlist("months[]")
                created = 0
                for i, ym in enumerate(selected_months):
                    exp_date = ym + "-01"
                    dt = datetime.strptime(exp_date, "%Y-%m-%d")
                    uid = generate_uid("EXP", f"{i}-{ym}")
                    conn.execute("""
                        INSERT INTO expenses
                        (uid,date,entry_date,category,sub_category,comments,amount,status,month,year)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (uid, exp_date, entry_date, category, sub_cat, comments, amount,
                          status, dt.strftime("%b"), dt.year))
                    log_action(conn, "CREATE", "expense", uid,
                               f"Recurring expense: {category} — €{amount:.2f} ({dt.strftime('%b %Y')})",
                               {"category": category, "sub_category": sub_cat,
                                "amount": amount, "month": dt.strftime("%b %Y"), "recurring": True})
                    created += 1
                conn.commit()
                flash(f"{created} expense records created.", "success")
            else:
                # Single expense — date field is a month picker ("YYYY-MM"), convert to first of month
                expense_month = request.form.get("expense_month", date.today().strftime("%Y-%m"))
                exp_date = expense_month + "-01"
                dt = datetime.strptime(exp_date, "%Y-%m-%d")
                uid = generate_uid("EXP")
                conn.execute("""
                    INSERT INTO expenses
                    (uid,date,entry_date,category,sub_category,comments,amount,status,month,year)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (uid, exp_date, entry_date, category, sub_cat, comments, amount,
                      status, dt.strftime("%b"), dt.year))
                log_action(conn, "CREATE", "expense", uid,
                           f"Expense: {category} — €{amount:.2f} ({dt.strftime('%b %Y')})",
                           {"category": category, "sub_category": sub_cat,
                            "amount": amount, "month": dt.strftime("%b %Y"), "status": status})
                conn.commit()
                flash("Expense recorded.", "success")
        finally:
            conn.close()
        return redirect(url_for("expenses", tab="expenses", year=date.today().year))

    # ── GET ────────────────────────────────────────────────────────────────────
    tab          = request.args.get("tab", "expenses")
    year_filter  = request.args.get("year", str(date.today().year))
    cat_filter   = request.args.get("cat", "")
    status_filter = request.args.get("status", "all")  # all / Paid / Forecast

    conn = get_db()

    # Status clause
    if status_filter in ("Paid", "Forecast"):
        _s_clause = " AND status=?"
        _s_param  = [status_filter]
    else:
        _s_clause = ""
        _s_param  = []

    # Month normaliser — trims whitespace AND normalises capitalisation
    _month_norm = """CASE TRIM(UPPER(month))
        WHEN 'JAN' THEN 'Jan' WHEN 'FEB' THEN 'Feb' WHEN 'MAR' THEN 'Mar'
        WHEN 'APR' THEN 'Apr' WHEN 'MAY' THEN 'May' WHEN 'JUN' THEN 'Jun'
        WHEN 'JUL' THEN 'Jul' WHEN 'AUG' THEN 'Aug' WHEN 'SEP' THEN 'Sep'
        WHEN 'OCT' THEN 'Oct' WHEN 'NOV' THEN 'Nov' WHEN 'DEC' THEN 'Dec'
        ELSE TRIM(month) END"""
    _month_order = """CASE TRIM(UPPER(month))
        WHEN 'JAN' THEN 1 WHEN 'FEB' THEN 2 WHEN 'MAR' THEN 3
        WHEN 'APR' THEN 4 WHEN 'MAY' THEN 5 WHEN 'JUN' THEN 6
        WHEN 'JUL' THEN 7 WHEN 'AUG' THEN 8 WHEN 'SEP' THEN 9
        WHEN 'OCT' THEN 10 WHEN 'NOV' THEN 11 WHEN 'DEC' THEN 12 END"""

    if year_filter == "all":
        all_expenses = conn.execute(
            f"SELECT * FROM expenses WHERE 1=1{_s_clause} ORDER BY date DESC",
            _s_param
        ).fetchall()
        totals = conn.execute(
            f"SELECT category, SUM(amount) as total, COUNT(*) as cnt FROM expenses WHERE 1=1{_s_clause} GROUP BY category ORDER BY total DESC",
            _s_param
        ).fetchall()
        monthly = conn.execute(f"""
            SELECT year || '-' || ({_month_norm}) AS ym, SUM(amount) AS total
            FROM expenses WHERE 1=1{_s_clause}
            GROUP BY year, TRIM(UPPER(month))
            ORDER BY year DESC, {_month_order}
        """, _s_param).fetchall()
    else:
        all_expenses = conn.execute(
            f"SELECT * FROM expenses WHERE year=?{_s_clause} ORDER BY date DESC",
            [year_filter] + _s_param
        ).fetchall()
        totals = conn.execute(
            f"SELECT category, SUM(amount) as total, COUNT(*) as cnt FROM expenses WHERE year=?{_s_clause} GROUP BY category ORDER BY total DESC",
            [year_filter] + _s_param
        ).fetchall()
        monthly = conn.execute(f"""
            SELECT ({_month_norm}) AS month, SUM(amount) AS total
            FROM expenses WHERE year=?{_s_clause}
            GROUP BY TRIM(UPPER(month))
            ORDER BY {_month_order}
        """, [year_filter] + _s_param).fetchall()

    years = conn.execute("SELECT DISTINCT year FROM expenses ORDER BY year DESC").fetchall()

    sup_rows = conn.execute(
        "SELECT id, category, name, pct_casetta, pct_farm, pct_personal FROM expense_suppliers WHERE active=1 ORDER BY category, name"
    ).fetchall()
    cat_split_rows = conn.execute(
        "SELECT category, pct_casetta, pct_farm, pct_personal FROM expense_category_splits"
    ).fetchall()
    conn.close()

    suppliers_by_cat = {}
    for row in sup_rows:
        suppliers_by_cat.setdefault(row["category"], []).append({
            "id": row["id"], "name": row["name"],
            "pct_casetta": row["pct_casetta"] if row["pct_casetta"] is not None else 1.0,
            "pct_farm":    row["pct_farm"]    if row["pct_farm"]    is not None else 0.0,
            "pct_personal":row["pct_personal"]if row["pct_personal"]is not None else 0.0,
        })
    cat_splits = {r["category"]: {
        "pct_casetta": r["pct_casetta"] if r["pct_casetta"] is not None else 1.0,
        "pct_farm":    r["pct_farm"]    if r["pct_farm"]    is not None else 0.0,
        "pct_personal":r["pct_personal"]if r["pct_personal"]is not None else 0.0,
    } for r in cat_split_rows}

    return render_template("expenses.html",
        tab=tab,
        categories=EXPENSE_CATEGORIES,
        all_expenses=all_expenses,
        totals=totals,
        monthly=monthly,
        years=["all"] + [r["year"] for r in years],
        year_filter=year_filter,
        status_filter=status_filter,
        today=date.today().isoformat(),
        suppliers_by_cat=suppliers_by_cat,
        cat_splits=cat_splits,
        cat_filter=cat_filter,
    )


@app.route("/expenses/edit/<uid>", methods=["POST"])
@login_required
def edit_expense(uid):
    expense_month = request.form.get("expense_month", date.today().strftime("%Y-%m"))
    exp_date  = expense_month + "-01"
    entry_date = request.form.get("entry_date", date.today().isoformat())
    dt = datetime.strptime(exp_date, "%Y-%m-%d")
    conn = get_db()
    edit_amount = float(request.form.get("amount", 0))
    if edit_amount <= 0:
        flash("Amount must be greater than zero.", "warning")
        return_year   = request.form.get("return_year", str(dt.year))
        return_status = request.form.get("return_status", "all")
        return redirect(url_for("expenses", tab="expenses", year=return_year, status=return_status))
    conn.execute("""
        UPDATE expenses
        SET date=?,entry_date=?,category=?,sub_category=?,comments=?,amount=?,status=?,month=?,year=?
        WHERE uid=?
    """, (exp_date, entry_date, request.form.get("category"),
          request.form.get("sub_category",""), request.form.get("comments",""),
          edit_amount, request.form.get("status","Paid"),
          dt.strftime("%b"), dt.year, uid))
    log_action(conn, "UPDATE", "expense", uid,
               f"Edited expense: {request.form.get('category')} — €{edit_amount:.2f} ({dt.strftime('%b %Y')})")
    conn.commit()
    conn.close()
    flash("Expense updated.", "success")
    return_year   = request.form.get("return_year", str(dt.year))
    return_status = request.form.get("return_status", "all")
    return redirect(url_for("expenses", tab="expenses", year=return_year, status=return_status))


@app.route("/expenses/delete/<uid>", methods=["POST"])
@login_required
def delete_expense(uid):
    conn = get_db()
    row = conn.execute("SELECT year, category, amount FROM expenses WHERE uid=?", (uid,)).fetchone()
    year = row["year"] if row else date.today().year
    log_action(conn, "DELETE", "expense", uid,
               f"Deleted expense: {row['category']} €{row['amount']:.2f}" if row else f"Deleted expense {uid}")
    conn.execute("DELETE FROM expenses WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    flash("Expense deleted.", "success")
    return_year   = request.form.get("return_year", str(year))
    return_status = request.form.get("return_status", "all")
    return redirect(url_for("expenses", tab="expenses", year=return_year, status=return_status))


@app.route("/api/expense_suppliers/<path:category>")
@login_required
def api_expense_suppliers(category):
    conn = get_db()
    rows = conn.execute(
        "SELECT name FROM expense_suppliers WHERE category=? AND active=1 ORDER BY name",
        (category,)
    ).fetchall()
    conn.close()
    return jsonify([r["name"] for r in rows])


@app.route("/expenses/suppliers/add", methods=["POST"])
@login_required
def add_expense_supplier():
    category = request.form.get("category","").strip()
    name     = request.form.get("name","").strip()
    if category and name:
        conn = get_db()
        try:
            conn.execute("INSERT OR IGNORE INTO expense_suppliers (category,name) VALUES (?,?)", (category, name))
            conn.commit()
        except Exception:
            pass
        conn.close()
        flash(f"Added '{name}'.", "success")
    return redirect(url_for("expenses", tab="maintenance", cat=category))


@app.route("/expenses/suppliers/splits/<int:supplier_id>", methods=["POST"])
@login_required
def update_supplier_splits(supplier_id):
    """Save Casetta/Farm/Personal split % for a supplier (called via fetch)."""
    data = request.get_json(force=True)
    pc = round(float(data.get("pct_casetta", 0)), 4)
    pf = round(float(data.get("pct_farm", 0)), 4)
    pp = round(float(data.get("pct_personal", 0)), 4)
    total = round(pc + pf + pp, 4)
    if abs(total - 1.0) > 0.01:
        return jsonify({"ok": False, "error": f"Splits must sum to 100% (got {round(total*100)}%)"}), 400
    conn = get_db()
    conn.execute("""
        UPDATE expense_suppliers SET pct_casetta=?, pct_farm=?, pct_personal=? WHERE id=?
    """, (pc, pf, pp, supplier_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/expenses/category-splits", methods=["POST"])
@login_required
def update_category_splits():
    """Save Casetta/Farm/Personal split % for a category (called via fetch)."""
    data = request.get_json(force=True)
    category = data.get("category", "")
    pc = round(float(data.get("pct_casetta", 0)), 4)
    pf = round(float(data.get("pct_farm", 0)), 4)
    pp = round(float(data.get("pct_personal", 0)), 4)
    if not category:
        return jsonify({"ok": False, "error": "no category"}), 400
    total = round(pc + pf + pp, 4)
    if abs(total - 1.0) > 0.01:
        return jsonify({"ok": False, "error": f"Splits must sum to 100% (got {round(total*100)}%)"}), 400
    conn = get_db()
    conn.execute("""
        INSERT INTO expense_category_splits (category, pct_casetta, pct_farm, pct_personal)
        VALUES (?,?,?,?)
        ON CONFLICT(category) DO UPDATE SET pct_casetta=excluded.pct_casetta,
            pct_farm=excluded.pct_farm, pct_personal=excluded.pct_personal
    """, (category, pc, pf, pp))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/expenses/suppliers/delete/<int:supplier_id>", methods=["POST"])
@login_required
def delete_expense_supplier(supplier_id):
    conn = get_db()
    row = conn.execute("SELECT category FROM expense_suppliers WHERE id=?", (supplier_id,)).fetchone()
    category = row["category"] if row else ""
    conn.execute("DELETE FROM expense_suppliers WHERE id=?", (supplier_id,))
    conn.commit()
    conn.close()
    flash("Supplier removed.", "success")
    return redirect(url_for("expenses", tab="maintenance", cat=category))


@app.route("/expenses/month-detail")
@login_required
def expenses_month_detail():
    """Return all expenses for a given year + month as JSON (for modal drill-down)."""
    year  = request.args.get("year", "")
    month = request.args.get("month", "")
    if not year or not month:
        return jsonify([])
    conn = get_db()
    rows = conn.execute("""
        SELECT date, category, sub_category, comments, amount, status
        FROM expenses
        WHERE year=? AND TRIM(month)=?
        ORDER BY date, category
    """, (year, month.strip())).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# ─── BOOKINGS ─────────────────────────────────────────────────────────────────

@app.route("/bookings", methods=["GET", "POST"])
@login_required
def bookings():
    from datetime import timedelta
    if request.method == "POST":
        conn = get_db()
        arrival = request.form.get("arrival")
        num_nights = int(request.form.get("num_nights", 1))
        property_name = request.form.get("property", "Casetta")
        room = request.form.get("room", "Whole House")

        arr_dt = datetime.strptime(arrival, "%Y-%m-%d")
        dep_dt = arr_dt + timedelta(days=num_nights)
        departure = dep_dt.date().isoformat()

        conflicts = check_double_booking(conn, property_name, room, arrival, departure)
        if conflicts:
            names = ", ".join(c["guest_name"] for c in conflicts)
            flash(f"⚠ Double booking conflict with: {names}. Dates overlap an existing booking.", "warning")
            conn.close()
            return redirect(url_for("bookings"))

        cur = conn.execute("""
            INSERT INTO bookings
            (entry_date, guest_name, property, room, arrival, num_nights, departure,
             source, source_code, confirmed, rate_type, total_cost, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (date.today().isoformat(),
              request.form.get("guest_name"),
              property_name, room,
              arrival, num_nights, departure,
              request.form.get("source"),
              request.form.get("source_code"),
              request.form.get("confirmed", "Yes"),
              request.form.get("rate_type", "RACK"),
              float(request.form.get("total_cost", 0)),
              request.form.get("notes", "")))
        new_booking_id = cur.lastrowid
        log_action(conn, "CREATE", "booking", new_booking_id,
                   f"Booking: {request.form.get('guest_name')} · {room} · {arrival} ({num_nights} nights)",
                   {"guest": request.form.get("guest_name"), "property": property_name,
                    "room": room, "arrival": arrival, "departure": departure,
                    "num_nights": num_nights, "source": request.form.get("source"),
                    "confirmed": request.form.get("confirmed"), "total_cost": float(request.form.get("total_cost", 0))})
        conn.commit()
        conn.close()
        flash("Booking saved.", "success")
        redirect_after = request.form.get("redirect_after", url_for("bookings"))
        return redirect(redirect_after)

    conn = get_db()
    year_filter = request.args.get("year", str(date.today().year))
    tab = request.args.get("tab", "")
    all_bookings = conn.execute(
        "SELECT * FROM bookings WHERE arrival LIKE ? ORDER BY arrival",
        (f"{year_filter}%",)
    ).fetchall()
    rates = conn.execute(
        "SELECT * FROM booking_rates ORDER BY property, date_from"
    ).fetchall()
    conn.close()

    return render_template("bookings.html",
        sources=BOOKING_SOURCES,
        casetta_rooms=CASETTA_ROOMS,
        all_bookings=all_bookings,
        booking_rates=rates,
        year_filter=int(year_filter),
        tab=tab,
        today=date.today().isoformat()
    )


@app.route("/bookings/calendar")
@login_required
def bookings_calendar():
    # Load all bookings (small dataset — filtered client-side by month/year/property)
    conn = get_db()
    all_b = conn.execute("""
        SELECT id, entry_date, guest_name, property, room, arrival, departure,
               num_nights, source, source_code, confirmed, rate_type, total_cost, notes
        FROM bookings ORDER BY arrival
    """).fetchall()
    conn.close()
    return render_template("booking_calendar.html",
        bookings_json=json.dumps([dict(b) for b in all_b]),
        sources=BOOKING_SOURCES,
        years=list(range(2024, date.today().year + 3)),
    )


@app.route("/bookings/edit/<int:booking_id>", methods=["POST"])
@login_required
def edit_booking(booking_id):
    from datetime import timedelta
    conn = get_db()
    arrival = request.form.get("arrival")
    num_nights = int(request.form.get("num_nights", 1))
    property_name = request.form.get("property", "Casetta")
    room = request.form.get("room", "Whole House")

    arr_dt = datetime.strptime(arrival, "%Y-%m-%d")
    dep_dt = arr_dt + timedelta(days=num_nights)
    departure = dep_dt.date().isoformat()

    conflicts = check_double_booking(conn, property_name, room, arrival, departure, exclude_id=booking_id)
    if conflicts:
        names = ", ".join(c["guest_name"] for c in conflicts)
        flash(f"⚠ Double booking conflict with: {names}.", "warning")
        conn.close()
        return redirect(url_for("bookings"))

    conn.execute("""
        UPDATE bookings SET
            guest_name=?, property=?, room=?, arrival=?, num_nights=?, departure=?,
            source=?, source_code=?, confirmed=?, rate_type=?, total_cost=?, notes=?
        WHERE id=?
    """, (
        request.form.get("guest_name"),
        property_name, room, arrival, num_nights, departure,
        request.form.get("source"),
        request.form.get("source_code"),
        request.form.get("confirmed", "Yes"),
        request.form.get("rate_type", "RACK"),
        float(request.form.get("total_cost", 0)),
        request.form.get("notes", ""),
        booking_id
    ))
    log_action(conn, "UPDATE", "booking", booking_id,
               f"Edited booking #{booking_id}: {request.form.get('guest_name')} · {room} · {arrival}",
               {"guest": request.form.get("guest_name"), "property": property_name,
                "room": room, "arrival": arrival, "num_nights": num_nights,
                "confirmed": request.form.get("confirmed"), "total_cost": float(request.form.get("total_cost", 0))})
    conn.commit()
    conn.close()
    flash("Booking updated.", "success")
    return redirect(url_for("bookings"))


@app.route("/bookings/delete/<int:booking_id>", methods=["POST"])
@login_required
def delete_booking(booking_id):
    conn = get_db()
    row = conn.execute("SELECT guest_name, room, arrival FROM bookings WHERE id=?", (booking_id,)).fetchone()
    log_action(conn, "DELETE", "booking", booking_id,
               f"Deleted booking #{booking_id}: {row['guest_name']} · {row['room']} · {row['arrival']}" if row else f"Deleted booking #{booking_id}")
    conn.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    flash("Booking deleted.", "success")
    return redirect(url_for("bookings"))


@app.route("/bookings/rates", methods=["POST"])
@login_required
def manage_rates():
    conn = get_db()
    action = request.form.get("action")
    if action == "add":
        rate   = float(request.form.get("rate_per_night", 0))
        prop   = request.form.get("property")
        d_from = request.form.get("date_from")
        d_to   = request.form.get("date_to")
        conn.execute("""
            INSERT INTO booking_rates (property, room, source, date_from, date_to, rate_per_night, notes)
            VALUES (?,?,?,?,?,?,?)
        """, (prop, request.form.get("room", ""), request.form.get("source", ""),
              d_from, d_to, rate, request.form.get("notes", "")))
        log_action(conn, "CREATE", "booking_rate", None,
                   f"Rate added: {prop} €{rate:.0f}/night ({d_from} → {d_to})",
                   {"property": prop, "rate": rate, "from": d_from, "to": d_to})
        conn.commit()
        flash("Rate period added.", "success")
    elif action == "delete":
        rate_id = request.form.get("rate_id")
        row = conn.execute("SELECT property, rate_per_night, date_from FROM booking_rates WHERE id=?", (rate_id,)).fetchone()
        log_action(conn, "DELETE", "booking_rate", rate_id,
                   f"Rate deleted: {row['property']} €{row['rate_per_night']:.0f}/night from {row['date_from']}" if row else f"Rate {rate_id} deleted")
        conn.execute("DELETE FROM booking_rates WHERE id=?", (rate_id,))
        conn.commit()
        flash("Rate deleted.", "success")
    conn.close()
    return redirect(url_for("bookings") + "?tab=rates")


# ─── ADMIN ────────────────────────────────────────────────────────────────────

@app.route("/admin/audit")
@login_required
def admin_audit():
    if not current_user.is_admin:
        flash("Admin access only.", "danger")
        return redirect(url_for("dashboard"))
    conn = get_db()
    # Filters
    f_type   = request.args.get("type", "")
    f_entity = request.args.get("entity", "")
    f_user   = request.args.get("user", "")
    f_date   = request.args.get("date", "")
    f_search = request.args.get("q", "")

    query = "SELECT * FROM audit_log WHERE 1=1"
    params = []
    if f_type:
        query += " AND action_type=?"; params.append(f_type)
    if f_entity:
        query += " AND entity_type=?"; params.append(f_entity)
    if f_user:
        query += " AND user_name=?"; params.append(f_user)
    if f_date:
        query += " AND timestamp LIKE ?"; params.append(f_date + "%")
    if f_search:
        query += " AND description LIKE ?"; params.append(f"%{f_search}%")
    query += " ORDER BY timestamp DESC LIMIT 500"

    logs  = conn.execute(query, params).fetchall()
    users = conn.execute("SELECT DISTINCT user_name FROM audit_log WHERE user_name IS NOT NULL ORDER BY user_name").fetchall()
    conn.close()
    return render_template("admin_audit.html", logs=logs, users=users,
                           f_type=f_type, f_entity=f_entity, f_user=f_user,
                           f_date=f_date, f_search=f_search)


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


# ─── OTHER INCOME ─────────────────────────────────────────────────────────────

@app.route("/other-income", methods=["GET", "POST"])
@login_required
def other_income():
    conn = get_db()

    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            qty        = float(request.form.get("quantity", 1))
            unit_price = float(request.form.get("unit_price", 0))
            total      = qty * unit_price
            uid        = generate_uid("INC")
            conn.execute("""
                INSERT INTO other_income
                (uid, date, type, sub_type, comments, unit_label, quantity, unit_price, total)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (uid,
                  request.form.get("date", date.today().isoformat()),
                  request.form.get("type"),
                  request.form.get("sub_type"),
                  request.form.get("comments", ""),
                  request.form.get("unit_label", "Units"),
                  qty, unit_price, total))
            log_action(conn, "CREATE", "other_income", uid,
                       f"{request.form.get('sub_type')} — {qty} {request.form.get('unit_label','Units')} @ €{unit_price:.2f} = €{total:.2f}",
                       {"type": request.form.get("type"), "sub_type": request.form.get("sub_type"),
                        "quantity": qty, "unit_price": unit_price, "total": total})
            conn.commit()
            flash("Income recorded.", "success")

        elif action == "add_category":
            cat_type = request.form.get("cat_type", "").strip()
            cat_sub  = request.form.get("cat_sub", "").strip()
            if cat_type and cat_sub:
                try:
                    conn.execute("INSERT INTO other_income_categories (type, sub_type) VALUES (?,?)", (cat_type, cat_sub))
                    log_action(conn, "CREATE", "other_income_category", None,
                               f"Category added: {cat_type} / {cat_sub}")
                    conn.commit()
                    flash(f"Added '{cat_sub}' under '{cat_type}'.", "success")
                except Exception:
                    flash("Category already exists.", "warning")
            else:
                flash("Both Type and Sub-type are required.", "warning")

        elif action == "delete_category":
            cat_id = request.form.get("cat_id")
            row = conn.execute("SELECT type, sub_type FROM other_income_categories WHERE id=?", (cat_id,)).fetchone()
            log_action(conn, "DELETE", "other_income_category", cat_id,
                       f"Category deleted: {row['type']} / {row['sub_type']}" if row else f"Category {cat_id} deleted")
            conn.execute("DELETE FROM other_income_categories WHERE id=?", (cat_id,))
            conn.commit()
            flash("Category removed.", "success")

        conn.close()
        return redirect(url_for("other_income"))

    # GET — load records and categories
    year_filter = request.args.get("year", str(date.today().year))
    records = conn.execute(
        "SELECT * FROM other_income WHERE date LIKE ? ORDER BY date DESC, created_at DESC",
        (f"{year_filter}%",)
    ).fetchall()
    categories = conn.execute(
        "SELECT * FROM other_income_categories WHERE active=1 ORDER BY type, sub_type"
    ).fetchall()
    years = conn.execute(
        "SELECT DISTINCT substr(date,1,4) AS yr FROM other_income ORDER BY yr DESC"
    ).fetchall()
    conn.close()

    # Build type → sub_types map for JS
    cat_map = {}
    for c in categories:
        cat_map.setdefault(c["type"], []).append(c["sub_type"])

    cat_types = sorted(cat_map.keys())
    return render_template("other_income.html",
        records=records,
        categories=categories,
        cat_map_json=json.dumps(cat_map),
        cat_types=cat_types,
        years=["all"] + [r["yr"] for r in years] + ([str(date.today().year)] if str(date.today().year) not in [r["yr"] for r in years] else []),
        year_filter=year_filter,
        today=date.today().isoformat(),
    )


@app.route("/other-income/edit/<uid>", methods=["POST"])
@login_required
def edit_other_income(uid):
    conn = get_db()
    qty        = float(request.form.get("quantity", 1))
    unit_price = float(request.form.get("unit_price", 0))
    total      = qty * unit_price
    conn.execute("""
        UPDATE other_income
        SET date=?, type=?, sub_type=?, comments=?, unit_label=?, quantity=?, unit_price=?, total=?
        WHERE uid=?
    """, (request.form.get("date"),
          request.form.get("type"),
          request.form.get("sub_type"),
          request.form.get("comments", ""),
          request.form.get("unit_label", "Units"),
          qty, unit_price, total, uid))
    log_action(conn, "UPDATE", "other_income", uid,
               f"Edited: {request.form.get('sub_type')} — {qty} @ €{unit_price:.2f} = €{total:.2f}")
    conn.commit()
    conn.close()
    flash("Record updated.", "success")
    return redirect(url_for("other_income"))


@app.route("/other-income/delete/<uid>", methods=["POST"])
@login_required
def delete_other_income(uid):
    conn = get_db()
    row = conn.execute("SELECT sub_type, quantity, total FROM other_income WHERE uid=?", (uid,)).fetchone()
    log_action(conn, "DELETE", "other_income", uid,
               f"Deleted: {row['sub_type']} — €{row['total']:.2f}" if row else f"Deleted income {uid}")
    conn.execute("DELETE FROM other_income WHERE uid=?", (uid,))
    conn.commit()
    conn.close()
    flash("Record deleted.", "success")
    return redirect(url_for("other_income"))


# ─── ACCOUNTING ───────────────────────────────────────────────────────────────

@app.route("/accounting")
@login_required
def accounting():
    year = int(request.args.get("year", date.today().year))
    months = [f"{year}-{m:02d}" for m in range(1, 13)]
    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    prop_filter = request.args.get("property", "Casetta")   # default to Casetta only
    from database import PROPERTIES

    conn = get_db()

    # ── Accommodation (bookings.total_cost, keyed by arrival month) ──
    prop_clause = "" if prop_filter == "All" else " AND (property=? OR (property IS NULL AND ?='Casetta'))"
    prop_params = [] if prop_filter == "All" else [prop_filter, prop_filter]
    accom_rows = conn.execute(f"""
        SELECT strftime('%Y-%m', arrival) AS ym, SUM(total_cost) AS total
        FROM bookings WHERE strftime('%Y', arrival)=? AND confirmed != 'CXL'{prop_clause}
        GROUP BY ym
    """, ([str(year)] + prop_params)).fetchall()
    accom = {r["ym"]: r["total"] for r in accom_rows}

    # ── Drink sales (is_hosted=0) ──
    drinks_rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS ym, SUM(total_sale) AS total
        FROM drink_sales WHERE strftime('%Y', date)=? AND is_hosted=0
        GROUP BY ym
    """, (str(year),)).fetchall()
    drinks = {r["ym"]: r["total"] for r in drinks_rows}

    # ── Other income — by month AND by type ──
    other_rows = conn.execute("""
        SELECT strftime('%Y-%m', date) AS ym, type, SUM(total) AS total
        FROM other_income WHERE strftime('%Y', date)=?
        GROUP BY ym, type
    """, (str(year),)).fetchall()
    other_types = sorted(set(r["type"] for r in other_rows))
    # other[type][ym] = total
    other = {}
    for r in other_rows:
        other.setdefault(r["type"], {})[r["ym"]] = r["total"]

    # ── Expenses — Paid only, grouped by expense PERIOD (year+month), not entry date ──
    raw_exp_rows = conn.execute("""
        SELECT
            year || '-' || CASE TRIM(UPPER(month))
                WHEN 'JAN' THEN '01' WHEN 'FEB' THEN '02' WHEN 'MAR' THEN '03'
                WHEN 'APR' THEN '04' WHEN 'MAY' THEN '05' WHEN 'JUN' THEN '06'
                WHEN 'JUL' THEN '07' WHEN 'AUG' THEN '08' WHEN 'SEP' THEN '09'
                WHEN 'OCT' THEN '10' WHEN 'NOV' THEN '11' WHEN 'DEC' THEN '12'
                ELSE '00' END AS ym,
            category, sub_category, SUM(amount) AS total
        FROM expenses WHERE year=? AND status='Paid'
        GROUP BY ym, category, sub_category
    """, (str(year),)).fetchall()

    # Load split tables
    sup_split_map = {
        (r["category"], r["name"]): (
            r["pct_casetta"] if r["pct_casetta"] is not None else 1.0,
            r["pct_farm"]    if r["pct_farm"]    is not None else 0.0,
            r["pct_personal"]if r["pct_personal"]is not None else 0.0,
        )
        for r in conn.execute(
            "SELECT category, name, pct_casetta, pct_farm, pct_personal FROM expense_suppliers"
        ).fetchall()
    }
    cat_split_map = {
        r["category"]: (
            r["pct_casetta"] if r["pct_casetta"] is not None else 1.0,
            r["pct_farm"]    if r["pct_farm"]    is not None else 0.0,
            r["pct_personal"]if r["pct_personal"]is not None else 0.0,
        )
        for r in conn.execute(
            "SELECT category, pct_casetta, pct_farm, pct_personal FROM expense_category_splits"
        ).fetchall()
    }

    exp_cats = sorted(set(r["category"] for r in raw_exp_rows))
    # expenses[stream][category][ym] = total  (stream: 'total','casetta','farm','personal')
    expenses = {s: {} for s in ("total", "casetta", "farm", "personal")}
    for r in raw_exp_rows:
        cat  = r["category"]
        sub  = r["sub_category"] or ""
        ym   = r["ym"]
        amt  = r["total"] or 0
        key  = (cat, sub)
        if key in sup_split_map:
            pc, pf, pp = sup_split_map[key]
        elif cat in cat_split_map:
            pc, pf, pp = cat_split_map[cat]
        else:
            pc, pf, pp = 1.0, 0.0, 0.0
        for stream, pct in [("total", 1.0), ("casetta", pc), ("farm", pf), ("personal", pp)]:
            expenses[stream].setdefault(cat, {}).setdefault(ym, 0)
            expenses[stream][cat][ym] += amt * pct

    # ── Available years (union across all tables) ──
    yrs_sql = """
        SELECT DISTINCT strftime('%Y', arrival) AS yr FROM bookings WHERE arrival IS NOT NULL
        UNION SELECT DISTINCT strftime('%Y', date) FROM drink_sales
        UNION SELECT DISTINCT strftime('%Y', date) FROM other_income
        UNION SELECT DISTINCT strftime('%Y', date) FROM expenses
        ORDER BY yr DESC
    """
    available_years = [r[0] for r in conn.execute(yrs_sql).fetchall() if r[0]]
    conn.close()

    # ── Helper: row totals ──
    def month_vals(data_dict, ym_list):
        return [data_dict.get(ym, 0) or 0 for ym in ym_list]

    # Build structured data for template
    inc_accom  = month_vals(accom, months)
    inc_drinks = month_vals(drinks, months)
    inc_other  = {t: month_vals(other.get(t, {}), months) for t in other_types}

    # Total income per month
    inc_total = []
    for i in range(12):
        t = inc_accom[i] + inc_drinks[i] + sum(inc_other[ot][i] for ot in other_types)
        inc_total.append(t)

    # Expense rows per month — 4 streams: total, casetta, farm, personal
    def build_exp_rows(stream):
        return {c: month_vals(expenses[stream].get(c, {}), months) for c in exp_cats}

    exp_rows_data     = build_exp_rows("total")
    exp_rows_casetta  = build_exp_rows("casetta")
    exp_rows_farm     = build_exp_rows("farm")
    exp_rows_personal = build_exp_rows("personal")

    def stream_total(rows):
        return [sum(rows[c][i] for c in exp_cats) for i in range(12)]

    exp_total     = stream_total(exp_rows_data)
    exp_casetta   = stream_total(exp_rows_casetta)
    exp_farm      = stream_total(exp_rows_farm)
    exp_personal  = stream_total(exp_rows_personal)

    # Profit (all streams vs total income)
    profit = [inc_total[i] - exp_total[i] for i in range(12)]
    margin = [round(profit[i]/inc_total[i]*100, 1) if inc_total[i] else 0 for i in range(12)]

    def row_total(lst): return sum(lst)

    return render_template("accounting.html",
        year=year,
        available_years=available_years if available_years else [year],
        months=months,
        month_labels=month_labels,
        # Income
        inc_accom=inc_accom,
        inc_drinks=inc_drinks,
        inc_other=inc_other,
        other_types=other_types,
        inc_total=inc_total,
        # Expenses — all streams
        exp_rows=exp_rows_data,
        exp_rows_casetta=exp_rows_casetta,
        exp_rows_farm=exp_rows_farm,
        exp_rows_personal=exp_rows_personal,
        exp_total=exp_total,
        exp_casetta=exp_casetta,
        exp_farm=exp_farm,
        exp_personal=exp_personal,
        exp_cats=exp_cats,
        # P&L
        profit=profit,
        margin=margin,
        row_total=row_total,
        # Property filter
        prop_filter=prop_filter,
        properties=["All"] + PROPERTIES,
    )


@app.route("/menus")
@login_required
def menus():
    return render_template("menus.html")


@app.route("/menu/<path:location>")
@login_required
def print_menu(location):
    conn = get_db()
    items = conn.execute(
        "SELECT * FROM stock_items WHERE location=? AND active=1 ORDER BY selling_price_bottle DESC",
        (location,)
    ).fetchall()
    conn.close()
    return render_template("menu_print.html", items=items, location=location)


@app.route("/admin/menu/<path:location>")
@login_required
def print_menu_admin(location):
    return redirect(url_for("print_menu", location=location))


if __name__ == "__main__":
    init_db()
    print("\n  Casetta App running at http://localhost:5050\n")
    app.run(debug=True, port=5050)
