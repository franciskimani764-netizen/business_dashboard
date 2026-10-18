"""Shared Streamlit UI helpers: theme, header, footer, sidebar, auth guard.

Every page (app.py and pages/*.py) calls ``setup_page`` first, then
``require_login`` and ``render_sidebar``.
"""
from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

from database import queries
from database.connection import DEFAULT_ADMIN_PASSWORD, init_db
from utils import validation

ROOT_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = ROOT_DIR / "assets" / "logo.png"

APP_TITLE = "Fraximus Business Intelligence"
FOOTER_TEXT = "Developed by Fraximus Tech | 2026"

# (page path, label, icon, description)
MENU = [
    ("pages/Dashboard.py", "Dashboard", "📊", "KPIs, charts and sales forecasting"),
    ("pages/Sales.py", "Sales", "💰", "Record and review sales"),
    ("pages/Products.py", "Products", "📦", "Catalogue and stock levels"),
    ("pages/Customers.py", "Customers", "👥", "Customer list and purchase history"),
    ("pages/Expenses.py", "Expenses", "🧾", "Track business costs"),
]

_CSS = """
<style>
/* ---- Cream theme ---- */
.stApp { background-color: #FFF8E7; color: #2C3E50; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stSidebar"] { background-color: #F6ECCF; border-right: 1px solid #E8DDBB; }
h1, h2, h3, h4, h5, h6, label, .stMarkdown p, .stCaption, [data-testid="stCaptionContainer"] {
    color: #2C3E50 !important;
}
/* Hide Streamlit's automatic page list: navigation is role-based via st.page_link */
[data-testid="stSidebarNav"] { display: none; }

/* ---- Components ---- */
[data-testid="stMetric"] {
    background: #FFFDF5; border: 1px solid #E8DDBB; border-radius: 12px; padding: 14px 16px;
}
div.stButton > button, div[data-testid="stFormSubmitButton"] > button,
div[data-testid="stDownloadButton"] > button {
    border-radius: 8px; border: 1px solid #2C3E50;
}
div.stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] > button[kind="primary"],
div.stButton > button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
    background-color: #2C3E50; color: #FFF8E7;
}
div.stButton > button[kind="primary"] p,
button[data-testid="stBaseButton-primaryFormSubmit"] p { color: #FFF8E7 !important; }
[data-testid="stExpander"], [data-testid="stForm"] {
    background: #FFFDF5; border: 1px solid #E8DDBB; border-radius: 12px;
}
.fx-title { margin: 0; padding: 0; font-size: 2rem; font-weight: 700; color: #2C3E50; }
.fx-sub { margin: 0; color: #2C3E50; opacity: .75; }

/* ---- Fixed footer on every page ---- */
.fx-footer {
    position: fixed; left: 0; bottom: 0; width: 100%; text-align: center;
    padding: 8px 0; background: #F6ECCF; color: #2C3E50; font-size: .85rem;
    border-top: 1px solid #E8DDBB; z-index: 1000;
}
.block-container { padding-bottom: 4.5rem; }
</style>
"""


@st.cache_resource(show_spinner=False)
def _bootstrap_database() -> bool:
    """Create tables / default admin once per server process."""
    init_db()
    return True


def setup_page(page_title: str) -> None:
    """Must be the first Streamlit call on every page."""
    st.set_page_config(
        page_title=f"{page_title} | Fraximus BI",
        page_icon=str(LOGO_PATH) if LOGO_PATH.exists() else "📊",
        layout="wide",
    )
    _bootstrap_database()
    st.markdown(_CSS, unsafe_allow_html=True)
    st.markdown(f'<div class="fx-footer">{FOOTER_TEXT}</div>', unsafe_allow_html=True)


# ----------------------------------------------------------------------------
# Authentication / roles
# ----------------------------------------------------------------------------
def current_user() -> dict | None:
    return st.session_state.get("user")


def is_admin() -> bool:
    user = current_user()
    return bool(user and user["role"] == "admin")


def login(username: str, password: str) -> bool:
    user = queries.verify_credentials(username, password)
    if not user:
        time.sleep(1)  # slow down brute-force attempts
        return False
    st.session_state["user"] = user
    st.session_state["must_change_pw"] = (
        user["role"] == "admin" and password == DEFAULT_ADMIN_PASSWORD
    )
    return True


def logout() -> None:
    for key in ("user", "must_change_pw"):
        st.session_state.pop(key, None)


def require_login() -> dict:
    """Stop the page with a login prompt when nobody is signed in."""
    user = current_user()
    if not user:
        st.warning("Please log in to access this page.")
        st.page_link("app.py", label="Go to login", icon="🔐")
        st.stop()
    return user


# ----------------------------------------------------------------------------
# Layout pieces
# ----------------------------------------------------------------------------
def render_header(page_title: str, subtitle: str = "") -> None:
    """Logo + 'Fraximus Business Intelligence' title, then the page heading."""
    col_logo, col_title = st.columns([1, 11], vertical_alignment="center")
    with col_logo:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=70)
    with col_title:
        st.markdown(f'<h1 class="fx-title">{APP_TITLE}</h1>', unsafe_allow_html=True)
    st.markdown(f"### {page_title}")
    if subtitle:
        st.caption(subtitle)
    show_flash()


def render_sidebar() -> None:
    """Role-based navigation using st.page_link."""
    user = current_user()
    if not user:
        return
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=90)
        st.markdown("**Fraximus BI**")
        st.caption(f"👤 {user['username']} · {user['role'].title()}")
        st.divider()
        home_label = "Home & Admin Panel" if user["role"] == "admin" else "Home"
        st.page_link("app.py", label=home_label, icon="🏠")
        for path, label, icon, _desc in MENU:
            st.page_link(path, label=label, icon=icon)
        st.divider()
        if st.button("Log out", use_container_width=True):
            logout()
            st.switch_page("app.py")


def set_flash(message: str, kind: str = "success") -> None:
    """Queue a message that survives the next st.rerun()."""
    st.session_state["_flash"] = (kind, message)


def show_flash() -> None:
    item = st.session_state.pop("_flash", None)
    if item:
        kind, message = item
        {"success": st.success, "error": st.error, "warning": st.warning}.get(kind, st.info)(message)


def form_nonce(base: str) -> int:
    """Counter used in widget keys so a form can be cleared after a successful submit."""
    return st.session_state.get(f"{base}_nonce", 0)


def reset_form(base: str) -> None:
    st.session_state[f"{base}_nonce"] = form_nonce(base) + 1


def show_errors(errors: list[str]) -> None:
    for message in errors:
        st.error(message)


def date_filter(key: str, default_index: int = 1) -> tuple[date | None, date | None]:
    """Period picker. Returns (start, end); (None, None) means 'all time'."""
    presets = ["Last 30 days", "Last 90 days", "This year", "All time", "Custom range"]
    today = date.today()
    col_preset, col_from, col_to = st.columns([2, 2, 2])
    preset = col_preset.selectbox("Period", presets, index=default_index, key=f"{key}_preset")
    if preset == "Last 30 days":
        return today - timedelta(days=29), today
    if preset == "Last 90 days":
        return today - timedelta(days=89), today
    if preset == "This year":
        return date(today.year, 1, 1), today
    if preset == "All time":
        return None, None
    start = col_from.date_input("From", value=today - timedelta(days=29), key=f"{key}_from")
    end = col_to.date_input("To", value=today, key=f"{key}_to")
    error = validation.validate_date_range(start, end)
    if error:
        st.error(error)
        st.stop()
    return start, end
