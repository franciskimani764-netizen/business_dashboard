"""Products: add products, restock (everyone); edit/delete (admin only)."""
import sqlite3

import streamlit as st

from database import queries
from utils import calculations as calc
from utils import validation
from utils.ui import (
    form_nonce, is_admin, render_header, render_sidebar, require_login, reset_form,
    set_flash, setup_page, show_errors,
)

setup_page("Products")
user = require_login()
render_sidebar()
render_header("Products & Stock", "Manage your catalogue and keep an eye on stock levels")
admin = is_admin()

products = queries.get_products()

# ---- KPIs ----
k1, k2, k3, k4 = st.columns(4)
k1.metric("Products", f"{len(products):,}")
k2.metric("Units in stock", f"{int(products['stock'].sum()) if not products.empty else 0:,}")
stock_value = float((products["cost_price"] * products["stock"]).sum()) if not products.empty else 0.0
k3.metric("Stock value (at cost)", calc.format_currency(stock_value))
k4.metric("Low-stock items", f"{len(calc.low_stock(products)):,}",
          f"≤ {calc.LOW_STOCK_THRESHOLD} units", delta_color="off")

left, right = st.columns(2)

# ---- Add product ----
with left:
    st.subheader("➕ Add product")
    n = form_nonce("add_product")
    with st.form(f"add_product_form_{n}"):
        name = st.text_input("Product name", key=f"p_name_{n}")
        category = st.text_input("Category", value="General", key=f"p_cat_{n}")
        c1, c2 = st.columns(2)
        cost = c1.number_input("Cost price (KES)", min_value=0.0, step=1.0, format="%.2f",
                               key=f"p_cost_{n}")
        sell = c2.number_input("Selling price (KES)", min_value=0.0, step=1.0, format="%.2f",
                               key=f"p_sell_{n}")
        stock = st.number_input("Initial stock", min_value=0, value=0, step=1, key=f"p_stock_{n}")
        submitted = st.form_submit_button("Add product", type="primary")
    if submitted:
        errors = validation.collect_errors(
            validation.validate_required(name, "Product name"),
            validation.validate_required(category, "Category", 50),
            validation.validate_positive_number(cost, "Cost price", allow_zero=True),
            validation.validate_positive_number(sell, "Selling price"),
            validation.validate_quantity(stock, "Initial stock", allow_zero=True),
        )
        if errors:
            show_errors(errors)
        else:
            try:
                queries.add_product(name.strip(), category.strip(), float(cost), float(sell), int(stock))
            except sqlite3.IntegrityError:
                st.error("A product with that name already exists.")
            else:
                set_flash(f"Product '{name.strip()}' added." +
                          (" ⚠️ Selling price is below cost." if sell < cost else ""))
                reset_form("add_product")
                st.rerun()

# ---- Restock ----
with right:
    st.subheader("📥 Restock")
    if products.empty:
        st.info("Add a product first.")
    else:
        options = {int(r["id"]): f"{r['name']}  (stock: {int(r['stock'])})"
                   for _, r in products.iterrows()}
        with st.form("restock_form"):
            rid = st.selectbox("Product", list(options.keys()),
                               format_func=lambda i: options[i], key="restock_product")
            add_qty = st.number_input("Units to add", min_value=1, value=1, step=1, key="restock_qty")
            restock = st.form_submit_button("Add stock", type="primary")
        if restock:
            error = validation.validate_quantity(add_qty, "Units to add")
            if error:
                st.error(error)
            else:
                queries.add_stock(rid, int(add_qty))
                set_flash(f"Added {int(add_qty)} units to stock.")
                st.rerun()

# ---- Inventory table ----
st.divider()
st.subheader("📋 Inventory")
if products.empty:
    st.info("No products yet.")
else:
    view = products[["id", "name", "category", "cost_price", "selling_price", "stock"]].copy()
    view["margin"] = ((view["selling_price"] - view["cost_price"]) /
                      view["selling_price"].where(view["selling_price"] > 0) * 100).fillna(0)
    view["status"] = view["stock"].map(
        lambda s: "⚠️ Low" if s <= calc.LOW_STOCK_THRESHOLD else "✅ OK")
    st.dataframe(
        view.rename(columns={"id": "ID", "name": "Product", "category": "Category",
                             "cost_price": "Cost", "selling_price": "Price", "stock": "Stock",
                             "margin": "Margin %", "status": "Status"}),
        hide_index=True, use_container_width=True,
        column_config={
            "Cost": st.column_config.NumberColumn(format="%.2f"),
            "Price": st.column_config.NumberColumn(format="%.2f"),
            "Margin %": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    # ---- Edit / delete (inputs disabled for workers) ----
    with st.expander("✏️ Edit / 🗑️ Delete a product"):
        if not admin:
            st.caption("🔒 Only administrators can edit or delete products.")
        labels = {int(r["id"]): r["name"] for _, r in products.iterrows()}
        pid = st.selectbox("Select product", list(labels.keys()),
                           format_func=lambda i: labels[i], key="edit_product_select",
                           disabled=not admin)
        row = products.loc[products["id"] == pid].iloc[0]
        e1, e2 = st.columns(2)
        new_name = e1.text_input("Name", value=row["name"], key=f"e_name_{pid}", disabled=not admin)
        new_cat = e2.text_input("Category", value=row["category"], key=f"e_cat_{pid}", disabled=not admin)
        e3, e4, e5 = st.columns(3)
        new_cost = e3.number_input("Cost price", min_value=0.0, value=float(row["cost_price"]),
                                   step=1.0, format="%.2f", key=f"e_cost_{pid}", disabled=not admin)
        new_sell = e4.number_input("Selling price", min_value=0.0, value=float(row["selling_price"]),
                                   step=1.0, format="%.2f", key=f"e_sell_{pid}", disabled=not admin)
        new_stock = e5.number_input("Stock", min_value=0, value=int(row["stock"]), step=1,
                                    key=f"e_stock_{pid}", disabled=not admin)
        b1, b2 = st.columns(2)
        if b1.button("💾 Save changes", type="primary", disabled=not admin, key=f"save_prod_{pid}"):
            if not admin:
                st.error("Administrators only.")
            else:
                errors = validation.collect_errors(
                    validation.validate_required(new_name, "Product name"),
                    validation.validate_required(new_cat, "Category", 50),
                    validation.validate_positive_number(new_cost, "Cost price", allow_zero=True),
                    validation.validate_positive_number(new_sell, "Selling price"),
                    validation.validate_quantity(new_stock, "Stock", allow_zero=True),
                )
                if errors:
                    show_errors(errors)
                else:
                    try:
                        queries.update_product(pid, new_name.strip(), new_cat.strip(),
                                               float(new_cost), float(new_sell), int(new_stock))
                    except sqlite3.IntegrityError:
                        st.error("Another product already uses that name.")
                    else:
                        set_flash(f"Product '{new_name.strip()}' updated.")
                        st.rerun()
        confirm = b2.checkbox("Confirm delete", key=f"confirm_del_prod_{pid}", disabled=not admin)
        if b2.button("🗑️ Delete product", disabled=not (admin and confirm), key=f"del_prod_{pid}"):
            try:
                queries.delete_product(pid)
            except sqlite3.IntegrityError:
                st.error("This product has sales records and cannot be deleted. "
                         "Set its stock to 0 instead.")
            else:
                set_flash(f"Product '{row['name']}' deleted.")
                st.rerun()
