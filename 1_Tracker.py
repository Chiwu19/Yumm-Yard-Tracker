# 1_Tracker.py
import streamlit as st
import pandas as pd
from datetime import date
import database as db  # Import the new database module

# Initialize the database and its tables
db.init_db()

st.set_page_config(page_title="Sales Tracker", page_icon="📈", layout="wide")

# --- Initialize Session State for Confirmations ---
if 'confirm_remove_sale' not in st.session_state:
    st.session_state.confirm_remove_sale = False
if 'confirm_clear_log' not in st.session_state:
    st.session_state.confirm_clear_log = False
if 'confirm_end_day' not in st.session_state:
    st.session_state.confirm_end_day = False
if 'sale_to_remove' not in st.session_state:
    st.session_state.sale_to_remove = None


def display_sales_section(sales_df, section_title):
    """Displays the sales table from a DataFrame."""
    if sales_df.empty:
        st.info(f"No {section_title.lower()} sales have been logged for today yet.")
    else:
        # Reorder and rename columns for display to match the old format
        display_df = sales_df.rename(columns={
            "timestamp": "Timestamp",
            "item_name": "Item",
            "quantity": "Quantity",
            "price_per_item": "Price per Item (₹)",
            "total_sale": "Total Sale (₹)"
        })
        cols = ["Timestamp", "Item", "Quantity", "Price per Item (₹)", "Total Sale (₹)"]
        st.dataframe(display_df[cols])

# --- App Title & Main Metrics ---
st.title("Yumm Yard Daily Sales Tracker 📈")
st.markdown("---")

# --- Today's Live Sales Summary ---
st.header("Today's Revenue")

# Fetch live sales data directly from the database
todays_offline_df = db.get_sales(status='live', channel='Offline')
todays_online_df = db.get_sales(status='live', channel='Online')

live_offline_total = todays_offline_df["total_sale"].sum()
live_online_total = todays_online_df["total_sale"].sum()
live_grand_total = live_offline_total + live_online_total

col1, col2, col3 = st.columns(3)
col1.metric("Offline Revenue", f"₹{live_offline_total:.2f}")
col2.metric("Online Revenue", f"₹{live_online_total:.2f}")
col3.metric("Grand Total", f"₹{live_grand_total:.2f}")

st.markdown("---")

# --- Tabs for Offline and Online Sales ---
offline_tab, online_tab = st.tabs(["🛒 Offline Sales", "🛵 Online Sales"])

# Load menus once
offline_menu = db.get_menu('Offline')
online_menu = db.get_menu('Online')

with offline_tab:
    st.header("Log a New Offline Sale")
    if not offline_menu:
        st.warning("Please add items to the Offline Menu on the 'Menu Management' page first.")
    else:
        with st.form("offline_sale_form", clear_on_submit=True):
            selected_item = st.selectbox("Select Item", options=list(offline_menu.keys()), key="offline_select")
            quantity = st.number_input("Quantity", min_value=1, value=1, key="offline_qty")
            
            if st.form_submit_button("Log Offline Sale"):
                price = offline_menu[selected_item]
                sale_record = {
                    "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S.%f"), # Added microseconds for uniqueness
                    "Item": selected_item,
                    "Quantity": quantity,
                    "Price per Item (₹)": price,
                    "Total Sale (₹)": price * quantity,
                    "Channel": "Offline"
                }
                db.log_sale(sale_record)
                st.success(f"Logged offline sale of {quantity} x {selected_item}!")
                st.rerun()

    st.header("Today's Offline Sales")
    display_sales_section(todays_offline_df, "Offline")

with online_tab:
    st.header("Log a New Online Sale")
    if not online_menu:
        st.warning("Please add items to the Online Menu on the 'Menu Management' page first.")
    else:
        with st.form("online_sale_form", clear_on_submit=True):
            selected_item = st.selectbox("Select Item", options=list(online_menu.keys()), key="online_select")
            quantity = st.number_input("Quantity", min_value=1, value=1, key="online_qty")
            
            if st.form_submit_button("Log Online Sale"):
                price = online_menu[selected_item]
                sale_record = {
                    "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S.%f"), # Added microseconds for uniqueness
                    "Item": selected_item,
                    "Quantity": quantity,
                    "Price per Item (₹)": price,
                    "Total Sale (₹)": price * quantity,
                    "Channel": "Online"
                }
                db.log_sale(sale_record)
                st.success(f"Logged online sale of {quantity} x {selected_item}!")
                st.rerun()

    st.header("Today's Online Sales")
    display_sales_section(todays_online_df, "Online")

st.markdown("---")

# --- Today's Live Management Section ---
st.header("Manage Today's Sales")
st.markdown("Use these tools to correct mistakes in today's log before saving.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Remove Accidental Sale")
    
    all_todays_sales_df = pd.concat([todays_offline_df, todays_online_df])
    
    if all_todays_sales_df.empty:
        st.info("No sales logged today to remove.")
    else:
        all_todays_sales_df['display'] = all_todays_sales_df.apply(
            lambda row: f"{row['channel'].upper()}: {row['timestamp']} - {row['item_name']}", axis=1
        )
        sale_options = pd.Series(all_todays_sales_df.timestamp.values, index=all_todays_sales_df.display).to_dict()
        
        sale_to_remove_display = st.selectbox("Select a sale to remove", options=list(sale_options.keys()))
        
        if st.button("Remove Selected Sale"):
            st.session_state.confirm_remove_sale = True
            st.session_state.sale_to_remove = sale_options[sale_to_remove_display]

        if st.session_state.confirm_remove_sale:
            st.warning(f"**Are you sure you want to remove this sale?** This action cannot be undone.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, Remove It", type="primary"):
                    db.delete_sale_by_timestamp(st.session_state.sale_to_remove)
                    st.success("Sale removed successfully from today's log.")
                    st.session_state.confirm_remove_sale = False # Reset state
                    st.rerun()
            with c2:
                if st.button("Cancel"):
                    st.session_state.confirm_remove_sale = False # Reset state
                    st.rerun()

with col2:
    st.subheader("Clear Today's Log")
    if st.button("Clear All of Today's Sales"):
        st.session_state.confirm_clear_log = True

    if st.session_state.confirm_clear_log:
        st.warning("**Are you sure you want to clear ALL of today's sales?** This cannot be undone.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Yes, Clear Everything", type="primary"):
                db.clear_live_sales()
                st.success("Cleared all of today's live sales.")
                st.session_state.confirm_clear_log = False # Reset state
                st.rerun()
        with c2:
            if st.button("Cancel##"): # Use "##" to create a unique key for this button
                st.session_state.confirm_clear_log = False # Reset state
                st.rerun()

st.markdown("---")

# --- End of Day Section ---
st.header("End of Day")
st.info("When your workday is finished, save today's sales to your permanent historical record.")

if st.button("End Day & Save Sales", type="primary"):
    st.session_state.confirm_end_day = True

if st.session_state.confirm_end_day:
    st.warning("**Are you sure you want to end the day?** This will move all of today's sales to your permanent history.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Yes, End the Day", type="primary"):
            db.archive_live_sales()
            st.balloons()
            st.success(f"Successfully saved all sales for {date.today().isoformat()} to your permanent record!")
            st.session_state.confirm_end_day = False # Reset state
            st.rerun()
    with c2:
        if st.button("Cancel###"): # Use "###" to create a unique key
            st.session_state.confirm_end_day = False # Reset state
            st.rerun()