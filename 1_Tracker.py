# 1_Tracker.py
import streamlit as st
import pandas as pd
from datetime import date
import re
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
# Expense removal confirmation state
if 'confirm_remove_expense' not in st.session_state:
    st.session_state.confirm_remove_expense = False
if 'expense_to_remove' not in st.session_state:
    st.session_state.expense_to_remove = None
# Temporary in-memory orders for the POS-style UI (only channel now)
if 'current_order_offline' not in st.session_state:
    st.session_state.current_order_offline = {}


def display_sales_section(sales_df, section_title):
    """Displays the sales table from a DataFrame."""
    if sales_df.empty:
        # If a specific section title was provided, use it; otherwise show a generic message.
        if section_title and section_title.strip():
            st.info(f"No {section_title.lower()} sales have been logged for today yet.")
        else:
            st.info("No sales have been logged for today yet.")
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

# Use cached live sales in session_state so we don't refetch the entire table on every small action.
# The first run will load from the DB; subsequent interactions will update the in-memory copy.
if 'live_sales_df' not in st.session_state:
    st.session_state.live_sales_df = db.get_sales(status='live')
live_sales_df = st.session_state.live_sales_df

# Split into channels in-memory to avoid multiple DB queries (only Offline now)
todays_offline_df = live_sales_df[live_sales_df['channel'] == 'Offline'].copy()

# --- Sales section (tabs removed) ---
offline_tab = st.container()

# Cache menus in session_state so they are NOT refetched on every rerun.
# This keeps the menu stable across interactions until the user does a full refresh.
if 'menus' not in st.session_state:
    st.session_state.menus = db.get_menus()
menus = st.session_state.menus
offline_menu = menus.get('Offline', {})

with offline_tab:
    st.header("Log a New Sale")
    if not offline_menu:
        st.warning("Please add items to the Menu on the 'Menu Management' page first.")
    else:
        # Layout: left = menu with + / x controls, right = current order summary
        menu_col, order_col = st.columns([2, 1])
        with menu_col:
            st.subheader("Menu")
            # Add search box to quickly filter long offline menus
            search_offline = st.text_input("Search items...", key="offline_menu_search")
            # Build filtered view (case-insensitive substring match)
            if search_offline:
                filtered_offline_menu = {
                    item: price for item, price in offline_menu.items()
                    if search_offline.lower() in item.lower()
                }
            else:
                # By default show only the top 5 most common items (by historical sales)
                try:
                    top_items = db.get_top_items('Offline', 5)
                except Exception:
                    top_items = []
                if top_items:
                    filtered_offline_menu = {item: offline_menu[item] for item in top_items if item in offline_menu}
                else:
                    # No sales history yet — show first five items to avoid an empty list
                    first_items = list(offline_menu.items())[:5]
                    filtered_offline_menu = dict(first_items)
                st.info("Showing top 5 items by default. Use the search box to find other items.")
            if not filtered_offline_menu:
                st.info("No menu items match your search.")
            else:
                for item, price in filtered_offline_menu.items():
                    # Create a single-row layout for each menu item with small action buttons
                    a, b, c, d = st.columns([4, 1, 1, 1])
                    display_name = re.sub(r'^\*{1,2}\s*(.*?)\s*\*{1,2}$', r'\1', item).strip()
                    a.markdown(f"**{display_name}**")
                    b.write(f"₹{price:.2f}")
                    # + button: increment quantity in the in-memory order
                    if c.button("＋", key=f"offline_plus_{item}"):
                        st.session_state.current_order_offline[item] = st.session_state.current_order_offline.get(item, 0) + 1
                        st.rerun()
                    # × button: remove item from the in-memory order entirely
                    if d.button("×", key=f"offline_remove_{item}"):
                        if item in st.session_state.current_order_offline:
                            st.session_state.current_order_offline.pop(item, None)
                            st.rerun()
        with order_col:
            st.subheader("Order Summary")
            order = st.session_state.current_order_offline
            if not order:
                st.write("No items in the current order.")
            else:
                subtotal = 0.0
                for itm, qty in list(order.items()):
                    price = offline_menu.get(itm, 0.0)
                    line_total = price * qty
                    subtotal += line_total
                    r1, r2, r3 = st.columns([3, 1, 1])
                    r1.write(f"{itm} (x{qty})")
                    r2.write(f"₹{line_total:.2f}")
                    # remove item entirely from summary (show only × icon here)
                    if r3.button("×", key=f"offline_remove_summary_{itm}"):
                        if itm in st.session_state.current_order_offline:
                            st.session_state.current_order_offline.pop(itm, None)
                        st.rerun()
                st.markdown("---")
                st.write(f"**SUBTOTAL:** ₹{subtotal:.2f}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("Clear Order", key="offline_clear_order"):
                        st.session_state.current_order_offline = {}
                        st.rerun()
                with c2:
                    if st.button("Log Order", key="offline_log_order", type="primary"):
                        # Persist each line as its own sale row
                        for itm, qty in list(order.items()):
                            price = offline_menu.get(itm, 0.0)
                            sale_record = {
                                "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
                                "Item": itm,
                                "Quantity": qty,
                                "Price per Item (₹)": price,
                                "Total Sale (₹)": price * qty,
                                "Channel": "Offline"
                            }
                            db.log_sale(sale_record)
                            new_row = {
                                "timestamp": sale_record["Timestamp"],
                                "item_name": sale_record["Item"],
                                "quantity": sale_record["Quantity"],
                                "price_per_item": sale_record["Price per Item (₹)"],
                                "total_sale": sale_record["Total Sale (₹)"],
                                "channel": sale_record["Channel"],
                                "sale_date": date.today().isoformat(),
                                "status": "live"
                            }
                            if 'live_sales_df' in st.session_state:
                                st.session_state.live_sales_df = pd.concat(
                                    [st.session_state.live_sales_df, pd.DataFrame([new_row])],
                                    ignore_index=True
                                )
                            else:
                                st.session_state.live_sales_df = pd.DataFrame([new_row])
                        st.success("Logged current order to today's sales.")
                        st.session_state.current_order_offline = {}
                        st.rerun()

    # --- Sales display ---
    st.header("Today's Sales")
    display_sales_section(todays_offline_df, "")

    # --- Expenses: manual entry and today's expenses display ---
    st.subheader("Expenses")
    with st.form("add_expense_form", clear_on_submit=True):
        expense_amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f", key="expense_amount")
        expense_desc = st.text_input("Description", key="expense_desc")
        if st.form_submit_button("Add Expense"):
            if expense_amount > 0:
                db.add_expense(expense_amount, expense_desc)
                st.success("Expense added for today.")
                st.rerun()

    # Show today's expenses (live)
    today_str = date.today().isoformat()
    try:
        expenses_df = db.get_expenses(status='live', expense_date=today_str)
    except Exception:
        expenses_df = None

    st.write("**Today's Expenses**")
    if expenses_df is None or expenses_df.empty:
        st.write("No expenses logged for today.")
    else:
        # Show only relevant columns for clarity
        display_expenses = expenses_df[['id','expense_date', 'amount', 'description']].rename(
            columns={'expense_date': 'Date', 'amount': 'Amount (₹)', 'description': 'Description'}
        )
        st.dataframe(display_expenses, use_container_width=True)

        # --- Remove Accidental Expense ---
        st.subheader("Remove Accidental Expense")
        try:
            if expenses_df is None or expenses_df.empty:
                st.write("No expenses to remove.")
            else:
                # Build a display mapping of "id: ₹amount - description"
                expenses_df_sorted = expenses_df.copy()
                expenses_df_sorted['display'] = expenses_df_sorted.apply(
                    lambda r: f"{int(r['id'])}: ₹{r['amount']:.2f} - {str(r.get('description','')).strip()}",
                    axis=1
                )
                exp_options = pd.Series(expenses_df_sorted.id.values, index=expenses_df_sorted.display).to_dict()
                exp_to_remove_display = st.selectbox("Select an expense to remove", options=list(exp_options.keys()), key="select_expense_to_remove")
                if st.button("Remove Selected Expense", key="remove_selected_expense"):
                    st.session_state.confirm_remove_expense = True
                    st.session_state.expense_to_remove = exp_options[exp_to_remove_display]

                if st.session_state.confirm_remove_expense and st.session_state.expense_to_remove is not None:
                    st.warning("**Are you sure you want to remove this expense?** This action cannot be undone.")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Yes, Remove Expense", key="confirm_remove_expense_yes", type="primary"):
                            try:
                                db.delete_expense_by_id(st.session_state.expense_to_remove)
                            except Exception:
                                pass
                            st.success("Expense removed successfully.")
                            st.session_state.confirm_remove_expense = False
                            st.session_state.expense_to_remove = None
                            st.rerun()
                    with c2:
                        if st.button("Cancel", key="confirm_remove_expense_cancel"):
                            st.session_state.confirm_remove_expense = False
                            st.session_state.expense_to_remove = None
                            st.rerun()
        except Exception:
            # If anything goes wrong building the remove UI, fail silently to not break Tracker.
            pass

# Online sales support removed — only Offline channel is supported in Tracker now.
# (The Online tab and its UI were intentionally removed.)

st.markdown("---")

# --- Today's Live Management Section ---
st.header("Manage Today's Sales")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Remove Accidental Sale")
    
    all_todays_sales_df = todays_offline_df
    
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
                    # Update cached DF if present
                    if 'live_sales_df' in st.session_state:
                        st.session_state.live_sales_df = st.session_state.live_sales_df[
                            st.session_state.live_sales_df['timestamp'] != st.session_state.sale_to_remove
                        ].reset_index(drop=True)
                    st.success("Sale removed successfully from today's log.")
                    st.session_state.confirm_remove_sale = False
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
                # Clear the local cache (preserve columns if possible)
                if 'live_sales_df' in st.session_state:
                    st.session_state.live_sales_df = st.session_state.live_sales_df.iloc[0:0].copy()
                st.success("Cleared all of today's live sales.")
                st.session_state.confirm_clear_log = False
                st.rerun()
        with c2:
            if st.button("Cancel##"): # Use "##" to create a unique key for this button
                st.session_state.confirm_clear_log = False # Reset state
                st.rerun()

st.markdown("---")

# --- Today's Revenue Summary (placed before End of Day) ---
st.subheader("Today's Revenue Summary")

# Ensure we have the live sales cached
if 'live_sales_df' not in st.session_state:
    st.session_state.live_sales_df = db.get_sales(status='live')
live_sales_df = st.session_state.live_sales_df

# Safely compute totals and include today's expenses to compute profit
if live_sales_df is None or live_sales_df.empty:
    live_total = 0.0
else:
    todays_offline_df = live_sales_df[live_sales_df.get('channel') == 'Offline'].copy()
    live_total = todays_offline_df["total_sale"].sum() if not todays_offline_df.empty and "total_sale" in todays_offline_df.columns else 0.0

# Fetch today's live expenses (if any)
try:
    today_str = date.today().isoformat()
    expenses_df = db.get_expenses(status='live', expense_date=today_str)
    expenses_total = expenses_df['amount'].sum() if (expenses_df is not None and not expenses_df.empty and 'amount' in expenses_df.columns) else 0.0
except Exception:
    expenses_total = 0.0

profit = live_total - expenses_total
live_grand_total = live_total  # keep naming aligned with previous usage

# Display the summary metrics: Revenue, Expenses, Profit
col1, col2, col3 = st.columns(3)
col1.metric("Revenue", f"₹{live_total:.2f}")
col2.metric("Expenses", f"₹{expenses_total:.2f}")
col3.metric("Profit", f"₹{profit:.2f}")

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
            # Archive today's sales and expenses
            db.archive_live_sales()
            try:
                db.archive_live_expenses()
            except Exception:
                # Non-fatal if expenses table/function isn't available
                pass
            # Clear local cache of live sales (they are now archived)
            if 'live_sales_df' in st.session_state:
                st.session_state.live_sales_df = st.session_state.live_sales_df.iloc[0:0].copy()
            st.balloons()
            st.success(f"Successfully saved all sales and expenses for {date.today().isoformat()} to your permanent record!")
            st.session_state.confirm_end_day = False
            st.rerun()
    with c2:
        if st.button("Cancel###"): # Use "###" to create a unique key
            st.session_state.confirm_end_day = False # Reset state
            st.rerun()