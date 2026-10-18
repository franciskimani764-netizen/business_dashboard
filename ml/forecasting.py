"""Sales forecasting with Pandas + scikit-learn LinearRegression.

Pipeline: SQLite sales -> daily revenue series -> regression on a time trend
(plus day-of-week effects when there is enough history) -> next-N-day
prediction with an approximate 95% band -> Plotly figure.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from sklearn.linear_model import LinearRegression

from database import queries
from utils.calculations import PALETTE, empty_figure, style_figure

MIN_HISTORY_DAYS = 7      # minimum calendar days of history required
WEEKDAY_MIN_DAYS = 28     # use day-of-week features only with >= 4 weeks of data


def _load_daily_revenue() -> pd.Series:
    """Read sales from SQLite and return revenue per calendar day (gaps filled with 0)."""
    sales = queries.get_sales_df()
    if sales.empty:
        return pd.Series(dtype=float)
    daily = sales.groupby(sales["sale_date"].dt.normalize())["revenue"].sum()
    full_range = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    return daily.reindex(full_range, fill_value=0.0).astype(float)


def _features(dates: pd.DatetimeIndex, t: np.ndarray, use_weekday: bool) -> pd.DataFrame:
    cols = {"t": t}
    if use_weekday:
        for dow in range(1, 7):  # Monday is the baseline
            cols[f"dow_{dow}"] = (np.asarray(dates.dayofweek) == dow).astype(int)
    return pd.DataFrame(cols, index=dates)


def _run_forecast(days: int) -> Optional[dict]:
    """Fit the model and forecast. Returns None when there is not enough history."""
    daily = _load_daily_revenue()
    if len(daily) < MIN_HISTORY_DAYS:
        return None

    n = len(daily)
    use_weekday = n >= WEEKDAY_MIN_DAYS
    x_train = _features(daily.index, np.arange(n), use_weekday)
    model = LinearRegression().fit(x_train, daily.values)

    residuals = daily.values - model.predict(x_train)
    sigma = float(np.std(residuals))

    future_dates = pd.date_range(daily.index[-1] + pd.Timedelta(days=1), periods=days, freq="D")
    x_future = _features(future_dates, np.arange(n, n + days), use_weekday)
    predicted = np.clip(model.predict(x_future), 0, None)

    forecast = pd.DataFrame({
        "date": future_dates,
        "predicted": predicted,
        "lower": np.clip(predicted - 1.96 * sigma, 0, None),
        "upper": predicted + 1.96 * sigma,
    })
    return {
        "history": daily,
        "forecast": forecast,
        "r2": float(model.score(x_train, daily.values)),
        "slope": float(model.coef_[0]),
    }


def forecast_summary(days: int = 30) -> Optional[dict]:
    """Headline numbers for the forecast (used for KPI cards)."""
    result = _run_forecast(days)
    if result is None:
        return None
    total = float(result["forecast"]["predicted"].sum())
    recent = float(result["history"].tail(days).sum())
    return {
        "total": total,
        "avg_daily": total / days,
        "change_pct": ((total - recent) / recent * 100) if recent > 0 else None,
        "trend_per_day": result["slope"],
        "r2": result["r2"],
    }


def predict_sales(days: int = 30) -> go.Figure:
    """Predict revenue for the next ``days`` days and return a Plotly figure."""
    result = _run_forecast(days)
    if result is None:
        return empty_figure(
            f"Not enough sales history yet - record at least {MIN_HISTORY_DAYS} days of sales "
            "to unlock forecasting."
        )

    history, forecast = result["history"], result["forecast"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=history.index, y=history.values, name="Actual daily sales",
                             mode="lines", line=dict(color="#9AA5B1", width=1.5)))
    fig.add_trace(go.Scatter(x=history.index, y=history.rolling(7, min_periods=1).mean(),
                             name="7-day average", mode="lines",
                             line=dict(color=PALETTE[0], width=2.5)))
    # Confidence band (upper edge invisible, lower edge fills up to it)
    fig.add_trace(go.Scatter(x=forecast["date"], y=forecast["upper"], mode="lines",
                             line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast["date"], y=forecast["lower"], mode="lines",
                             line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(192,121,43,0.18)", name="95% range",
                             hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=forecast["date"], y=forecast["predicted"],
                             name=f"Forecast (next {days} days)", mode="lines",
                             line=dict(color=PALETTE[1], width=3, dash="dash")))
    fig.update_yaxes(title_text="Sales (KES)")
    return style_figure(fig, f"Sales forecast - next {days} days", height=440, hover_unified=True)
