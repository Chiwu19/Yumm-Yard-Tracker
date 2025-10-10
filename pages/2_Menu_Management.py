# pages/2_Menu_Management.py
import streamlit as st
import pandas as pd
from datetime import date
import database as db # Import the new database module

# Initialize the database and its tables
db.init_db()

# --- Initialize Session State for Confirmations ---
if 'confirm_delete_history' not in st.session_state:
    st.session_state.confirm_delete_history = False
if 'date_to_delete' not in st.session_state:
    st.session_state.date_to_delete = None

st.set_page_config(page_title="Menu Management", page_icon="📋", layout="wide")

st.title("Menu & Data Management 📋")
st.markdown("Add, view, and remove menu items. You can also manage your permanent historical sales records here.")

# --- Menu Management Section ---
st.header("Menu Management")
col1, col2 = st.columns(2)

# Load menus into a session_state cache so the menu isn't refetched on every rerun.
# It will be loaded from the DB once per app session (or when the app is fully refreshed).
if 'menus' not in st.session_state:
    st.session_state.menus = db.get_menus()
menus = st.session_state.menus
offline_menu = menus.get('Offline', {})
online_menu = menus.get('Online', {})

with col1:
    st.subheader("Offline Menu (In-Store)")
    with st.form("offline_menu_form", clear_on_submit=True):
        st.write("**Add New Item**")
        item_name = st.text_input("Item Name", key="offline_item_add")
        item_price = st.number_input("Price (₹)", min_value=0.0, format="%.2f", key="offline_price_add")
        if st.form_submit_button("Add to Offline Menu"):
            if item_name:
                db.add_menu_item(item_name, item_price, 'Offline')
                # Update the in-memory menu cache so other pages (or this page) see the change
                st.session_state.menus.setdefault('Offline', {})[item_name] = item_price
                st.success(f"Added '{item_name}' to Offline Menu.")
                st.rerun()
    
    if offline_menu:
        st.write("---")
        st.write("**Current Offline Menu**")
        for item, price in offline_menu.items():
            st.write(f"- {item}: ₹{price:.2f}")
        
        st.write("---")
        st.write("**Remove Item**")
        item_to_remove_offline = st.selectbox("Select item to remove", options=list(offline_menu.keys()), key="offline_item_remove")
        if st.button("Remove from Offline Menu", type="primary"):
            db.delete_menu_item(item_to_remove_offline, 'Offline')
            # Update the in-memory cache
            if 'menus' in st.session_state and 'Offline' in st.session_state.menus:
                st.session_state.menus['Offline'].pop(item_to_remove_offline, None)
            st.success(f"Removed '{item_to_remove_offline}' from Offline Menu.")
            st.rerun()
    else:
        st.info("No items in the offline menu yet.")

with col2:
    st.subheader("Online Menu (Zomato/Swiggy)")
    with st.form("online_menu_form", clear_on_submit=True):
        st.write("**Add New Item**")
        item_name = st.text_input("Item Name", key="online_item_add")
        item_price = st.number_input("Price (₹)", min_value=0.0, format="%.2f", key="online_price_add")
        if st.form_submit_button("Add to Online Menu"):
            if item_name:
                db.add_menu_item(item_name, item_price, 'Online')
                # Update the in-memory menu cache
                st.session_state.menus.setdefault('Online', {})[item_name] = item_price
                st.success(f"Added '{item_name}' to Online Menu.")
                st.rerun()

    if online_menu:
        st.write("---")
        st.write("**Current Online Menu**")
        for item, price in online_menu.items():
            st.write(f"- {item}: ₹{price:.2f}")

        st.write("---")
        st.write("**Remove Item**")
        item_to_remove_online = st.selectbox("Select item to remove", options=list(online_menu.keys()), key="online_item_remove")
        if st.button("Remove from Online Menu", type="primary"):
            db.delete_menu_item(item_to_remove_online, 'Online')
            # Update the in-memory cache
            if 'menus' in st.session_state and 'Online' in st.session_state.menus:
                st.session_state.menus['Online'].pop(item_to_remove_online, None)
            st.success(f"Removed '{item_to_remove_online}' from Online Menu.")
            st.rerun()
    else:
        st.info("No items in the online menu yet.")

st.markdown("---")

# --- Historical Data Management Section ---
st.header("Historical Data Management 💾")
st.markdown("View and delete permanent sales records for any given day.")

saved_dates = db.get_archived_dates()

if not saved_dates:
    st.info("No historical sales have been saved yet.")
else:
    date_to_view = st.selectbox("Select a day to view its sales record:", options=saved_dates)
    
    if date_to_view:
        st.subheader(f"Sales Record for {date.fromisoformat(date_to_view).strftime('%B %d, %Y')}")
        
        day_sales_df = db.get_sales(status='archived', start_date=date.fromisoformat(date_to_view), end_date=date.fromisoformat(date_to_view))
        
        offline_sales_df = day_sales_df[day_sales_df['channel'] == 'Offline']
        online_sales_df = day_sales_df[day_sales_df['channel'] == 'Online']
        
        st.write("**Offline Sales**")
        if not offline_sales_df.empty:
            st.dataframe(offline_sales_df)
        else:
            st.write("No offline sales were recorded for this day.")
            
        st.write("**Online Sales**")
        if not online_sales_df.empty:
            st.dataframe(online_sales_df)
        else:
            st.write("No online sales were recorded for this day.")

        st.write("---")
        st.subheader(f"Danger Zone")
        if st.button(f"Permanently Delete All Sales for {date_to_view}", type="primary"):
            st.session_state.confirm_delete_history = True
            st.session_state.date_to_delete = date_to_view
        
        if st.session_state.confirm_delete_history and st.session_state.date_to_delete == date_to_view:
            st.warning(f"**Are you sure you want to delete all records for {st.session_state.date_to_delete}?** This action cannot be undone.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Yes, Permanently Delete", type="primary"):
                    db.delete_archived_sales_by_date(st.session_state.date_to_delete)
                    st.success(f"Successfully deleted all data for {st.session_state.date_to_delete}.")
                    st.session_state.confirm_delete_history = False # Reset state
                    st.rerun()
            with c2:
                if st.button("Cancel"):
                    st.session_state.confirm_delete_history = False # Reset state
                    st.rerun()