# pages/3_Analysis.py
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import database as db # Import the new database module

# Initialize the database and its tables
db.init_db()

st.set_page_config(page_title="Historical Analysis", page_icon="📊", layout="wide")

available_dates_str = db.get_archived_dates()

if not available_dates_str:
    st.warning("No historical sales data available to analyze. Please log sales and use the 'End Day & Save Sales' button on the Tracker page.")
else:
    available_dates = sorted([date.fromisoformat(d) for d in available_dates_str])
    # --- Date Range Selector ---
    st.header("🗓️ Select Date Range for Analysis")
    
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)

    date_option = st.selectbox(
        "Choose a time period:",
        ("Last 7 Days", "This Week (Mon-Today)", "This Month", "All Time", "Custom Range")
    )

    start_date, end_date = None, None
    min_date, max_date = min(available_dates), max(available_dates)

    if date_option == "Last 7 Days":
        start_date, end_date = today - timedelta(days=6), today
    elif date_option == "This Week (Mon-Today)":
        start_date, end_date = start_of_week, today
    elif date_option == "This Month":
        start_date, end_date = start_of_month, today
    elif date_option == "All Time":
        start_date, end_date = min_date, max_date
    elif date_option == "Custom Range":
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Start date", min_date, min_value=min_date, max_value=max_date)
        with col2:
            end_date = st.date_input("End date", max_date, min_value=min_date, max_value=max_date)

    # --- Fetch and Prepare Data ---
    df = db.get_sales(status='archived', start_date=start_date, end_date=end_date)
    
    if df.empty:
        st.warning("No sales data found in the selected date range.")
    else:
        df['Date'] = pd.to_datetime(df['sale_date'])
        
        # --- Analysis Display ---
        st.markdown("---")
        st.header(f"📈 Analysis for {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")

        total_revenue = df["total_sale"].sum()
        total_items_sold = df["quantity"].sum()
        
        col1, col2 = st.columns(2)
        col1.metric("Grand Total Revenue", f"₹{total_revenue:.2f}")
        col2.metric("Total Items Sold", f"{total_items_sold}")
        
        st.subheader("Revenue Over Time")
        
        # Dynamic grouping based on date range size
        range_days = (end_date - start_date).days
        if range_days <= 14:
            period_char, period_name = 'D', 'Daily'
        elif range_days <= 90:
            period_char, period_name = 'W', 'Weekly'
        else:
            period_char, period_name = 'M', 'Monthly'

        revenue_over_time = df.set_index('Date').resample(period_char)['total_sale'].sum().reset_index()

        fig_line = px.line(
            revenue_over_time, 
            x='Date', 
            y='total_sale', 
            title=f'{period_name} Revenue Trend', 
            markers=True,
            labels={'total_sale': 'Total Revenue (₹)'}
        )
        st.plotly_chart(fig_line, use_container_width=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Revenue by Channel")
            revenue_by_channel = df.groupby('channel')['total_sale'].sum().reset_index()
            fig_pie = px.pie(revenue_by_channel, names='channel', values='total_sale', title='Revenue Split',
                             color_discrete_sequence=px.colors.sequential.Agsunset)
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col2:
            st.subheader("⭐ Best-Selling Items")
            best_sellers = df.groupby('item_name').agg(
                Quantity_Sold=('quantity', 'sum'),
                Revenue_Generated=('total_sale', 'sum')
            ).sort_values(by="Revenue_Generated", ascending=False).reset_index()
            st.dataframe(best_sellers, use_container_width=True)