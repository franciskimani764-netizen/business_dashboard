"""All CRUD operations for Fraximus Business Dashboard.

Every function opens its own short-lived transaction via ``db_session`` so the
Streamlit script (which reruns constantly) never holds a connection open.
Permission checks (admin vs worker) are enforced by the UI layer; stock and
integrity rules are enforced here.
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Optional

import bcrypt
import pandas as pd

from database.connection import db_session


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def _iso(value) -> Optional[str]:
    """Convert a date/datetime into 'YYYY-MM-DD' (None stays None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with db_session() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:  # e.g. password longer than bcrypt's 72-byte limit
        return False


# ----------------------------------------------------------------------------
# Users
# ----------------------------------------------------------------------------
def create_user(username: str, password: str, role: str) -> int:
    """Create a user. Raises sqlite3.IntegrityError if the username already exists."""
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, hash_password(password), role),
        )
        return cur.lastrowid


def verify_credentials(username: str, password: str) -> Optional[dict]:
    """Return {'id', 'username', 'role'} when the credentials are valid, otherwise None."""
    with db_session() as conn:
        row = conn.execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"id": row["id"], "username": row["username"], "role": row["role"]}
    return None


def list_users() -> pd.DataFrame:
    return _df("SELECT id, username, role, created_at FROM users ORDER BY role, username")


def delete_worker(user_id: int) -> bool:
    """Delete a user only if they are a worker. Returns True when a row was removed."""
    with db_session() as conn:
        cur = conn.execute("DELETE FROM users WHERE id = ? AND role = 'worker'", (user_id,))
        return cur.rowcount > 0


def update_password(user_id: int, new_password: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )


# ----------------------------------------------------------------------------
# Products
# ----------------------------------------------------------------------------
def add_product(name: str, category: str, cost_price: float, selling_price: float, stock: int) -> int:
    """Insert a product. Raises sqlite3.IntegrityError on duplicate names."""
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO products (name, category, cost_price, selling_price, stock) "
            "VALUES (?, ?, ?, ?, ?)",
            (name, category, cost_price, selling_price, stock),
        )
        return cur.lastrowid


def get_products() -> pd.DataFrame:
    return _df(
        "SELECT id, name, category, cost_price, selling_price, stock, created_at "
        "FROM products ORDER BY name"
    )


def update_product(product_id: int, name: str, category: str, cost_price: float,
                   selling_price: float, stock: int) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE products SET name=?, category=?, cost_price=?, selling_price=?, stock=? "
            "WHERE id=?",
            (name, category, cost_price, selling_price, stock, product_id),
        )


def delete_product(product_id: int) -> None:
    """Delete a product. Raises sqlite3.IntegrityError if sales reference it."""
    with db_session() as conn:
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))


def add_stock(product_id: int, quantity: int) -> None:
    """Increase stock (restock)."""
    with db_session() as conn:
        conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?", (quantity, product_id))


# ----------------------------------------------------------------------------
# Customers
# ----------------------------------------------------------------------------
def add_customer(name: str, phone: str, email: str) -> int:
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO customers (name, phone, email) VALUES (?, ?, ?)",
            (name, phone or None, email or None),
        )
        return cur.lastrowid


def get_customers() -> pd.DataFrame:
    """Customers with their purchase count and lifetime spend."""
    return _df(
        """
        SELECT c.id, c.name, c.phone, c.email, c.created_at,
               COUNT(s.id) AS purchases,
               COALESCE(SUM(s.quantity * s.unit_price), 0) AS total_spent
        FROM customers c
        LEFT JOIN sales s ON s.customer_id = c.id
        GROUP BY c.id
        ORDER BY c.name
        """
    )


def update_customer(customer_id: int, name: str, phone: str, email: str) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE customers SET name=?, phone=?, email=? WHERE id=?",
            (name, phone or None, email or None, customer_id),
        )


def delete_customer(customer_id: int) -> None:
    """Delete a customer. Their past sales are kept (customer becomes 'walk-in')."""
    with db_session() as conn:
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


def get_customer_purchase_history(customer_id: int) -> pd.DataFrame:
    df = _df(
        """
        SELECT s.id, s.sale_date, p.name AS product, s.quantity, s.unit_price,
               s.quantity * s.unit_price AS total
        FROM sales s
        JOIN products p ON p.id = s.product_id
        WHERE s.customer_id = ?
        ORDER BY s.sale_date DESC, s.id DESC
        """,
        (customer_id,),
    )
    if not df.empty:
        df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df


# ----------------------------------------------------------------------------
# Sales
# ----------------------------------------------------------------------------
def add_sale(product_id: int, customer_id: Optional[int], quantity: int, unit_price: float,
             sale_date, created_by: str) -> int:
    """Record a sale and decrement stock atomically. Raises ValueError on bad input/stock."""
    with db_session() as conn:
        prod = conn.execute(
            "SELECT cost_price, stock, name FROM products WHERE id = ?", (product_id,)
        ).fetchone()
        if prod is None:
            raise ValueError("Product not found.")
        if quantity > prod["stock"]:
            raise ValueError(
                f"Insufficient stock for '{prod['name']}': {prod['stock']} available, "
                f"{quantity} requested."
            )
        cur = conn.execute(
            "INSERT INTO sales (product_id, customer_id, quantity, unit_price, unit_cost, "
            "sale_date, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (product_id, customer_id, quantity, unit_price, prod["cost_price"],
             _iso(sale_date), created_by),
        )
        conn.execute("UPDATE products SET stock = stock - ? WHERE id = ?", (quantity, product_id))
        return cur.lastrowid


def get_sales_df(start=None, end=None) -> pd.DataFrame:
    """Sales joined with product/customer names, with revenue/cost/profit columns."""
    df = _df(
        """
        SELECT s.id, s.sale_date, p.name AS product, p.category,
               c.name AS customer, s.quantity, s.unit_price, s.unit_cost,
               s.quantity * s.unit_price                  AS revenue,
               s.quantity * s.unit_cost                   AS cost,
               s.quantity * (s.unit_price - s.unit_cost)  AS profit,
               s.created_by, s.product_id, s.customer_id
        FROM sales s
        JOIN products p ON p.id = s.product_id
        LEFT JOIN customers c ON c.id = s.customer_id
        WHERE (? IS NULL OR s.sale_date >= ?)
          AND (? IS NULL OR s.sale_date <= ?)
        ORDER BY s.sale_date DESC, s.id DESC
        """,
        (_iso(start), _iso(start), _iso(end), _iso(end)),
    )
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    return df


def update_sale(sale_id: int, customer_id: Optional[int], quantity: int, unit_price: float,
                sale_date) -> None:
    """Edit a sale and re-balance stock. Raises ValueError if stock would go negative."""
    with db_session() as conn:
        sale = conn.execute(
            "SELECT product_id, quantity FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()
        if sale is None:
            raise ValueError("Sale not found.")
        prod = conn.execute(
            "SELECT stock, name FROM products WHERE id = ?", (sale["product_id"],)
        ).fetchone()
        available = prod["stock"] + sale["quantity"]  # stock if this sale never happened
        if quantity > available:
            raise ValueError(
                f"Insufficient stock for '{prod['name']}': only {available} units available."
            )
        conn.execute(
            "UPDATE sales SET customer_id=?, quantity=?, unit_price=?, sale_date=? WHERE id=?",
            (customer_id, quantity, unit_price, _iso(sale_date), sale_id),
        )
        conn.execute(
            "UPDATE products SET stock = ? WHERE id = ?", (available - quantity, sale["product_id"])
        )


def delete_sale(sale_id: int) -> None:
    """Delete a sale and return its quantity to stock."""
    with db_session() as conn:
        sale = conn.execute(
            "SELECT product_id, quantity FROM sales WHERE id = ?", (sale_id,)
        ).fetchone()
        if sale is None:
            return
        conn.execute("UPDATE products SET stock = stock + ? WHERE id = ?",
                     (sale["quantity"], sale["product_id"]))
        conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))


# ----------------------------------------------------------------------------
# Expenses
# ----------------------------------------------------------------------------
def add_expense(category: str, description: str, amount: float, expense_date, created_by: str) -> int:
    with db_session() as conn:
        cur = conn.execute(
            "INSERT INTO expenses (category, description, amount, expense_date, created_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (category, description or None, amount, _iso(expense_date), created_by),
        )
        return cur.lastrowid


def get_expenses_df(start=None, end=None) -> pd.DataFrame:
    df = _df(
        """
        SELECT id, expense_date, category, description, amount, created_by
        FROM expenses
        WHERE (? IS NULL OR expense_date >= ?)
          AND (? IS NULL OR expense_date <= ?)
        ORDER BY expense_date DESC, id DESC
        """,
        (_iso(start), _iso(start), _iso(end), _iso(end)),
    )
    df["expense_date"] = pd.to_datetime(df["expense_date"])
    return df


def update_expense(expense_id: int, category: str, description: str, amount: float,
                   expense_date) -> None:
    with db_session() as conn:
        conn.execute(
            "UPDATE expenses SET category=?, description=?, amount=?, expense_date=? WHERE id=?",
            (category, description or None, amount, _iso(expense_date), expense_id),
        )


def delete_expense(expense_id: int) -> None:
    with db_session() as conn:
        conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
