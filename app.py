"""Fraximus Business Dashboard - main entry point.

Handles: login, landing page with role-based menu, admin panel (manage team
members) and account settings. Run with:  streamlit run app.py
"""
import sqlite3

import streamlit as st

from database import queries
from utils import validation
from utils.ui import (
    APP_TITLE, LOGO_PATH, MENU, current_user, form_nonce, is_admin, login,
    render_header, render_sidebar, reset_form, set_flash, setup_page, show_errors,
)

setup_page("Home")


# ----------------------------------------------------------------------------
# Login
# ----------------------------------------------------------------------------
def show_login() -> None:
    _, middle, _ = st.columns([1, 1.3, 1])
    with middle:
        _, logo_col, _ = st.columns([1, 1, 1])
        with logo_col:
            if LOGO_PATH.exists():
                st.image(str(LOGO_PATH), width=150)
        st.markdown(
            f"<h2 style='text-align:center;margin-bottom:0'>{APP_TITLE}</h2>"
            "<p style='text-align:center;opacity:.75'>Sign in to continue</p>",
            unsafe_allow_html=True,
        )
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", type="primary", use_container_width=True)
        if submitted:
            if not username.strip() or not password:
                st.error("Enter both username and password.")
            elif login(username.strip(), password):
                st.rerun()
            else:
                st.error("Invalid username or password.")


# ----------------------------------------------------------------------------
# Landing / home
# ----------------------------------------------------------------------------
def show_home(user: dict) -> None:
    if user["role"] == "admin":
        st.info("**Administrator access:** add, edit and delete records, manage team members "
                "and view sales forecasts.")
    else:
        st.info("**Worker access:** add sales, products, customers and expenses, and view the "
                "dashboard. Editing and deleting records is reserved for administrators.")

    st.markdown("#### Where would you like to go?")
    cols = st.columns(3)
    for i, (path, label, icon, description) in enumerate(MENU):
        with cols[i % 3]:
            with st.container(border=True):
                st.page_link(path, label=label, icon=icon, use_container_width=True)
                st.caption(description)


# ----------------------------------------------------------------------------
# Admin panel
# ----------------------------------------------------------------------------
def show_admin_panel(user: dict) -> None:
    if not is_admin():  # defence in depth: never render for non-admins
        st.error("Administrators only.")
        return

    st.subheader("➕ Add a team member")
    n = form_nonce("add_user")
    with st.form(f"add_user_form_{n}"):
        username = st.text_input("Username", key=f"new_username_{n}")
        col_pw, col_role = st.columns(2)
        password = col_pw.text_input("Password", type="password", key=f"new_password_{n}")
        role = col_role.selectbox("Role", ["worker", "admin"], key=f"new_role_{n}")
        submitted = st.form_submit_button("Create user", type="primary")
    if submitted:
        errors = validation.collect_errors(
            validation.validate_username(username),
            validation.validate_password(password),
            validation.validate_role(role),
        )
        if errors:
            show_errors(errors)
        else:
            try:
                queries.create_user(username.strip(), password, role)
            except sqlite3.IntegrityError:
                st.error("That username is already taken.")
            else:
                set_flash(f"User '{username.strip()}' created as {role}.")
                reset_form("add_user")
                st.rerun()

    st.subheader("👥 Team members")
    users = queries.list_users()
    st.dataframe(
        users.rename(columns={"id": "ID", "username": "Username", "role": "Role",
                              "created_at": "Created"}),
        hide_index=True, use_container_width=True,
    )

    st.subheader("🗑️ Remove a worker")
    workers = users[users["role"] == "worker"]
    if workers.empty:
        st.caption("There are no worker accounts to remove.")
        return
    options = dict(zip(workers["id"].astype(int), workers["username"]))
    worker_id = st.selectbox("Worker", list(options.keys()), format_func=lambda i: options[i],
                             key="remove_worker_select")
    confirm = st.checkbox(f"I confirm I want to remove '{options[worker_id]}'",
                          key=f"remove_worker_confirm_{worker_id}")
    if st.button("Remove worker", disabled=not confirm):
        if queries.delete_worker(worker_id):
            set_flash(f"Worker '{options[worker_id]}' removed.")
            st.rerun()
        else:
            st.error("Could not remove that user.")


# ----------------------------------------------------------------------------
# Account (change own password)
# ----------------------------------------------------------------------------
def show_account(user: dict) -> None:
    st.subheader("🔑 Change my password")
    if st.session_state.get("must_change_pw"):
        st.warning("You are still using the default admin password. Please change it now.")
    with st.form("change_password_form", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        submitted = st.form_submit_button("Update password", type="primary")
    if submitted:
        errors = validation.collect_errors(validation.validate_password(new))
        if new != confirm:
            errors.append("New password and confirmation do not match.")
        if not queries.verify_credentials(user["username"], current):
            errors.append("Current password is incorrect.")
        if errors:
            show_errors(errors)
        else:
            queries.update_password(user["id"], new)
            st.session_state["must_change_pw"] = False
            st.success("Password updated.")


# ----------------------------------------------------------------------------
# Router
# ----------------------------------------------------------------------------
user = current_user()
if not user:
    show_login()
else:
    render_sidebar()
    render_header("Home", f"Welcome back, {user['username']}")
    if st.session_state.get("must_change_pw"):
        st.warning("⚠️ Default admin password detected. Change it under **My Account**.")

    if user["role"] == "admin":
        tab_home, tab_admin, tab_account = st.tabs(["🏠 Home", "🛠️ Admin Panel", "🔑 My Account"])
        with tab_home:
            show_home(user)
        with tab_admin:
            show_admin_panel(user)
        with tab_account:
            show_account(user)
    else:
        tab_home, tab_account = st.tabs(["🏠 Home", "🔑 My Account"])
        with tab_home:
            show_home(user)
        with tab_account:
            show_account(user)
