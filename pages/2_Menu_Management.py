# pages/2_Menu_Management.py
import streamlit as st
import pandas as pd
from datetime import date
import re
import database as db # Import the new database module

# Initialize the database and its tables
db.init_db()

# --- Initialize Session State for Confirmations ---
if 'confirm_delete_history' not in st.session_state:
    st.session_state.confirm_delete_history = False
if 'date_to_delete' not in st.session_state:
    st.session_state.date_to_delete = None

st.set_page_config(page_title="Menu Management", page_icon="📋", layout="wide")

# --- Menu Management Section ---
st.header("Menu Management")
col = st.container()

# Load menus into a session_state cache so the menu isn't refetched on every rerun.
# It will be loaded from the DB once per app session (or when the app is fully refreshed).
if 'menus' not in st.session_state:
    st.session_state.menus = db.get_menus()
menus = st.session_state.menus
offline_menu = menus.get('Offline', {})

with col:
    st.subheader("Menu")
    with st.form("offline_menu_form", clear_on_submit=True):
        st.write("**Add New Item**")
        item_name = st.text_input("Item Name", key="offline_item_add")
        item_price = st.number_input("Price (₹)", min_value=0.0, format="%.2f", key="offline_price_add")
        if st.form_submit_button("Add to Menu"):
            if item_name:
                # sanitize incoming name to strip markdown emphasis characters so UI rendering stays consistent
                clean_name = item_name.strip()
                m = re.match(r'^\*{1,2}\s*(.*?)\s*\*{1,2}$', clean_name)
                if m:
                    clean_name = m.group(1)
                db.add_menu_item(clean_name, item_price, 'Offline')
                # Update the in-memory menu cache so other pages (or this page) see the change
                st.session_state.menus.setdefault('Offline', {})[clean_name] = item_price
                st.success(f"Added '{clean_name}' to Menu.")
                st.rerun()
    
    if offline_menu:
        st.write("---")
        st.write("**Current Menu**")
        for item, price in offline_menu.items():
            display_name = item.strip('*').strip()
            st.markdown(f"- **{display_name}**: ₹{price:.2f}")
        
        st.write("---")
        st.write("**Remove Item**")
        item_to_remove_offline = st.selectbox("Select item to remove", options=list(offline_menu.keys()), key="offline_item_remove")
        if st.button("Remove from Menu", type="primary"):
            db.delete_menu_item(item_to_remove_offline, 'Offline')
            # Update the in-memory cache
            if 'menus' in st.session_state and 'Offline' in st.session_state.menus:
                st.session_state.menus['Offline'].pop(item_to_remove_offline, None)
            st.success(f"Removed '{item_to_remove_offline}' from Menu.")
            st.rerun()
    else:
        st.info("No items in the menu yet.")

# Note: online menu UI removed; the page now focuses on the single Menu (in-store)

st.markdown("---")

# --- Historical Data Management Section ---
st.header("Historical Data Management 💾")
st.markdown("View and delete permanent sales records for any given day.")

saved_dates = db.get_archived_dates()
# Also fetch archived expense dates for management UI (if expenses exist)
try:
    saved_expense_dates = db.get_archived_dates()  # reuse same function if expenses share dates
except Exception:
    saved_expense_dates = []

if not saved_dates:
    st.info("No historical sales have been saved yet.")
else:
    date_to_view = st.selectbox("Select a day to view its sales record:", options=saved_dates)
    
    if date_to_view:
        st.subheader(f"Sales Record for {date.fromisoformat(date_to_view).strftime('%B %d, %Y')}")
        
        day_sales_df = db.get_sales(status='archived', start_date=date.fromisoformat(date_to_view), end_date=date.fromisoformat(date_to_view))
        
        offline_sales_df = day_sales_df[day_sales_df['channel'] == 'Offline']
        online_sales_df = day_sales_df[day_sales_df['channel'] == 'Online']
        
        st.write("**Sales**")
        if not day_sales_df.empty:
            st.dataframe(day_sales_df)
        else:
            st.write("No sales were recorded for this day.")
            
        # Also show archived expenses for the day (if any)
        try:
            expenses_df = db.get_expenses(status='archived', expense_date=date_to_view)
            st.write("**Expenses**")
            if not expenses_df.empty:
                st.dataframe(expenses_df)
            else:
                st.write("No expenses were recorded for this day.")
        except Exception:
            # If expenses table doesn't exist, silently continue
            pass

        # --- Daily totals (per-channel + grand total) (placed below the tables) ---
        # Compute totals and include expenses to compute profit
        total_sales = day_sales_df["total_sale"].sum() if (not day_sales_df.empty and "total_sale" in day_sales_df.columns) else 0.0
        try:
            expenses_df = db.get_expenses(status='archived', expense_date=date_to_view)
            total_expenses = expenses_df['amount'].sum() if (not expenses_df.empty and 'amount' in expenses_df.columns) else 0.0
        except Exception:
            total_expenses = 0.0
        grand_total = total_sales
        profit = grand_total - total_expenses

        tcol1, tcol2, tcol3 = st.columns([1,1,1])
        tcol1.metric("Revenue", f"₹{grand_total:.2f}")
        tcol2.metric("Expenses", f"₹{total_expenses:.2f}")
        tcol3.metric("Profit", f"₹{profit:.2f}")

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
                    # Also delete archived expenses for the date if present
                    try:
                        db.delete_archived_expenses_by_date(st.session_state.date_to_delete)
                    except Exception:
                        pass
                    st.success(f"Successfully deleted all data for {st.session_state.date_to_delete}.")
                    st.session_state.confirm_delete_history = False # Reset state
                    st.rerun()
            with c2:
                if st.button("Cancel"):
                    st.session_state.confirm_delete_history = False # Reset state
                    st.rerun()