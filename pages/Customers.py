"""Customers: add customers, view purchase history (everyone); edit/delete (admin only)."""
import streamlit as st

from database import queries
from utils import calculations as calc
from utils import validation
from utils.ui import (
    form_nonce, is_admin, render_header, render_sidebar, require_login, reset_form,
    set_flash, setup_page, show_errors,
)

setup_page("Customers")
user = require_login()
render_sidebar()
render_header("Customers", "Your customer list and purchase history")
admin = is_admin()

customers = queries.get_customers()

k1, k2 = st.columns(2)
k1.metric("Customers", f"{len(customers):,}")
k2.metric("Lifetime customer spend",
          calc.format_currency(float(customers["total_spent"].sum()) if not customers.empty else 0.0))

# ---- Add customer ----
st.subheader("➕ Add customer")
n = form_nonce("add_customer")
with st.form(f"add_customer_form_{n}"):
    name = st.text_input("Full name", key=f"c_name_{n}")
    c1, c2 = st.columns(2)
    phone = c1.text_input("Phone (optional)", placeholder="+254 7XX XXX XXX", key=f"c_phone_{n}")
    email = c2.text_input("Email (optional)", key=f"c_email_{n}")
    submitted = st.form_submit_button("Add customer", type="primary")
if submitted:
    errors = validation.collect_errors(
        validation.validate_required(name, "Customer name"),
        validation.validate_phone(phone),
        validation.validate_email(email),
    )
    if errors:
        show_errors(errors)
    else:
        queries.add_customer(name.strip(), phone.strip(), email.strip())
        set_flash(f"Customer '{name.strip()}' added.")
        reset_form("add_customer")
        st.rerun()

# ---- Customer list ----
st.divider()
st.subheader("📋 Customer list")
if customers.empty:
    st.info("No customers yet.")
else:
    view = customers[["id", "name", "phone", "email", "purchases", "total_spent"]]
    st.dataframe(
        view.rename(columns={"id": "ID", "name": "Name", "phone": "Phone", "email": "Email",
                             "purchases": "Purchases", "total_spent": "Total spent"}),
        hide_index=True, use_container_width=True,
        column_config={"Total spent": st.column_config.NumberColumn(format="%.2f")},
    )

    labels = {int(r["id"]): r["name"] for _, r in customers.iterrows()}

    # ---- Purchase history ----
    st.subheader("🧾 Purchase history")
    cid = st.selectbox("Customer", list(labels.keys()), format_func=lambda i: labels[i],
                       key="history_customer")
    history = queries.get_customer_purchase_history(cid)
    if history.empty:
        st.info("This customer has no recorded purchases yet.")
    else:
        h1, h2, h3 = st.columns(3)
        h1.metric("Purchases", f"{len(history):,}")
        h2.metric("Total spent", calc.format_currency(float(history["total"].sum())))
        h3.metric("Last purchase", f"{history['sale_date'].max():%Y-%m-%d}")
        st.dataframe(
            history.rename(columns={"id": "Sale ID", "sale_date": "Date", "product": "Product",
                                    "quantity": "Qty", "unit_price": "Unit price",
                                    "total": "Total"}),
            hide_index=True, use_container_width=True,
            column_config={
                "Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
                "Unit price": st.column_config.NumberColumn(format="%.2f"),
                "Total": st.column_config.NumberColumn(format="%.2f"),
            },
        )

    # ---- Edit / delete (inputs disabled for workers) ----
    with st.expander("✏️ Edit / 🗑️ Delete a customer"):
        if not admin:
            st.caption("🔒 Only administrators can edit or delete customers.")
        eid = st.selectbox("Select customer", list(labels.keys()), format_func=lambda i: labels[i],
                           key="edit_customer_select", disabled=not admin)
        row = customers.loc[customers["id"] == eid].iloc[0]
        e1, e2, e3 = st.columns(3)
        new_name = e1.text_input("Name", value=row["name"], key=f"ec_name_{eid}", disabled=not admin)
        new_phone = e2.text_input("Phone", value=row["phone"] or "", key=f"ec_phone_{eid}",
                                  disabled=not admin)
        new_email = e3.text_input("Email", value=row["email"] or "", key=f"ec_email_{eid}",
                                  disabled=not admin)
        b1, b2 = st.columns(2)
        if b1.button("💾 Save changes", type="primary", disabled=not admin, key=f"save_cust_{eid}"):
            if not admin:
                st.error("Administrators only.")
            else:
                errors = validation.collect_errors(
                    validation.validate_required(new_name, "Customer name"),
                    validation.validate_phone(new_phone),
                    validation.validate_email(new_email),
                )
                if errors:
                    show_errors(errors)
                else:
                    queries.update_customer(eid, new_name.strip(), new_phone.strip(), new_email.strip())
                    set_flash("Customer updated.")
                    st.rerun()
        confirm = b2.checkbox("Confirm delete", key=f"confirm_del_cust_{eid}", disabled=not admin)
        if b2.button("🗑️ Delete customer", disabled=not (admin and confirm), key=f"del_cust_{eid}"):
            queries.delete_customer(eid)
            set_flash(f"Customer '{row['name']}' deleted. Their past sales were kept as walk-in sales.")
            st.rerun()
