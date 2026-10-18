"""Business calculations and Plotly chart builders.

Pure functions: they take Pandas DataFrames (from database/queries.py) and
return numbers, DataFrames or Plotly figures, so they are easy to test.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

TEXT_COLOR = "#2C3E50"
CREAM = "#FFF8E7"
PLOT_BG = "#FFFDF5"
GRID = "#EFE5C8"
PALETTE = ["#2C3E50", "#C0792B", "#27AE60", "#8E44AD", "#2980B9", "#E67E22", "#16A085", "#C0392B"]
LOW_STOCK_THRESHOLD = 5


# ----------------------------------------------------------------------------
# Formatting & basic maths
# ----------------------------------------------------------------------------
def format_currency(value: float) -> str:
    return f"KES {value:,.2f}"


def safe_div(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def line_total(quantity: float, unit_price: float) -> float:
    return round(float(quantity) * float(unit_price), 2)


def _col_sum(df: pd.DataFrame, column: str) -> float:
    return float(df[column].sum()) if df is not None and not df.empty else 0.0


# ----------------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------------
def total_revenue(sales_df: pd.DataFrame) -> float:
    return _col_sum(sales_df, "revenue")


def total_cogs(sales_df: pd.DataFrame) -> float:
    """Cost of goods sold."""
    return _col_sum(sales_df, "cost")


def gross_profit(sales_df: pd.DataFrame) -> float:
    return total_revenue(sales_df) - total_cogs(sales_df)


def total_expenses(expenses_df: pd.DataFrame) -> float:
    return _col_sum(expenses_df, "amount")


def net_profit(sales_df: pd.DataFrame, expenses_df: pd.DataFrame) -> float:
    return gross_profit(sales_df) - total_expenses(expenses_df)


def gross_margin_pct(sales_df: pd.DataFrame) -> float:
    return safe_div(gross_profit(sales_df), total_revenue(sales_df)) * 100


def net_margin_pct(sales_df: pd.DataFrame, expenses_df: pd.DataFrame) -> float:
    return safe_div(net_profit(sales_df, expenses_df), total_revenue(sales_df)) * 100


def compute_kpis(sales_df: pd.DataFrame, expenses_df: pd.DataFrame) -> dict:
    return {
        "revenue": total_revenue(sales_df),
        "cogs": total_cogs(sales_df),
        "gross_profit": gross_profit(sales_df),
        "expenses": total_expenses(expenses_df),
        "net_profit": net_profit(sales_df, expenses_df),
        "gross_margin": gross_margin_pct(sales_df),
        "net_margin": net_margin_pct(sales_df, expenses_df),
        "units_sold": int(sales_df["quantity"].sum()) if not sales_df.empty else 0,
        "transactions": int(len(sales_df)),
    }


# ----------------------------------------------------------------------------
# Aggregations
# ----------------------------------------------------------------------------
def daily_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["sale_date", "revenue", "profit"])
    return (sales_df.groupby("sale_date", as_index=False)[["revenue", "profit"]]
            .sum().sort_values("sale_date"))


def top_products(sales_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    if sales_df.empty:
        return pd.DataFrame(columns=["product", "revenue", "quantity"])
    return (sales_df.groupby("product", as_index=False)
            .agg(revenue=("revenue", "sum"), quantity=("quantity", "sum"))
            .sort_values("revenue", ascending=False).head(n))


def expenses_by_category(expenses_df: pd.DataFrame) -> pd.DataFrame:
    if expenses_df.empty:
        return pd.DataFrame(columns=["category", "amount"])
    return (expenses_df.groupby("category", as_index=False)["amount"].sum()
            .sort_values("amount", ascending=False))


def monthly_summary(sales_df: pd.DataFrame, expenses_df: pd.DataFrame) -> pd.DataFrame:
    """Revenue, gross profit, expenses and net profit per calendar month."""
    cols = ["month", "revenue", "gross_profit", "expenses", "net_profit"]
    if sales_df.empty and expenses_df.empty:
        return pd.DataFrame(columns=cols)

    if sales_df.empty:
        s = pd.DataFrame(columns=["month", "revenue", "gross_profit"])
    else:
        tmp = sales_df.assign(month=sales_df["sale_date"].dt.strftime("%Y-%m"))
        s = (tmp.groupby("month", as_index=False)[["revenue", "profit"]].sum()
             .rename(columns={"profit": "gross_profit"}))

    if expenses_df.empty:
        e = pd.DataFrame(columns=["month", "expenses"])
    else:
        tmp = expenses_df.assign(month=expenses_df["expense_date"].dt.strftime("%Y-%m"))
        e = (tmp.groupby("month", as_index=False)["amount"].sum()
             .rename(columns={"amount": "expenses"}))

    merged = s.merge(e, on="month", how="outer").fillna(0.0).sort_values("month")
    merged["net_profit"] = merged["gross_profit"] - merged["expenses"]
    return merged[cols].reset_index(drop=True)


def low_stock(products_df: pd.DataFrame, threshold: int = LOW_STOCK_THRESHOLD) -> pd.DataFrame:
    if products_df.empty:
        return products_df
    return products_df[products_df["stock"] <= threshold].sort_values("stock")


# ----------------------------------------------------------------------------
# Plotly charts (shared professional style)
# ----------------------------------------------------------------------------
def style_figure(fig: go.Figure, title: str | None = None, height: int = 380,
                 hover_unified: bool = False) -> go.Figure:
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR, family="Segoe UI, Arial, sans-serif"),
        colorway=PALETTE,
        margin=dict(l=20, r=20, t=55 if title else 20, b=20),
        height=height,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0),
        hovermode="x unified" if hover_unified else "closest",
    )
    if title:
        fig.update_layout(title=dict(text=title, x=0.01, font=dict(size=16, color=TEXT_COLOR)))
    fig.update_xaxes(showgrid=False, linecolor="#E8DDBB")
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def empty_figure(message: str = "No data for the selected period", height: int = 380) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper",
                       showarrow=False, font=dict(size=15, color=TEXT_COLOR))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return style_figure(fig, height=height)


def chart_sales_trend(sales_df: pd.DataFrame) -> go.Figure:
    daily = daily_sales(sales_df)
    if daily.empty:
        return empty_figure()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=daily["sale_date"], y=daily["revenue"], name="Sales",
                             mode="lines", fill="tozeroy", line=dict(color=PALETTE[0], width=2),
                             fillcolor="rgba(44,62,80,0.12)"))
    fig.add_trace(go.Scatter(x=daily["sale_date"], y=daily["profit"], name="Gross profit",
                             mode="lines+markers", line=dict(color=PALETTE[2], width=2)))
    fig.update_yaxes(title_text="KES")
    return style_figure(fig, "Sales & profit over time", hover_unified=True)


def chart_top_products(sales_df: pd.DataFrame, n: int = 8) -> go.Figure:
    top = top_products(sales_df, n)
    if top.empty:
        return empty_figure()
    top = top.sort_values("revenue")  # ascending so the biggest bar is on top
    fig = go.Figure(go.Bar(x=top["revenue"], y=top["product"], orientation="h",
                           marker_color=PALETTE[1], text=top["revenue"].map("{:,.0f}".format),
                           textposition="outside", cliponaxis=False))
    fig.update_xaxes(title_text="Revenue (KES)")
    return style_figure(fig, "Top products by revenue")


def chart_expense_breakdown(expenses_df: pd.DataFrame) -> go.Figure:
    by_cat = expenses_by_category(expenses_df)
    if by_cat.empty:
        return empty_figure()
    fig = go.Figure(go.Pie(labels=by_cat["category"], values=by_cat["amount"], hole=0.5,
                           marker=dict(colors=PALETTE), textinfo="label+percent",
                           sort=False))
    fig.update_layout(showlegend=False)
    return style_figure(fig, "Expenses by category")


def chart_monthly_performance(sales_df: pd.DataFrame, expenses_df: pd.DataFrame) -> go.Figure:
    monthly = monthly_summary(sales_df, expenses_df)
    if monthly.empty:
        return empty_figure()
    fig = go.Figure()
    fig.add_trace(go.Bar(x=monthly["month"], y=monthly["revenue"], name="Sales",
                         marker_color=PALETTE[0]))
    fig.add_trace(go.Bar(x=monthly["month"], y=monthly["expenses"], name="Expenses",
                         marker_color=PALETTE[7]))
    fig.add_trace(go.Scatter(x=monthly["month"], y=monthly["net_profit"], name="Net profit",
                             mode="lines+markers", line=dict(color=PALETTE[2], width=3)))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title_text="KES")
    return style_figure(fig, "Monthly performance", hover_unified=True)


def chart_expense_trend(expenses_df: pd.DataFrame) -> go.Figure:
    if expenses_df.empty:
        return empty_figure()
    daily = expenses_df.groupby("expense_date", as_index=False)["amount"].sum()
    fig = go.Figure(go.Bar(x=daily["expense_date"], y=daily["amount"], marker_color=PALETTE[7]))
    fig.update_yaxes(title_text="KES")
    return style_figure(fig, "Expenses over time", hover_unified=True)
