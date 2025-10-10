import pandas as pd
from datetime import date
import streamlit as st
import libsql_client

import nest_asyncio
nest_asyncio.apply()

def get_db_connection():
    """
    Establishes a new connection to the Turso database.
    """
    url = st.secrets["TURSO_DATABASE_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]
    return libsql_client.create_client(url=url, auth_token=auth_token)

def init_db():
    """Initializes the database tables if they don't exist."""
    conn = get_db_connection()
    conn.batch([
        """
        CREATE TABLE IF NOT EXISTS menus (
            item_name TEXT NOT NULL,
            channel TEXT NOT NULL,
            price REAL NOT NULL,
            PRIMARY KEY (item_name, channel)
        )
        """,
        """
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
        """
    ])
    conn.close() # <-- ADDED BACK

# --- Menu Functions ---
def get_menu(channel):
    """Retrieves a specific menu (offline or online) as a dictionary."""
    conn = get_db_connection()
    rs = conn.execute("SELECT item_name, price FROM menus WHERE channel = ? ORDER BY item_name", (channel,))
    menu = {row["item_name"]: row["price"] for row in rs.rows}
    conn.close() # <-- ADDED BACK
    return menu

def add_menu_item(item_name, price, channel):
    """Adds or updates an item in a menu."""
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO menus (item_name, price, channel) VALUES (?, ?, ?)",
                   (item_name, price, channel))
    conn.close() # <-- ADDED BACK

def delete_menu_item(item_name, channel):
    """Deletes an item from a menu."""
    conn = get_db_connection()
    conn.execute("DELETE FROM menus WHERE item_name = ? AND channel = ?", (item_name, channel))
    conn.close() # <-- ADDED BACK

# --- Sales Functions ---
def log_sale(sale_dict):
    """Logs a single sale transaction to the database with 'live' status."""
    conn = get_db_connection()
    conn.execute(
        """
        INSERT INTO sales (timestamp, item_name, quantity, price_per_item, total_sale, channel, sale_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'live')
        """,
        (
            sale_dict["Timestamp"],
            sale_dict["Item"],
            sale_dict["Quantity"],
            sale_dict["Price per Item (₹)"],
            sale_dict["Total Sale (₹)"],
            sale_dict["Channel"],
            date.today().isoformat()
        )
    )
    conn.close() # <-- ADDED BACK

def get_sales(status='live', channel=None, start_date=None, end_date=None):
    """Fetches sales data as a Pandas DataFrame, with optional filters."""
    conn = get_db_connection()
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

    rs = conn.execute(query, params)
    columns = [col for col in rs.columns]
    df = pd.DataFrame(rs.rows, columns=columns)
    conn.close() # <-- ADDED BACK
    return df

def get_live_revenue(channel):
    """Calculates the sum of 'live' sales for a specific channel directly in the DB."""
    conn = get_db_connection()
    rs = conn.execute(
        "SELECT SUM(total_sale) FROM sales WHERE status = 'live' AND channel = ?",
        (channel,)
    )
    total = rs.rows[0][0]
    result = total if total is not None else 0.0
    conn.close() # <-- ADDED BACK
    return result

def delete_sale_by_timestamp(timestamp):
    """Deletes a single sale using its unique timestamp."""
    conn = get_db_connection()
    conn.execute("DELETE FROM sales WHERE timestamp = ?", (timestamp,))
    conn.close() # <-- ADDED BACK

def clear_live_sales():
    """Deletes all sales with 'live' status."""
    conn = get_db_connection()
    conn.execute("DELETE FROM sales WHERE status = 'live'")
    conn.close() # <-- ADDED BACK

def archive_live_sales():
    """Changes the status of all 'live' sales to 'archived' (End of Day action)."""
    conn = get_db_connection()
    conn.execute("UPDATE sales SET status = 'archived' WHERE status = 'live'")
    conn.close() # <-- ADDED BACK

def get_archived_dates():
    """Returns a sorted list of unique dates for which there are archived sales."""
    conn = get_db_connection()
    rs = conn.execute("SELECT DISTINCT sale_date FROM sales WHERE status = 'archived' ORDER BY sale_date DESC")
    dates = [row["sale_date"] for row in rs.rows]
    conn.close() # <-- ADDED BACK
    return dates

def delete_archived_sales_by_date(date_str):
    """Permanently deletes all archived sales for a specific date."""
    conn = get_db_connection()
    conn.execute("DELETE FROM sales WHERE status = 'archived' AND sale_date = ?", (date_str,))
    conn.close() # <-- ADDED BACK