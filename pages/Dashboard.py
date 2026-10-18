"""Dashboard: KPIs, Plotly charts and (admin only) ML sales forecast."""
import streamlit as st

from database import queries
from ml.forecasting import forecast_summary, predict_sales
from utils import calculations as calc
from utils.ui import (
    date_filter, is_admin, render_header, render_sidebar, require_login, setup_page,
)

setup_page("Dashboard")
require_login()
render_sidebar()
render_header("Dashboard", "Sales, profit and expense overview")

start, end = date_filter("dash")
sales = queries.get_sales_df(start, end)
expenses = queries.get_expenses_df(start, end)
products = queries.get_products()
kpi = calc.compute_kpis(sales, expenses)


def render_overview() -> None:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total sales", calc.format_currency(kpi["revenue"]))
    c2.metric("Gross profit", calc.format_currency(kpi["gross_profit"]),
              f"{kpi['gross_margin']:.1f}% margin")
    c3.metric("Total expenses", calc.format_currency(kpi["expenses"]))
    c4.metric("Net profit", calc.format_currency(kpi["net_profit"]),
              f"{kpi['net_margin']:.1f}% margin")
    c5.metric("Transactions", f"{kpi['transactions']:,}", f"{kpi['units_sold']:,} units sold",
              delta_color="off")

    left, right = st.columns([3, 2])
    left.plotly_chart(calc.chart_sales_trend(sales), use_container_width=True, key="dash_sales_trend")
    right.plotly_chart(calc.chart_top_products(sales), use_container_width=True, key="dash_top_products")

    left, right = st.columns([3, 2])
    left.plotly_chart(calc.chart_monthly_performance(sales, expenses), use_container_width=True, key="dash_monthly")
    right.plotly_chart(calc.chart_expense_breakdown(expenses), use_container_width=True, key="dash_expense_pie")

    low = calc.low_stock(products)
    if not low.empty:
        with st.expander(f"⚠️ Low stock alerts ({len(low)})", expanded=False):
            st.dataframe(
                low[["name", "category", "stock"]].rename(
                    columns={"name": "Product", "category": "Category", "stock": "In stock"}),
                hide_index=True, use_container_width=True,
            )


def render_forecast() -> None:
    st.caption("Linear-regression forecast built from your recorded daily sales. "
               "It improves as more history is recorded.")
    horizon = st.slider("Forecast horizon (days)", 7, 90, 30, key="forecast_days")
    summary = forecast_summary(horizon)
    if summary:
        m1, m2, m3 = st.columns(3)
        change = summary["change_pct"]
        m1.metric(f"Predicted sales (next {horizon} days)", calc.format_currency(summary["total"]),
                  f"{change:+.1f}% vs previous {horizon} days" if change is not None else None)
        m2.metric("Average per day", calc.format_currency(summary["avg_daily"]))
        m3.metric("Trend", f"{calc.format_currency(summary['trend_per_day'])} / day",
                  f"model fit R² = {summary['r2']:.2f}", delta_color="off")
    st.plotly_chart(predict_sales(horizon), use_container_width=True, key="dash_forecast")


if is_admin():
    tab_overview, tab_forecast = st.tabs(["📊 Overview", "🔮 Sales Forecast"])
    with tab_overview:
        render_overview()
    with tab_forecast:
        render_forecast()
else:
    render_overview()
