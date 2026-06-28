import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), "casetta.db")

ROOMS = ["Casetta Whole House", "Cantina", "Lavanda", "Menta", "Prezzemolo", "Salvia"]

PROPERTIES = ["Casetta", "Folegandros"]
CASETTA_ROOMS = ["Whole House", "Cantina", "Lavanda", "Menta", "Prezzemolo", "Salvia"]

LOCATIONS = ["Dining Room", "Loggia Fridge", "Loggia Glass Cabinet", "Cellar", "Kitchen"]

DRINK_CATEGORIES = ["Beer", "Cocktail", "Digestivo", "Hot drinks", "Red", "Red (T)",
                    "Rose", "Soft drink", "Sparkling", "Spirit", "White", "White (T)"]

# Maps category → (code_prefix, numeric_start) for auto-code generation
CATEGORY_CODE_PREFIX = {
    "Sparkling":  ("SW",  1001),
    "White":      ("W",   2001),
    "White (T)":  ("WT",  2012),
    "Rose":       ("P",   7001),
    "Red":        ("R",   3001),
    "Red (T)":    ("RT",  3016),
    "Beer":       ("BR",  4001),
    "Cocktail":   ("C",   8001),
    "Spirit":     ("SP",  5001),
    "Digestivo":  ("D",   7001),
    "Hot drinks": ("TC",  9001),
    "Soft drink": ("SD",  6001),
}

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

# Format: (id, category, name, purchase_price, selling_price_bottle)
STOCK_ITEMS = [
    # Sparkling
    ("SW1001", "Sparkling", "Col de Salici Prosecco",              9.65,  28.00),
    ("SW1002", "Sparkling", "Villa Giustiani Prosecco Rosè",        6.71,  23.00),
    ("SW1003", "Sparkling", "Marchese Antinori Spumante",          19.52,  58.00),
    ("SW1004", "Sparkling", "Villa Folini Prosecco Rosè",           6.90,  25.00),
    ("SW1005", "Sparkling", "Franciacorta Corte Aura 2021",        14.23,  39.00),
    ("SW1006", "Sparkling", "Louis Roederer Cristal 2015",          0.00, 820.00),
    ("SW1007", "Sparkling", "Krug Gran Cuvée Edition 171",          0.00, 760.00),
    ("SW1008", "Sparkling", "Krug Gran Cuvée Edition 168",          0.00, 720.00),
    ("SW1009", "Sparkling", "Dom Perignon 2015",                    0.00, 540.00),
    ("SW1010", "Sparkling", "Philipponat 2009",                     0.00, 195.00),
    ("SW1011", "Sparkling", "Lalier Réflexion R020",                0.00, 128.00),
    ("SW1012", "Sparkling", "Bolle di Borro Rosé 2017",             0.00, 150.00),
    ("SW1013", "Sparkling", "Berlucchi Cuvée Imperiale 150cl",      0.00, 160.00),
    # White
    ("W2001",  "White",     "San Michele W",                        7.90,  24.00),
    ("W2003",  "White",     "Rocca Bernarda Sauvignon",             0.00,   0.00),
    ("W2004",  "White",     "Rocca Bernarda Pinot Grigio",         10.11,  30.00),
    ("W2005",  "White",     "Vermentino Antinori",                 11.00,  33.00),
    ("W2006",  "White",     "Vermentino Teia Villa Noviana",       20.55,  62.00),
    ("W2007",  "White",     "Poggio Al Sole Sangiovese Bianco",     0.00,  28.00),
    ("W2008",  "White",     "Vermentino Villa Marsiliana",         12.69,  33.00),
    ("W2009",  "White",     "Pinot Grigio Terlano",                14.38,  35.00),
    ("W2010",  "White",     "Tramin Sauvignon Bianco",             14.52,  36.00),
    ("W2011",  "White",     "Mastrojanni Trebbiano 2024",          17.38,  42.00),
    # White (T)
    ("WT2012", "White (T)", "Vermentino Colli di Luni Fosso di Corsano Terenzuola 2023", 18.90, 37.00),
    ("WT2013", "White (T)", "Pinot Bianco Medievum Gumphof 2023",  16.90,  33.00),
    ("WT2014", "White (T)", "Grechetto La Torre a Civitella Sergio Mottura 2022", 24.90, 47.00),
    ("WT2015", "White (T)", "Gewurtztraminer Turmhof Tiefenbruner 2022", 23.00, 50.00),
    ("WT2016", "White (T)", "Adenzia Bianco Baglio del Cristo di Campobello 2023", 13.50, 27.00),
    # Rose
    ("P7001",  "Rose",      "Calafuria Rosè",                      12.06,  36.00),
    ("P7002",  "Rose",      "Campo al Mare Bolgheri",              13.30,  36.00),
    ("P7003",  "Rose",      "Sister Ula",                           5.84,  24.00),
    ("P7004",  "Rose",      "Cassiopea",                           15.75,  36.00),
    ("P7005",  "Rose",      "Sal'Asso Tenuta L'Apparita Rosè",     10.50,  39.00),
    # Red
    ("R3001",  "Red",       "San Michele R",                        8.00,  24.00),
    ("R3002",  "Red",       "Rosso Montalcino",                    14.03,  42.00),
    ("R3003",  "Red",       "Bolgheri Bruciato",                   17.73,  47.00),
    ("R3004",  "Red",       "Marchese Antinori Riserva 2015",      21.80, 110.00),
    ("R3005",  "Red",       "Brunello Scopone 2013",               18.00,  54.00),
    ("R3006",  "Red",       "Ulla",                                 5.25,  22.00),
    ("R3007",  "Red",       "Fonterutoli Chianti 2020",            14.49,  54.00),
    ("R3008",  "Red",       "Fonterutoli Vicoregio 2019",          46.75, 165.00),
    ("R3009",  "Red",       "Poggio Al Sole Trittico",              4.39,  23.00),
    ("R3010",  "Red",       "Poggio Al Sole Chianti Classico",     12.81,  34.00),
    ("R3011",  "Red",       "Tenuta L'Apparita D'Assolo Nero",     16.58,  38.00),
    ("R3012",  "Red",       "Tenuta L'Apparita D'Assolo Selezione Bianco", 19.90, 46.00),
    ("R3013",  "Red",       "Brunello Argiano 2020",               80.00, 180.00),
    ("R3014",  "Red",       "Rosso Argiano 2023",                  25.00,  46.00),
    ("R3015",  "Red",       "Tre Borri Corzano e Paterno 2018",    43.00, 110.00),
    ("R3016",  "Red",       "Giodo Brunello di Montalcino",        83.00, 240.00),
    ("R3017",  "Red",       "Magaldo 2016",                         0.00,  95.00),
    ("R3018",  "Red",       "Tieri del Fula Poggio Torselli 2004", 13.33, 130.00),
    ("R3019",  "Red",       "Fonterutoli Concerto 2020",           45.00, 130.00),
    ("R3020",  "Red",       "Fattoria dei Bardi Brunello di Montalcino 2019", 35.00, 85.00),
    ("R3021",  "Red",       "Le Corti Chianti Classico 2023",      14.00,  32.00),
    ("R3022",  "Red",       "Le Corti Birillo 2022",               13.00,  36.00),
    ("R3023",  "Red",       "Le Corti Don Tommaso 2021",           15.00,  38.00),
    ("R3024",  "Red",       "Collemattoni Rosso di Montalcino 2021", 17.00, 38.00),
    ("R3025",  "Red",       "Brolio Chianti Classico Ricasoli 2021", 20.00, 54.00),
    ("R3026",  "Red",       "Millanni Cusona 2015",                40.00, 108.00),
    ("R3027",  "Red",       "Le Corti Cortevecchia Chianti Classico 2022", 25.00, 50.00),
    ("R3028",  "Red",       "Ocra Bolgheri Guicciardini 2018",     11.67,  75.00),
    ("R3029",  "Red",       "Pian delle Vigne Rosso Montalcino 2016", 0.00, 58.00),
    ("R3030",  "Red",       "La Vigna delle Bambole Chianti Classico 2015", 22.00, 62.00),
    ("R3031",  "Red",       "Duemani 2017",                        90.00, 195.00),
    ("R3032",  "Red",       "Matsu",                                0.00,   0.00),
    ("R3033",  "Red",       "Argiano Brunello di Montalcino 2023",  0.00,  75.00),
    # Red (T)
    ("RT3016", "Red (T)",   "Rosso di Montalcino Cupano 2021",     43.90, 110.00),
    ("RT3017", "Red (T)",   "Lacrima di Moro D'Alba Rubico Marotti Campi 2023", 8.50, 37.00),
    ("RT3018", "Red (T)",   "Aglianico Jungano San Salvatore",     18.50,  25.00),
    ("RT3019", "Red (T)",   "Etna Rosso Tornatore 2021",           15.30,  34.00),
    ("RT3020", "Red (T)",   "Pelaverga di Verduno Basadone Castello di Verduno 2023", 17.50, 40.00),
    # Beer
    ("BR4001", "Beer",      "Birra Moretti",                        0.81,   7.00),
    ("BR4002", "Beer",      "Birra Moretti Zero",                   0.94,   5.00),
    ("BR4003", "Beer",      "Birra Messina",                        1.77,   5.00),
    ("BR4004", "Beer",      "Birra Tassomiglia",                    2.43,   8.00),
    ("BR4005", "Beer",      "Birra Maialetto",                      2.38,   8.00),
    ("BR4006", "Beer",      "Birra Peroni",                         0.80,   5.00),
    ("BR4007", "Beer",      "Birra Peroni 0%",                      1.10,   5.50),
    # Cocktail
    ("C8001",  "Cocktail",  "Roveta Dodici",                        0.00,  18.00),
    ("C8002",  "Cocktail",  "Omero",                                0.00,   0.00),
    ("C8003",  "Cocktail",  "Aperol Spritz",                        1.73,  10.00),
    ("C8004",  "Cocktail",  "Campari Soda",                         0.24,   4.50),
    # Spirit
    ("SP5001", "Spirit",    "Dessert Wine",                        25.00,  75.00),
    ("SP5002", "Spirit",    "Peter in Florence Gin 500ml",         31.94,  99.00),
    ("SP5003", "Spirit",    "Ginepraio Pontedera Gin",             40.00, 120.00),
    ("SP5004", "Spirit",    "Valombrosa Gin",                      55.00, 165.00),
    ("SP5005", "Spirit",    "Bombay Gin",                         322.00,  69.00),
    ("SP5006", "Spirit",    "Scape Grace Dry Gin 1000ml",          61.29, 183.87),
    ("SP5007", "Spirit",    "Duchess Gin 700ml",                   40.00, 120.00),
    ("SP5008", "Spirit",    "Grey Goose Vodka 700ml",              37.00, 117.00),
    ("SP5009", "Spirit",    "Absolute Vodka 700ml",                39.31,  47.00),
    ("SP5010", "Spirit",    "VKA Tuscan Vodka 700ml",              15.74, 132.00),
    ("SP5011", "Spirit",    "Havana Club Rum 1000ml",               8.44,  56.00),
    ("SP5012", "Spirit",    "Dictador Rum 1982",                   18.65, 830.00),
    ("SP5013", "Spirit",    "Campari 1000ml",                     213.17,  56.97),
    ("SP5014", "Spirit",    "Casamigos Tequila 700ml",             37.98, 165.00),
    ("SP5015", "Spirit",    "Ouzo 200ml",                          17.50,  20.40),
    ("SP5016", "Spirit",    "Bacardi Rum 700ml",                    8.13,  75.00),
    ("SP5017", "Spirit",    "Whiskey Single Malt 700ml",           87.50,  65.52),
    ("SP5018", "Spirit",    "Gin Mare 700ml",                      23.72, 120.00),
    ("SP5019", "Spirit",    "Tanqueray Ten Gin 1000ml",            59.00,  99.00),
    ("SP5020", "Spirit",    "Mount Gay Black Rum 700ml",           52.65,  89.00),
    ("SP5021", "Spirit",    "Monkey 47 Gin",                        0.00,   0.00),
    ("SP5022", "Spirit",    "Loch Lomond Whisky",                   0.00,   0.00),
    ("SP5023", "Spirit",    "Captain's Tsipouro",                   0.00,   0.00),
    # Digestivo
    ("D7001",  "Digestivo", "Molinari Sambucca 700ml",              0.00,  60.00),
    ("D7002",  "Digestivo", "Poli Grappa 700ml",                   22.00,  66.00),
    ("D7003",  "Digestivo", "Averna 700ml",                        16.16,  38.00),
    ("D7004",  "Digestivo", "Vin Santo del Chianti Antinori",      32.00,  60.00),
    ("D7005",  "Digestivo", "Limoncello 500ml",                     4.40,  30.00),
    ("D7006",  "Digestivo", "Skinos 1000ml",                       15.48,  46.44),
    ("D7007",  "Digestivo", "Amaro Certosa / Amaro Del Capo",      35.00, 105.00),
    ("D7008",  "Digestivo", "Elixir di S.Bernardo",                 0.00,   0.00),
    ("D7009",  "Digestivo", "Amaro Al Mirto",                       0.00,   0.00),
    ("D7010",  "Digestivo", "Ciobreliu Thyme Liqueur",              0.00,   7.00),
    # Hot drinks
    ("TC9001", "Hot drinks","Tea (Outside Breakfast)",              0.00,   3.50),
    ("TC9002", "Hot drinks","Coffee (Outside Breakfast)",           0.00,   2.50),
    ("TC9003", "Hot drinks","Cappuccino (Outside Breakfast)",       0.00,   3.50),
    # Soft drink
    ("SD6001", "Soft drink","Coke",                                 0.83,   3.00),
    ("SD6002", "Soft drink","Coke Zero",                            0.85,   3.00),
    ("SD6003", "Soft drink","Fanta",                                0.00,   0.00),
    ("SD6004", "Soft drink","Lemon Soda",                           0.77,   3.00),
    ("SD6005", "Soft drink","Schweppes Tonic 1L",                   1.20,   3.60),
    ("SD6006", "Soft drink","Fevertree Tonic",                      1.30,   4.50),
    ("SD6007", "Soft drink","Fevertree Ginger Beer",                1.24,   4.00),
    ("SD6008", "Soft drink","Sparkling Water",                      9.78,   2.50),
    ("SD6009", "Soft drink","Flat Mineral Water",                   1.52,   0.00),
    ("SD6010", "Soft drink","Flat Mineral Boccioni",                0.50,   3.60),
    ("SD6011", "Soft drink","Schweppes Soda Water",                 1.20,   3.00),
    ("SD6013", "Soft drink","Kinley Lemon",                         0.90,   3.00),
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
            active INTEGER DEFAULT 1,
            location TEXT DEFAULT '',
            winery TEXT DEFAULT '',
            region TEXT DEFAULT '',
            grape TEXT DEFAULT '',
            bottle_size TEXT DEFAULT ''
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

        CREATE TABLE IF NOT EXISTS booking_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property TEXT NOT NULL,
            room TEXT,
            source TEXT,
            date_from TEXT NOT NULL,
            date_to TEXT NOT NULL,
            rate_per_night REAL NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            display_name TEXT
        );

        CREATE TABLE IF NOT EXISTS expense_suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            active INTEGER DEFAULT 1,
            UNIQUE(category, name)
        );
    """)

    # Migrations — add columns silently if they don't exist yet
    migrations = [
        "ALTER TABLE bookings ADD COLUMN property TEXT",
        "ALTER TABLE stock_items ADD COLUMN location TEXT DEFAULT ''",
        "ALTER TABLE stock_items ADD COLUMN winery TEXT DEFAULT ''",
        "ALTER TABLE stock_items ADD COLUMN region TEXT DEFAULT ''",
        "ALTER TABLE stock_items ADD COLUMN grape TEXT DEFAULT ''",
        "ALTER TABLE stock_items ADD COLUMN bottle_size TEXT DEFAULT ''",
        "ALTER TABLE expenses ADD COLUMN entry_date TEXT DEFAULT ''",
    ]
    for sql in migrations:
        try:
            c.execute(sql)
            conn.commit()
        except Exception:
            pass

    # Backfill entry_date = date for existing expense records
    try:
        c.execute("UPDATE expenses SET entry_date=date WHERE entry_date IS NULL OR entry_date=''")
        conn.commit()
    except Exception:
        pass

    # Infer property for existing bookings with no property set
    try:
        c.execute("""
            UPDATE bookings SET property =
            CASE WHEN upper(room) LIKE '%FOL%' THEN 'Folegandros' ELSE 'Casetta' END
            WHERE property IS NULL OR property = ''
        """)
        conn.commit()
    except Exception:
        pass

    # Pre-populate locations from the printed menu sheets
    ITEM_LOCATIONS = {
        # Dining Room — wine cabinet
        "R3004": "Dining Room", "R3005": "Dining Room", "R3007": "Dining Room",
        "R3008": "Dining Room", "R3009": "Dining Room", "R3010": "Dining Room",
        "R3011": "Dining Room", "R3012": "Dining Room", "R3013": "Dining Room",
        "R3015": "Dining Room", "R3016": "Dining Room", "R3017": "Dining Room",
        "R3018": "Dining Room", "R3019": "Dining Room", "R3020": "Dining Room",
        "R3021": "Dining Room", "R3022": "Dining Room", "R3023": "Dining Room",
        "R3024": "Dining Room", "R3025": "Dining Room", "R3026": "Dining Room",
        "R3027": "Dining Room", "R3028": "Dining Room", "R3029": "Dining Room",
        "R3030": "Dining Room", "R3031": "Dining Room", "R3033": "Dining Room",
        "RT3016": "Dining Room",
        # Loggia Fridge
        "SW1003": "Loggia Fridge", "W2008": "Loggia Fridge", "W2009": "Loggia Fridge",
        "W2010": "Loggia Fridge", "W2011": "Loggia Fridge",
        "BR4006": "Loggia Fridge", "BR4007": "Loggia Fridge",
        "SD6001": "Loggia Fridge", "SD6002": "Loggia Fridge",
        "SD6006": "Loggia Fridge", "SD6007": "Loggia Fridge",
        "SD6011": "Loggia Fridge", "SD6013": "Loggia Fridge",
        "C8003":  "Loggia Fridge", "C8004":  "Loggia Fridge",
        "D7001":  "Loggia Fridge", "D7005":  "Loggia Fridge",
        "D7006":  "Loggia Fridge", "D7007":  "Loggia Fridge",
        "D7010":  "Loggia Fridge",
        "SP5008": "Loggia Fridge", "SP5010": "Loggia Fridge",
        # Loggia Glass Cabinet
        "D7002":  "Loggia Glass Cabinet", "SP5012": "Loggia Glass Cabinet",
        "SP5014": "Loggia Glass Cabinet", "SP5015": "Loggia Glass Cabinet",
        "SP5018": "Loggia Glass Cabinet",
        "SP5021": "Loggia Glass Cabinet", "SP5022": "Loggia Glass Cabinet",
        "SP5023": "Loggia Glass Cabinet",
        "D7008":  "Loggia Glass Cabinet", "D7009":  "Loggia Glass Cabinet",
        "SW1006": "Loggia Glass Cabinet", "SW1007": "Loggia Glass Cabinet",
        "SW1008": "Loggia Glass Cabinet", "SW1009": "Loggia Glass Cabinet",
        "SW1010": "Loggia Glass Cabinet", "SW1011": "Loggia Glass Cabinet",
        "SW1012": "Loggia Glass Cabinet", "SW1013": "Loggia Glass Cabinet",
    }
    for item_id, loc in ITEM_LOCATIONS.items():
        try:
            c.execute(
                "UPDATE stock_items SET location=? WHERE id=? AND (location IS NULL OR location='')",
                (loc, item_id)
            )
        except Exception:
            pass
    conn.commit()

    # Pre-populate winery / region / grape for Dining Room wines
    DINING_ROOM_DETAILS = {
        "R3004": ("Tenuta Tignanello",          "San Casciano",          "S/CS/CF"),
        "R3005": ("Scopone",                    "Montalcino",            "S"),
        "R3007": ("Mazzei",                     "Castellina in Chianti", "S/MAL/COL/M"),
        "R3008": ("Fonterutoli / Mazzei",       "Castellina in Chianti", "S"),
        "R3009": ("Poggio Al Sole",             "Tavarnelle",            "S/M/CS"),
        "R3010": ("Poggio Al Sole",             "Tavarnelle",            "S/C"),
        "R3011": ("D'Assolo Tenuta L'Apparita", "San Casciano",          "S"),
        "R3012": ("D'Assolo Tenuta L'Apparita", "San Casciano",          "S"),
        "R3013": ("Argiano",                    "Montalcino",            "S"),
        "R3015": ("Corzano e Paterno",          "San Casciano",          "S/CS/M"),
        "R3016": ("Giodo",                      "Montalcino",            "S"),
        "R3017": ("Carobbio",                   "Panzano in Chianti",    "S/M/CS"),
        "R3018": ("Tenuta Poggio Torselli",     "San Casciano",          "S/M/CS"),
        "R3019": ("Mazzei",                     "Castellina in Chianti", "S/CS"),
        "R3020": ("Fattoria di Barbi",          "Montalcino",            "S"),
        "R3021": ("Tenuta Le Corti",            "San Casciano",          "S/C"),
        "R3022": ("Tenuta Marsiliana / Le Corti","Maremma",              "M/CS"),
        "R3023": ("Villa Le Corti",             "San Casciano",          "S"),
        "R3024": ("Collemattoni",               "Montalcino",            "S"),
        "R3025": ("Ricasoli",                   "Gaiole in Chianti",     "S/M/CS"),
        "R3026": ("Cusona / Guicciardini",      "San Gimignano",         "S/M/CS"),
        "R3027": ("Villa Le Corti",             "San Casciano",          "S"),
        "R3028": ("Guicciardini Strozzi",       "Bolgheri",              "CS/M/S"),
        "R3029": ("Marchese Antinori",          "Montalcino",            "S"),
        "R3030": ("Il Palaggio di Panzano",     "Greve in Chianti",      "S"),
        "R3031": ("Azienda Agricola Duemani",   "Riparbella / Toscana",  "CF"),
        "R3033": ("Argiano",                    "Montalcino",            "S"),
        "RT3016": ("Cupano",                    "Montalcino",            "S"),
    }
    for item_id, (winery, region, grape) in DINING_ROOM_DETAILS.items():
        try:
            c.execute(
                "UPDATE stock_items SET winery=?, region=?, grape=? WHERE id=? AND (winery IS NULL OR winery='')",
                (winery, region, grape, item_id)
            )
        except Exception:
            pass
    conn.commit()

    # Pre-populate descriptions for Loggia Glass Cabinet spirits
    GLASS_CABINET_DESCRIPTIONS = {
        "D7002":  "Distillation of grapes",
        "SP5012": "Aged Colombian rum 1982",
        "SP5014": "Distillation of agave",
        "SP5015": "Anise-flavoured Greek spirit",
        "SP5018": "Mediterranean gin — rosemary, basil, thyme, olive",
        "SP5021": "German gin — Black Forest botanicals",
        "SP5022": "Scotch whisky",
        "SP5023": "Distillation of Greek grapes",
        "D7008":  "Herbal liqueur",
        "D7009":  "Herbal liqueur — Sardinian myrtle berry",
        "D7010":  "Thyme herb liqueur",
    }
    for item_id, desc in GLASS_CABINET_DESCRIPTIONS.items():
        try:
            c.execute(
                "UPDATE stock_items SET region=? WHERE id=? AND (region IS NULL OR region='')",
                (desc, item_id)
            )
        except Exception:
            pass
    conn.commit()

    # Set selling_price_glass for items sold by the glass (Glass Cabinet & Fridge)
    GLASS_PRICES = {
        "D7002":  10.00,  # Poli Grappa
        "D7003":   6.00,  # Averna
        "D7006":   6.00,  # Skinos
        "D7007":   8.00,  # Amaro del Capo
        "D7008":   8.00,  # Elixir di S.Bernardo
        "D7009":   8.00,  # Amaro Al Mirto
        "D7010":   7.00,  # Ciobreliu
        "SP5008": 14.00,  # Grey Goose
        "SP5010":  8.00,  # VKA Tuscan Vodka
        "SP5014": 14.00,  # Casamigos Tequila
        "SP5015":  8.00,  # Ouzo
        "SP5018":  8.00,  # Gin Mare
        "SP5021": 10.00,  # Monkey 47
        "SP5022": 12.00,  # Loch Lomond Whisky
        "SP5023":  9.00,  # Captain's Tsipouro
    }
    for item_id, glass_price in GLASS_PRICES.items():
        try:
            c.execute(
                "UPDATE stock_items SET selling_price_glass=? WHERE id=? AND (selling_price_glass IS NULL OR selling_price_glass=0)",
                (glass_price, item_id)
            )
        except Exception:
            pass
    conn.commit()

    # Sync master stock list — insert new, update prices/names for existing
    for item_id, category, name, pp, spb in STOCK_ITEMS:
        c.execute(
            "INSERT OR IGNORE INTO stock_items (id, category, name, purchase_price, selling_price_bottle) VALUES (?,?,?,?,?)",
            (item_id, category, name, pp, spb)
        )
        c.execute(
            "UPDATE stock_items SET category=?, name=?, purchase_price=?, selling_price_bottle=? WHERE id=?",
            (category, name, pp, spb, item_id)
        )
    conn.commit()

    # Seed expense suppliers from spreadsheet lookup data
    EXPENSE_SUPPLIER_SEED = [
        ("UTILITIES",                    "Electricity"),
        ("UTILITIES",                    "Gas"),
        ("UTILITIES",                    "Wood"),
        ("UTILITIES",                    "Pubblicaqua"),
        ("UTILITIES",                    "Car Fuel"),
        ("UTILITIES",                    "Lorry Fuel"),
        ("UTILITIES",                    "Carvin"),
        ("UTILITIES",                    "Cascina Pulita"),
        ("VEHICLE",                      "Car"),
        ("VEHICLE",                      "Road Tax"),
        ("VEHICLE",                      "John Deere"),
        ("VEHICLE",                      "Lorry"),
        ("TAX",                          "Social and Pension Tax (INPS)"),
        ("TAX",                          "Property Tax (IMU)"),
        ("TAX",                          "Consorzio Bonifica"),
        ("TAX",                          "IRPEF Personal Income tax (>25%)"),
        ("TAX",                          "IRAP local regional tax"),
        ("TAX",                          "VAT (IVA) agriturismo 50%"),
        ("TAX",                          "Chamber of Commerce Registration"),
        ("TAX",                          "IRPEF STAFF (tax on their income)"),
        ("TAX",                          "INPS STAFF (tax on their income)"),
        ("TAX",                          "TARI (Alia)"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Fattura in Cloud"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Acrobat Software"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Sky TV"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Netflix"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Spotify"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Apple TV"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Apple iCloud / iTunes"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "TIM S.p.A."),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "S.I.A.E"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Omniconnect srl"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Aruba S.p.A."),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Mailchimp"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Vimeo"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "WeTransfer"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Zoom"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "TV License"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Google 2 TB"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "Stripe"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "American Express Card"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "ChatGPT Plus"),
        ("DIGITAL OFFICE & HOME SUPPLIES:", "HBO"),
        ("STAFF",                        "Liliana"),
        ("STAFF",                        "Claudia"),
        ("STAFF",                        "Patrizia"),
        ("STAFF",                        "Arianna"),
        ("STAFF",                        "Jeffrey Thickman"),
        ("STAFF",                        "Elisa"),
        ("STAFF",                        "Salvatore"),
        ("STAFF",                        "Gabriele"),
        ("STAFF",                        "Francesca & Giuditta"),
        ("STAFF",                        "Noemi"),
        ("STAFF",                        "Melu"),
        ("STAFF",                        "Angela"),
        ("STAFF",                        "Niccolo Mattei"),
        ("INSURANCE:",                   "Agriturismo Insurance"),
        ("INSURANCE:",                   "Tractor Insurance"),
        ("INSURANCE:",                   "Car Insurance"),
        ("INSURANCE:",                   "Trailer Cart"),
        ("CONSULTANTS",                  "Agriconsulting"),
        ("CONSULTANTS",                  "Studio Arcadia SRL"),
        ("CONSULTANTS",                  "Dott. Manfreddi Bufalini"),
        ("CONSULTANTS",                  "Marranci Lorenzo"),
        ("MARKETING",                    "Finn (Advertising)"),
        ("MARKETING",                    "Stefan Russel (Social)"),
        ("MARKETING",                    "Up (Advertising)"),
        ("MARKETING",                    "Con Poulos"),
        ("MARKETING",                    "Social Media (Newsletter)"),
        ("MARKETING",                    "Romano"),
        ("MARKETING",                    "Advertising (Newsletter)"),
        ("MARKETING",                    "Gifts"),
        ("MARKETING",                    "GoDaddy"),
        ("MARKETING",                    "Virginia"),
        ("MAINTENANCE SUPPLIERS",        "CISA srl (Electrician)"),
        ("MAINTENANCE SUPPLIERS",        "IDRA (Plumber)"),
        ("MAINTENANCE SUPPLIERS",        "Chimney Sweep"),
        ("MAINTENANCE SUPPLIERS",        "Emiliano (Painter)"),
        ("MAINTENANCE SUPPLIERS",        "TV Antenna Man"),
        ("MAINTENANCE SUPPLIERS",        "Andrea Bini (Gate)"),
        ("MAINTENANCE SUPPLIERS",        "Fire Extinguishers"),
        ("MAINTENANCE SUPPLIERS",        "Culligan Italiana S.p.A"),
        ("MAINTENANCE SUPPLIERS",        "S.A.T. srl (Rinai)"),
        ("MAINTENANCE SUPPLIERS",        "Caldaia Kesser (Wood Furnace)"),
        ("MAINTENANCE SUPPLIERS",        "Lezzi Gabriele"),
        ("MAINTENANCE SUPPLIERS",        "Water Group Consulting"),
        ("MAINTENANCE SUPPLIERS",        "Farm Contractor (Eleonori)"),
        ("MAINTENANCE SUPPLIERS",        "Eden Garden"),
        ("MAINTENANCE SUPPLIERS",        "Scarabelli Irrigation SRL"),
        ("MAINTENANCE SUPPLIERS",        "Andrea Irrigation"),
        ("MAINTENANCE SUPPLIERS",        "Gamberini Gianluca (Mega Pruning)"),
        ("MAINTENANCE SUPPLIERS",        "Milli Massimiliano"),
        ("MAINTENANCE SUPPLIERS",        "Nicola Ceccarelli (Builder)"),
        ("MAINTENANCE SUPPLIERS",        "Beatrice Venturini"),
        ("MAINTENANCE SUPPLIERS",        "Samuel (Carpenter)"),
        ("MAINTENANCE SUPPLIERS",        "Marco (Carpenter)"),
        ("MAINTENANCE SUPPLIERS",        "Lorenzo Viglione"),
        ("MAINTENANCE SUPPLIERS",        "Gicarserramenti (fabbri)"),
        ("MAINTENANCE SUPPLIERS",        "Clima Center"),
        ("MAINTENANCE SUPPLIERS",        "Gabriele Laghi AC"),
        ("MAINTENANCE SUPPLIERS",        "Abritaly"),
        ("PRODUCE / FOOD COSTS",         "Breakfast"),
        ("PRODUCE / FOOD COSTS",         "Lunch"),
        ("PRODUCE / FOOD COSTS",         "Dinner"),
        ("PRODUCE / FOOD COSTS",         "Aperitivo"),
        ("PRODUCE / FOOD COSTS",         "Cooking Class - Home"),
        ("PRODUCE / FOOD COSTS",         "Francesco Grocery"),
        ("PRODUCE / FOOD COSTS",         "COOP"),
        ("PRODUCE / FOOD COSTS",         "Tiziano Grocery"),
        ("PRODUCE / FOOD COSTS",         "Daniele Terreni"),
        ("SUPPLIERS",                    "Florist Sancasciano"),
        ("SUPPLIERS",                    "Eurofomitura SRL"),
        ("SUPPLIERS",                    "Targioni Monica"),
        ("SUPPLIERS",                    "Tapezzeria Montecchi"),
        ("SUPPLIERS",                    "Aymara Italia"),
        ("SUPPLIERS",                    "Ilio Palmieri"),
        ("SUPPLIERS",                    "Vivaio (Plants)"),
        ("SUPPLIERS",                    "Amazon"),
        ("SUPPLIERS",                    "Sunchemicals"),
        ("SUPPLIERS",                    "Olmo Casa SRL"),
        ("SUPPLIERS",                    "Bernino Commerciali"),
        ("SUPPLIERS",                    "Officina Cirri srl"),
        ("SUPPLIERS",                    "S.Agri.Vit. Srl"),
        ("SUPPLIERS",                    "Az Agr Stoppioni"),
        ("SUPPLIERS",                    "Cioni"),
        ("SUPPLIERS",                    "Bianchini & Morelli"),
        ("SUPPLIERS",                    "SOCEPI Srl"),
        ("SUPPLIERS",                    "Agricooop Cerbaia"),
        ("SUPPLIERS",                    "G.M.V Agricentre"),
        ("SUPPLIERS",                    "Oliviicoltori Toscani Associati"),
        ("SUPPLIERS",                    "Patrizia Anichini"),
        ("SUPPLIERS",                    "Alderighi"),
        ("SUPPLIERS",                    "Eden Park"),
        ("SUPPLIERS",                    "Pixart"),
        ("SUPPLIERS",                    "Mailboxes Oil"),
        ("SUPPLIERS",                    "Mailboxes Personal"),
        ("SUPPLIERS",                    "Andrea Lepri (Pali) Valentino"),
        ("SUPPLIERS",                    "Torre Bianca"),
        ("SUPPLIERS",                    "Consorzio Dell'Olio Toscano"),
        ("PERSONAL:",                    "Personal Health Insurance"),
        ("PERSONAL:",                    "Medical"),
        ("PERSONAL:",                    "Clothes"),
        ("PERSONAL:",                    "Hair and beauty"),
        ("PERSONAL:",                    "Food"),
        ("PERSONAL:",                    "Entertainment / Dining"),
        ("PERSONAL:",                    "Travel (Hotel / Flights etc)"),
        ("PERSONAL:",                    "Charitable Donations"),
        ("PERSONAL:",                    "Dott. Manfreddi Bufalini"),
        ("PERSONAL:",                    "Other"),
        ("BUSINESS EXP & ENRICHMENT COSTS", "Cooking Class"),
        ("BUSINESS EXP & ENRICHMENT COSTS", "Enrichment Costs"),
        ("BUSINESS EXP & ENRICHMENT COSTS", "Music & Singers"),
        ("BUSINESS EXP & ENRICHMENT COSTS", "Tram Tickets"),
        ("BUSINESS EXP & ENRICHMENT COSTS", "Flights"),
        ("CAPITAL PROJECTS",             "Agriturismo"),
        ("CAPITAL PROJECTS",             "Farm"),
    ]
    for cat, name in EXPENSE_SUPPLIER_SEED:
        try:
            c.execute("INSERT OR IGNORE INTO expense_suppliers (category, name) VALUES (?,?)", (cat, name))
        except Exception:
            pass
    conn.commit()

    # Seed default users if none exist
    user_count = c.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if user_count == 0:
        c.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, display_name) VALUES (?,?,?,?)",
            ("marcus", generate_password_hash("casetta2026"), "admin", "Marcus")
        )
        c.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role, display_name) VALUES (?,?,?,?)",
            ("xenia", generate_password_hash("casetta2026"), "user", "Xenia")
        )

    conn.commit()
    conn.close()
