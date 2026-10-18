"""Sales: record sales (everyone), review them (everyone), edit/delete (admin only)."""
import time
from datetime import date

import pandas as pd
import streamlit as st

from database import queries
from utils import calculations as calc
from utils import validation
from utils.ui import (
    current_user, date_filter, is_admin, render_header, render_sidebar, require_login,
    set_flash, setup_page, show_errors,
)

setup_page("Sales")
user = require_login()
render_sidebar()
render_header("Sales", "Record sales and review your sales history")
admin = is_admin()

products = queries.get_products()
customers = queries.get_customers()
customer_options = {0: "Walk-in customer"}
customer_options.update({int(r["id"]): r["name"] for _, r in customers.iterrows()})

# ----------------------------------------------------------------------------
# Add sale
# ----------------------------------------------------------------------------
st.subheader("➕ Record a sale")
if products.empty:
    st.info("No products yet. Add products on the Products page before recording sales.")
else:
    product_options = {
        int(r["id"]): f"{r['name']}  (stock: {int(r['stock'])})" for _, r in products.iterrows()
    }
    pid = st.selectbox("Product", list(product_options.keys()),
                       format_func=lambda i: product_options[i], key="sale_product")
    product = products.loc[products["id"] == pid].iloc[0]

    c1, c2, c3, c4 = st.columns(4)
    qty = c1.number_input("Quantity", min_value=1, value=1, step=1, key="sale_qty")
    # Price key includes the product id so the default follows the selected product
    price = c2.number_input("Unit price (KES)", min_value=0.0, value=float(product["selling_price"]),
                            step=1.0, format="%.2f", key=f"sale_price_{pid}")
    cust_id = c3.selectbox("Customer", list(customer_options.keys()),
                           format_func=lambda i: customer_options[i], key="sale_customer")
    sale_date = c4.date_input("Date", value=date.today(), max_value=date.today(), key="sale_date")

    st.caption(f"Sale total: **{calc.format_currency(calc.line_total(qty, price))}** · "
               f"Available stock: **{int(product['stock'])}**")

    if st.button("Record sale", type="primary", key="sale_submit"):
        errors = validation.collect_errors(
            validation.validate_quantity(qty),
            validation.validate_positive_number(price, "Unit price", allow_zero=True),
            validation.validate_not_future(sale_date, "Sale date"),
        )
        if errors:
            show_errors(errors)
        else:
            try:
                queries.add_sale(pid, cust_id or None, int(qty), float(price), sale_date,
                                 user["username"])
            except ValueError as exc:
                st.error(str(exc))
            else:
                set_flash(f"Sale recorded: {int(qty)} × {product['name']}.")
                st.rerun()

# ----------------------------------------------------------------------------
# Sales table
# ----------------------------------------------------------------------------
st.divider()
st.subheader("📋 Sales history")
start, end = date_filter("sales")
sales = queries.get_sales_df(start, end)

if sales.empty:
    st.info("No sales found for this period.")
else:
    m1, m2, m3 = st.columns(3)
    m1.metric("Revenue", calc.format_currency(calc.total_revenue(sales)))
    m2.metric("Gross profit", calc.format_currency(calc.gross_profit(sales)))
    m3.metric("Transactions", f"{len(sales):,}")

    view = sales[["id", "sale_date", "product", "customer", "quantity", "unit_price",
                  "revenue", "profit", "created_by"]].copy()
    view["customer"] = view["customer"].fillna("Walk-in")
    st.dataframe(
        view.rename(columns={"id": "ID", "sale_date": "Date", "product": "Product",
                             "customer": "Customer", "quantity": "Qty",
                             "unit_price": "Unit price", "revenue": "Revenue",
                             "profit": "Profit", "created_by": "Recorded by"}),
        hide_index=True, use_container_width=True,
        column_config={
            "Date": st.column_config.DateColumn(format="YYYY-MM-DD"),
            "Unit price": st.column_config.NumberColumn(format="%.2f"),
            "Revenue": st.column_config.NumberColumn(format="%.2f"),
            "Profit": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    st.download_button("⬇️ Download CSV", view.to_csv(index=False).encode("utf-8"),
                       file_name="sales.csv", mime="text/csv")

    # ------------------------------------------------------------------------
    # Edit / delete: ONLY rendered for admins
    # ------------------------------------------------------------------------
    if admin:
        with st.expander("✏️ Edit / 🗑️ Delete a sale"):
            labels = {
                int(r["id"]): f"#{int(r['id'])} · {r['sale_date']:%Y-%m-%d} · {r['product']} × {int(r['quantity'])}"
                for _, r in sales.iterrows()
            }
            sid = st.selectbox("Select sale", list(labels.keys()),
                               format_func=lambda i: labels[i], key="edit_sale_select")
            row = sales.loc[sales["id"] == sid].iloc[0]
            current_cust = 0 if pd.isna(row["customer_id"]) else int(row["customer_id"])
            cust_keys = list(customer_options.keys())

            e1, e2, e3, e4 = st.columns(4)
            new_qty = e1.number_input("Quantity", min_value=1, value=int(row["quantity"]),
                                      step=1, key=f"edit_qty_{sid}")
            new_price = e2.number_input("Unit price (KES)", min_value=0.0,
                                        value=float(row["unit_price"]), step=1.0, format="%.2f",
                                        key=f"edit_price_{sid}")
            new_cust = e3.selectbox("Customer", cust_keys,
                                    index=cust_keys.index(current_cust) if current_cust in cust_keys else 0,
                                    format_func=lambda i: customer_options[i],
                                    key=f"edit_cust_{sid}")
            new_date = e4.date_input("Date", value=row["sale_date"].date(),
                                     max_value=date.today(), key=f"edit_date_{sid}")

            b1, b2 = st.columns(2)
            if b1.button("💾 Save changes", type="primary", key=f"save_sale_{sid}"):
                errors = validation.collect_errors(
                    validation.validate_quantity(new_qty),
                    validation.validate_positive_number(new_price, "Unit price", allow_zero=True),
                    validation.validate_not_future(new_date, "Sale date"),
                )
                if errors:
                    show_errors(errors)
                else:
                    try:
                        queries.update_sale(sid, new_cust or None, int(new_qty),
                                            float(new_price), new_date)
                    except ValueError as exc:
                        st.error(str(exc))
                    else:
                        set_flash(f"Sale #{sid} updated.")
                        st.rerun()

            confirm = b2.checkbox("Confirm delete", key=f"confirm_del_sale_{sid}")
            if b2.button("🗑️ Delete sale", disabled=not confirm, key=f"del_sale_{sid}"):
                queries.delete_sale(sid)
                set_flash(f"Sale #{sid} deleted and stock restored.")
                st.rerun()
    else:
        st.caption("🔒 Editing and deleting sales is restricted to administrators.")
