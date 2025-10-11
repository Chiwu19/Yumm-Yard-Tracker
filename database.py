# database.py
import sqlite3
import pandas as pd
from datetime import date
import streamlit as st
import libsql # <-- IMPORT THE NEW LIBRARY

_conn = None

def connect_db():
    """
    Returns a shared database connection (lazy-initialized).
    Keeps a single global connection to avoid reinitialization.
    """
    global _conn
    if _conn is not None:
        return _conn

    # Get credentials from st.secrets
    url = st.secrets["TURSO_DATABASE_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]

    # Use libsql.connect instead of sqlite3.connect
    _conn = libsql.connect(database=url, auth_token=auth_token)
    return _conn

# ALL OF THE FUNCTIONS BELOW THIS LINE REMAIN EXACTLY THE SAME!
# NO MORE CHANGES ARE NEEDED.

def init_db():
    """Initializes the database tables if they don't exist."""
    # This now connects to Turso!
    conn = connect_db()
    cursor = conn.cursor()
    
    # Menu Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS menus (
        item_name TEXT NOT NULL,
        channel TEXT NOT NULL,
        price REAL NOT NULL,
        PRIMARY KEY (item_name, channel)
    )
    """)
    
    # Sales Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        timestamp TEXT PRIMARY KEY,
        item_name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price_per_item REAL NOT NULL,
        total_sale REAL NOT NULL,
        channel TEXT NOT NULL,
        sale_date TEXT NOT NULL,
        status TEXT NOT NULL 
    )
    """)
    conn.commit()
    # shared global connection - do not close here

# --- Menu Functions ---
def get_menu(channel):
    """Retrieves a specific menu (offline or online) as a dictionary."""
    conn = connect_db()
    query = "SELECT item_name, price FROM menus WHERE channel = ? ORDER BY item_name"
    df = pd.read_sql_query(query, conn, params=(channel,))
    # shared global connection - do not close here
    return dict(zip(df.item_name, df.price))

def get_menus():
    """Retrieves both Offline and Online menus in a single query.
    Returns a dict: {'Offline': {item: price, ...}, 'Online': {...}}
    """
    conn = connect_db()
    query = "SELECT item_name, price, channel FROM menus WHERE channel IN ('Offline','Online') ORDER BY channel, item_name"
    df = pd.read_sql_query(query, conn)
    menus = {}
    if not df.empty:
        # Build dictionary grouped by channel
        for _, row in df.iterrows():
            ch = row['channel']
            item = row['item_name']
            price = row['price']
            if ch not in menus:
                menus[ch] = {}
            menus[ch][item] = price
    # Ensure keys exist even if empty
    menus.setdefault('Offline', {})
    menus.setdefault('Online', {})
    return menus

def get_top_items(channel, limit=5, metric='orders'):
    """
    Return a list of the top `limit` items for a given channel.

    Metrics:
    - 'orders' (default): rank by number of times an item was ordered (COUNT of sales rows).
      This reflects "most reordered / best sellers" — how many separate sale entries included the item.
    - 'quantity': rank by total quantity sold (SUM of quantity).

    Returns an empty list when there is no sales data.
    """
    conn = connect_db()
    metric = (metric or 'orders').lower()

    if metric == 'quantity':
        # Rank by total quantity sold
        query = """
        SELECT item_name, SUM(quantity) as score
        FROM sales
        WHERE channel = ?
        GROUP BY item_name
        ORDER BY score DESC
        LIMIT ?
        """
        params = (channel, limit)
    else:
        # Default: rank by number of orders (count of rows for the item)
        query = """
        SELECT item_name, COUNT(*) as score
        FROM sales
        WHERE channel = ?
        GROUP BY item_name
        ORDER BY score DESC
        LIMIT ?
        """
        params = (channel, limit)

    try:
        df = pd.read_sql_query(query, conn, params=params)
    except Exception:
        # Fallback when parametrized LIMIT isn't supported by the driver
        if metric == 'quantity':
            df = pd.read_sql_query("""
            SELECT item_name, SUM(quantity) as score
            FROM sales
            WHERE channel = ?
            GROUP BY item_name
            ORDER BY score DESC
            """, conn, params=(channel,))
        else:
            df = pd.read_sql_query("""
            SELECT item_name, COUNT(*) as score
            FROM sales
            WHERE channel = ?
            GROUP BY item_name
            ORDER BY score DESC
            """, conn, params=(channel,))
        df = df.head(limit)

    # shared global connection - do not close here
    if df.empty:
        return []
    return df['item_name'].tolist()

def add_menu_item(item_name, price, channel):
    """Adds or updates an item in a menu."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO menus (item_name, price, channel) VALUES (?, ?, ?)", 
                   (item_name, price, channel))
    conn.commit()
    # shared global connection - do not close here

def delete_menu_item(item_name, channel):
    """Deletes an item from a menu."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menus WHERE item_name = ? AND channel = ?", (item_name, channel))
    conn.commit()
    # shared global connection - do not close here

# --- Sales Functions ---
def log_sale(sale_dict):
    """Logs a single sale transaction to the database with 'live' status."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO sales (timestamp, item_name, quantity, price_per_item, total_sale, channel, sale_date, status)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'live')
    """, (
        sale_dict["Timestamp"],
        sale_dict["Item"],
        sale_dict["Quantity"],
        sale_dict["Price per Item (₹)"],
        sale_dict["Total Sale (₹)"],
        sale_dict["Channel"],
        date.today().isoformat()
    ))
    conn.commit()
    # shared global connection - do not close here

def get_sales(status='live', channel=None, start_date=None, end_date=None):
    """Fetches sales data as a Pandas DataFrame, with optional filters."""
    conn = connect_db()
    query = "SELECT * FROM sales WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    if channel:
        query += " AND channel = ?"
        params.append(channel)
    if start_date:
        query += " AND sale_date >= ?"
        params.append(start_date.isoformat())
    if end_date:
        query += " AND sale_date <= ?"
        params.append(end_date.isoformat())
        
    df = pd.read_sql_query(query, conn, params=params)
    # shared global connection - do not close here
    return df

def delete_sale_by_timestamp(timestamp):
    """Deletes a single sale using its unique timestamp."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE timestamp = ?", (timestamp,))
    conn.commit()
    # shared global connection - do not close here
    
def clear_live_sales():
    """Deletes all sales with 'live' status."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE status = 'live'")
    conn.commit()
    # shared global connection - do not close here

def archive_live_sales():
    """Changes the status of all 'live' sales to 'archived' (End of Day action)."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sales SET status = 'archived' WHERE status = 'live'")
    conn.commit()
    # shared global connection - do not close here
    
def get_archived_dates():
    """Returns a sorted list of unique dates for which there are archived sales."""
    conn = connect_db()
    query = "SELECT DISTINCT sale_date FROM sales WHERE status = 'archived' ORDER BY sale_date DESC"
    df = pd.read_sql_query(query, conn)
    # shared global connection - do not close here
    return df['sale_date'].tolist()

def delete_archived_sales_by_date(date_str):
    """Permanently deletes all archived sales for a specific date."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE status = 'archived' AND sale_date = ?", (date_str,))
    conn.commit()
    # shared global connection - do not close here

def close_db():
    """Close the shared global database connection (if any)."""
    global _conn
    if _conn is not None:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None