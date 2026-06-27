import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "casetta.db")

ROOMS = ["Menta", "Lavanda", "Salvia", "Prezzemolo", "Cantina",
         "Casetta - WH", "Xenia - Hosting", "Angela - Hosting", "Slippage", "Events"]

DRINK_CATEGORIES = ["Beer", "Cocktail", "Digestivo", "Hot drinks", "Red", "Red (T)",
                    "Rose", "Soft drink", "Sparkling", "Spirit", "White", "White (T)"]

EXPENSE_CATEGORIES = [
    "BUSINESS EXP & ENRICHMENT COSTS", "CAPITAL PROJECTS", "CONSULTANTS",
    "DIGITAL OFFICE & HOME SUPPLIES:", "INSURANCE:", "MAINTENANCE SUPPLIERS",
    "MARKETING", "PERSONAL:", "PRODUCE / FOOD COSTS", "STAFF",
    "SUPPLIERS", "TAX", "UTILITIES", "VEHICLE"
]

BOOKING_SOURCES = [
    ("Casetta (Direct - Tuscany)", "CD"),
    ("TTT", "TTT"),
    ("TTT (From Casetta)", "TTTC"),
    ("Gundari", "GUN"),
    ("FOL Casetta", "FOLC"),
    ("Xenia Offer Casetta", "XOFFC"),
    ("Xenia Offer Fol", "COFFF"),
]

STOCK_ITEMS = [
    ("SW1001","Sparkling","Col de Salici Prosecco"),
    ("SW1002","Sparkling","Villa Giustiani Prosecco Rosè"),
    ("SW1003","Sparkling","Marchese Antinori Spumante"),
    ("SW1004","Sparkling","Villa Folini Prosecco Rosè"),
    ("SW1005","Sparkling","Franciacorta Corte Aura 2021"),
    ("W2001","White","San Michele W"),
    ("W2003","White","Rocca Bernarda Sauvignon"),
    ("W2004","White","Rocca Bernarda Pinot Grigio"),
    ("W2005","White","Vermentino Antinori"),
    ("W2006","White","Vermentino Teia Villa Noviana"),
    ("W2007","White","Poggio Al Sole Sangiovese Bianco"),
    ("W2008","White","Vermentino Villa Marsiliana"),
    ("W2009","White","Pinot Grigio Terlano"),
    ("W2010","White","Tramin Sauvignon Bianco"),
    ("W2011","White","Mastrojanni Trebbiano 2024"),
    ("WT2012","White (T)","Vermentino Colli di Luni Fosso di Corsano Terenzuola 2023"),
    ("WT2013","White (T)","Pinot Bianco Medievum Gumphof 2023"),
    ("WT2014","White (T)","Grechetto La Torre a Civitella Sergio Mottura 2022"),
    ("WT2015","White (T)","Gewurtztraminer Turmhof Tiefenbruner 2022"),
    ("WT2016","White (T)","Adenzia Bianco Baglio del Cristo di Campobello 2023"),
    ("WT2017","White (T)","Kerner Abbazia di Novacella 2022"),
    ("R3001","Red","Sangiovese Grosseto"),
    ("R3003","Red","Caiarossa IGT 2019"),
    ("R3004","Red","Chianti Classico Gran Selezione"),
    ("R3005","Red","Morellino di Scansano"),
    ("R3006","Red","Brunello di Montalcino DOCG 2015"),
    ("R3007","Red","Brunello di Montalcino Mastrojanni 2017"),
    ("R3008","Red","Vino Nobile di Montepulciano"),
    ("R3009","Red","Rosso di Montalcino"),
    ("R3010","Red","Sassicaia 2019"),
    ("R3011","Red","Barolo Cannubi 2018"),
    ("R3012","Red","Amarone della Valpolicella"),
    ("R3013","Red","Bolgari Rosso Antinori"),
    ("R3014","Red","Chianti Classico Antinori"),
    ("R3015","Red","Tignanello 2019"),
    ("R3016","Red","Solaia 2019"),
    ("R3017","Red","Campomaggio Radda Chianti Classico 2020"),
    ("R3018","Red","Mastrojanni Rosso di Montalcino 2022"),
    ("R3019","Red","Badia a Coltibuono Chianti Classico 2020"),
    ("R3020","Red","Poggio Il Castellare Morellino Di Scansano 2021"),
    ("RT3021","Red (T)","Etna Rosso Planeta 2021"),
    ("RT3022","Red (T)","Cerasuolo di Vittoria Planeta 2022"),
    ("RT3023","Red (T)","Aglianico del Vulture Basilisco 2020"),
    ("RT3024","Red (T)","Nerello Mascalese Etna Rosso Terre Nere 2022"),
    ("RO4001","Rose","Castel del Monte Rosato Il Falcone 2022"),
    ("BR4002","Beer","Birra Moretti - Zero"),
    ("BR4003","Beer","Birra Moretti"),
    ("BR4004","Beer","Menabrea"),
    ("CK5001","Cocktail","Aperol"),
    ("CK5002","Cocktail","Campari"),
    ("CK5003","Cocktail","Martini Bianco"),
    ("CK5004","Cocktail","Martini Rosso"),
    ("SP5005","Spirit","Absolute Vodka 700ml"),
    ("SP5006","Spirit","Bacardi Rum 700ml"),
    ("SP5007","Spirit","Bombay Gin"),
    ("SP5008","Spirit","Casamigos Tequila 700ml"),
    ("SP5009","Spirit","Grey Goose Vodka 700ml"),
    ("SP5010","Spirit","VKA Tuscan Vodka 700ml"),
    ("SP5011","Spirit","Havana Club Rum 1000ml"),
    ("SP5012","Spirit","Tanqueray Ten Gin 1000ml"),
    ("DG6001","Digestivo","Limoncello"),
    ("DG6002","Digestivo","Grappa"),
    ("DG6003","Digestivo","Amaro"),
    ("SD6004","Soft drink","Still Water"),
    ("SD6005","Soft drink","Sparkling Water"),
    ("SD6006","Soft drink","Coca Cola"),
    ("SD6007","Soft drink","Orange Juice"),
    ("SD6008","Soft drink","Sparkling Water"),
    ("HD7001","Hot drinks","Coffee"),
    ("HD7002","Hot drinks","Tea"),
    ("DW8001","Digestivo","Dessert Wine"),
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _is_db_healthy():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("SELECT 1")
        conn.close()
        return True
    except Exception:
        return False


def init_db():
    # If DB file is corrupt, remove and start fresh
    if os.path.exists(DB_PATH) and not _is_db_healthy():
        os.remove(DB_PATH)
        journal = DB_PATH + "-journal"
        if os.path.exists(journal):
            os.remove(journal)
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS stock_items (
            id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            purchase_price REAL DEFAULT 0,
            selling_price_bottle REAL DEFAULT 0,
            selling_price_glass REAL DEFAULT 0,
            current_stock INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS drink_sales (
            uid TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            room TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_type TEXT NOT NULL,
            unit_price REAL DEFAULT 0,
            discount_pct REAL DEFAULT 0,
            is_hosted INTEGER DEFAULT 0,
            total_sale REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            item_id TEXT NOT NULL,
            item_name TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            unit_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS expenses (
            uid TEXT PRIMARY KEY,
            date TEXT NOT NULL,
            category TEXT NOT NULL,
            sub_category TEXT,
            comments TEXT,
            amount REAL NOT NULL,
            status TEXT DEFAULT 'Paid',
            month TEXT,
            year INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            guest_name TEXT NOT NULL,
            room TEXT NOT NULL,
            arrival TEXT NOT NULL,
            num_nights INTEGER NOT NULL,
            departure TEXT,
            source TEXT,
            source_code TEXT,
            confirmed TEXT DEFAULT 'Yes',
            rate_type TEXT DEFAULT 'RACK',
            total_cost REAL DEFAULT 0,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)

    # Seed stock items if empty
    count = c.execute("SELECT COUNT(*) FROM stock_items").fetchone()[0]
    if count == 0:
        for item_id, category, name in STOCK_ITEMS:
            c.execute(
                "INSERT OR IGNORE INTO stock_items (id, category, name) VALUES (?, ?, ?)",
                (item_id, category, name)
            )

    conn.commit()
    conn.close()
