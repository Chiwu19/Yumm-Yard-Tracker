# database.py
import sqlite3
import pandas as pd
from datetime import date
import streamlit as st
import libsql # <-- IMPORT THE NEW LIBRARY

def connect_db():
    """
    Establishes a connection to the Turso SQLite database.
    It reads credentials from Streamlit secrets.
    """
    # Get credentials from st.secrets
    url = st.secrets["TURSO_DATABASE_URL"]
    auth_token = st.secrets["TURSO_AUTH_TOKEN"]

    # Use libsql.connect instead of sqlite3.connect
    return libsql.connect(database=url, auth_token=auth_token)

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
    conn.close()

# --- Menu Functions ---
def get_menu(channel):
    """Retrieves a specific menu (offline or online) as a dictionary."""
    conn = connect_db()
    query = "SELECT item_name, price FROM menus WHERE channel = ? ORDER BY item_name"
    df = pd.read_sql_query(query, conn, params=(channel,))
    conn.close()
    return dict(zip(df.item_name, df.price))

def add_menu_item(item_name, price, channel):
    """Adds or updates an item in a menu."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO menus (item_name, price, channel) VALUES (?, ?, ?)", 
                   (item_name, price, channel))
    conn.commit()
    conn.close()

def delete_menu_item(item_name, channel):
    """Deletes an item from a menu."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM menus WHERE item_name = ? AND channel = ?", (item_name, channel))
    conn.commit()
    conn.close()

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
    conn.close()

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
    conn.close()
    return df

def delete_sale_by_timestamp(timestamp):
    """Deletes a single sale using its unique timestamp."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE timestamp = ?", (timestamp,))
    conn.commit()
    conn.close()
    
def clear_live_sales():
    """Deletes all sales with 'live' status."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE status = 'live'")
    conn.commit()
    conn.close()

def archive_live_sales():
    """Changes the status of all 'live' sales to 'archived' (End of Day action)."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE sales SET status = 'archived' WHERE status = 'live'")
    conn.commit()
    conn.close()
    
def get_archived_dates():
    """Returns a sorted list of unique dates for which there are archived sales."""
    conn = connect_db()
    query = "SELECT DISTINCT sale_date FROM sales WHERE status = 'archived' ORDER BY sale_date DESC"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df['sale_date'].tolist()

def delete_archived_sales_by_date(date_str):
    """Permanently deletes all archived sales for a specific date."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sales WHERE status = 'archived' AND sale_date = ?", (date_str,))
    conn.commit()
    conn.close()