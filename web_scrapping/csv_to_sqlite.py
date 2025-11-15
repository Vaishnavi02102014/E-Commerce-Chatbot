import sqlite3
import pandas as pd
from pathlib import Path

# ---------- CONFIG ----------
CSV_PATH = Path(__file__).parent / "flipkart_product_data.csv"   # path to your CSV
DB_PATH = Path(__file__).parent / "products.db"        # sqlite file to create/use
TABLE_NAME = "product"
# ----------------------------

# Read CSV using pandas# find_and_check_dbs.py
import sqlite3
from pathlib import Path
import pandas as pd

project_root = Path.cwd()  # or set this to your project folder explicitly

# find all files named products.db under the project
db_files = list(project_root.rglob("products.db"))

if not db_files:
    print("No products.db found under", project_root)
else:
    print("Found the following products.db files:")
    for p in db_files:
        print("-", p)

    print("\nChecking each DB for tables and whether 'product' exists...\n")
    for p in db_files:
        print("DB:", p)
        try:
            with sqlite3.connect(p) as conn:
                tables = pd.read_sql_query(
                    "SELECT name FROM sqlite_master WHERE type='table';", conn
                )
            if tables.empty:
                print("  -> No tables found in this DB.")
            else:
                print("  -> Tables:", tables['name'].tolist())
                # If product exists, show a sample
                if "product" in tables['name'].tolist():
                    with sqlite3.connect(p) as conn:
                        df = pd.read_sql_query("SELECT COUNT(*) AS cnt FROM product;", conn)
                        cnt = int(df.loc[0, 'cnt'])
                        print(f"  -> 'product' table exists with {cnt} rows. Sample rows:")
                        with sqlite3.connect(p) as conn:
                            sample = pd.read_sql_query("SELECT * FROM product LIMIT 5;", conn)
                        print(sample)
        except Exception as e:
            print("  -> Error opening DB:", e)
        print("-" * 60)

df = pd.read_csv(CSV_PATH)

# Ensure expected columns exist
expected_cols = ['product_link', 'title', 'brand', 'price', 'discount', 'avg_rating', 'total_ratings']
missing = [c for c in expected_cols if c not in df.columns]
if missing:
    raise ValueError(f"CSV is missing columns: {missing}")

# Coerce types safely
# - price -> numeric (integers). Use coerce to convert invalid to NaN -> will become NULL
df['price'] = pd.to_numeric(df['price'], errors='coerce').astype('Float64')  # keep as pandas nullable to detect NaN
# - discount, avg_rating, total_ratings -> floats
df['discount'] = pd.to_numeric(df['discount'], errors='coerce')
df['avg_rating'] = pd.to_numeric(df['avg_rating'], errors='coerce')
df['total_ratings'] = pd.to_numeric(df['total_ratings'], errors='coerce')

# If you prefer price to be integer (and drop decimals) convert now:
# df['price'] = df['price'].round(0).astype('Int64')  # pandas nullable integer type
# But we'll insert as INTEGER (NULL allowed). We'll convert NaN -> None below.

# Replace pandas NA/NaN with None for sqlite insertion
df = df.where(pd.notnull(df), None)

# Create/connect to SQLite DB
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Create table if not exists (adjust schema as needed)
create_table_sql = f"""
CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_link TEXT UNIQUE,
    title TEXT,
    brand TEXT,
    price INTEGER,
    discount REAL,
    avg_rating REAL,
    total_ratings REAL
);
"""
cur.execute(create_table_sql)
conn.commit()

# Prepare insert statement. Use REPLACE INTO or INSERT OR IGNORE if you want to skip or overwrite duplicates:
insert_sql = f"""
INSERT OR REPLACE INTO {TABLE_NAME} (
    product_link, title, brand, price, discount, avg_rating, total_ratings
) VALUES (?, ?, ?, ?, ?, ?, ?);
"""

# Convert each row to a tuple in the right order and types suitable for sqlite
to_insert = []
for _, row in df.iterrows():
    # Convert price to integer if not None; if None leave as None
    price_val = None
    if row['price'] is not None:
        # If you used Float64 and want integer:
        try:
            price_val = int(row['price'])
        except Exception:
            price_val = None

    discount_val = None if row['discount'] is None else float(row['discount'])
    avg_rating_val = None if row['avg_rating'] is None else float(row['avg_rating'])
    total_ratings_val = None if row['total_ratings'] is None else float(row['total_ratings'])

    to_insert.append((
        row['product_link'],
        row['title'],
        row['brand'],
        price_val,
        discount_val,
        avg_rating_val,
        total_ratings_val
    ))

# Bulk insert
try:
    cur.executemany(insert_sql, to_insert)
    conn.commit()
    print(f"Inserted/updated {cur.rowcount} rows into '{TABLE_NAME}'.")
except Exception as e:
    conn.rollback()
    raise

# Close connection
conn.close()
