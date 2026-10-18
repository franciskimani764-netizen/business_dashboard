"""Expenses: add expenses (everyone); edit/delete (admin only)."""
from datetime import date

import streamlit as st

from database import queries
from utils import calculations as calc
from utils import validation
from utils.ui import (
    date_filter, form_nonce, is_admin, render_header, render_sidebar, require_login,
    reset_form, set_flash, setup_page, show_errors,
)

setup_page("Expenses")
user = require_login()
render_sidebar()
render_header("Expenses", "Track what the business spends")
admin = is_admin()

CATEGORIES = validation.EXPENSE_CATEGORIES

# ---- Add expense ----
st.subheader("➕ Add expense")
n = form_nonce("add_expense")
with st.form(f"add_expense_form_{n}"):
    c1, c2, c3 = st.columns(3)
    category = c1.selectbox("Category", CATEGORIES, key=f"x_cat_{n}")
    amount = c2.number_input("Amount (KES)", min_value=0.0, step=10.0, format="%.2f", key=f"x_amt_{n}")
    exp_date = c3.date_input("Date", value=date.today(), max_value=date.today(), key=f"x_date_{n}")
    description = st.text_input("Description (optional)", key=f"x_desc_{n}")
    submitted = st.form_submit_button("Add expense", type="primary")
if submitted:
    errors = validation.collect_errors(
        validation.validate_positive_number(amount, "Amount"),
        validation.validate_not_future(exp_date, "Expense date"),
        validation.validate_required(category, "Category", 50),
    )
    if len(description.strip()) > 200:
        errors.append("Description must be at most 200 characters.")
    if errors:
        show_errors(errors)
    else:
        queries.add_expense(category, description.strip(), float(amount), exp_date, user["username"])
        set_flash(f"Expense of {calc.format_currency(float(amount))} added under {category}.")
        reset_form("add_expense")
        st.rerun()

# ---- Table + filters ----
st.divider()
st.subheader("📋 Expense history")
start, end = date_filter("exp")
selected = st.multiselect("Categories", CATEGORIES, default=[], placeholder="All categories",
                          key="exp_categories")
expenses = queries.get_expenses_df(start, end)
if selected:
    expenses = expenses[expenses["category"].isin(selected)]

if expenses.empty:
    st.info("No expenses found for this selection.")
else:
    m1, m2 = st.columns(2)
    m1.metric("Total expenses", calc.format_currency(calc.total_expenses(expenses)))
    m2.metric("Entries", f"{len(expenses):,}")

    left, right = st.columns([3, 2])
    left.plotly_chart(calc.chart_expense_trend(expenses), use_container_width=True, key="exp_trend")
    right.plotly_chart(calc.chart_expense_breakdown(expenses), use_container_width=True, key="exp_pie")

    view = expenses.copy()
    view["description"] = view["description"].fillna("")
    st.dataframe(
        view.rename(columns={"id": "ID", "expense_date": "Date", "category": "Category",
                             "description": "Description", "amount": "Amount",
                             "created_by": "Recorded by"}),
        hide_index=True, use_container_width=True,
        column_config={
            "Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "Amount": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.download_button("⬇️ Download CSV", view.to_csv(index=False).encode("utf-8"),
                       file_name="expenses.csv", mime="text/csv")

    # ---- Edit / delete (inputs disabled for workers) ----
    with st.expander("✏️ Edit / 🗑️ Delete an expense"):
        if not admin:
            st.caption("🔒 Only administrators can edit or delete expenses.")
        labels = {
            int(r["id"]): f"#{int(r['id'])} · {r['expense_date']:%Y-%m-%d} · {r['category']} · {r['amount']:,.2f}"
            for _, r in expenses.iterrows()
        }
        xid = st.selectbox("Select expense", list(labels.keys()), format_func=lambda i: labels[i],
                           key="edit_expense_select", disabled=not admin)
        row = expenses.loc[expenses["id"] == xid].iloc[0]
        cat_list = CATEGORIES if row["category"] in CATEGORIES else CATEGORIES + [row["category"]]
        e1, e2, e3 = st.columns(3)
        new_cat = e1.selectbox("Category", cat_list, index=cat_list.index(row["category"]),
                               key=f"ex_cat_{xid}", disabled=not admin)
        new_amt = e2.number_input("Amount (KES)", min_value=0.0, value=float(row["amount"]),
                                  step=10.0, format="%.2f", key=f"ex_amt_{xid}", disabled=not admin)
        new_date = e3.date_input("Date", value=row["expense_date"].date(), max_value=date.today(),
                                 key=f"ex_date_{xid}", disabled=not admin)
        new_desc = st.text_input("Description", value=row["description"] or "",
                                 key=f"ex_desc_{xid}", disabled=not admin)
        b1, b2 = st.columns(2)
        if b1.button("💾 Save changes", type="primary", disabled=not admin, key=f"save_exp_{xid}"):
            if not admin:
                st.error("Administrators only.")
            else:
                errors = validation.collect_errors(
                    validation.validate_positive_number(new_amt, "Amount"),
                    validation.validate_not_future(new_date, "Expense date"),
                )
                if errors:
                    show_errors(errors)
                else:
                    queries.update_expense(xid, new_cat, new_desc.strip(), float(new_amt), new_date)
                    set_flash(f"Expense #{xid} updated.")
                    st.rerun()
        confirm = b2.checkbox("Confirm delete", key=f"confirm_del_exp_{xid}", disabled=not admin)
        if b2.button("🗑️ Delete expense", disabled=not (admin and confirm), key=f"del_exp_{xid}"):
            queries.delete_expense(xid)
            set_flash(f"Expense #{xid} deleted.")
            st.rerun()
