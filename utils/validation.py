"""Input validation helpers.

Each validator returns ``None`` when the value is valid, or a human-readable
error string. Pages collect the non-None results and show them with st.error.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Optional

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s\-]{6,18}$")

VALID_ROLES = ("admin", "worker")

EXPENSE_CATEGORIES = [
    "Rent", "Salaries", "Utilities", "Transport", "Marketing",
    "Supplies", "Maintenance", "Taxes & Licenses", "Internet & Airtime", "Other",
]


def collect_errors(*errors: Optional[str]) -> list[str]:
    """Filter out the None values from a list of validator results."""
    return [e for e in errors if e]


def validate_username(username: str) -> Optional[str]:
    if not username or not USERNAME_RE.match(username.strip()):
        return "Username must be 3-30 characters: letters, numbers, '.', '_' or '-'."
    return None


def validate_password(password: str) -> Optional[str]:
    if not password or len(password) < 6:
        return "Password must be at least 6 characters long."
    if len(password.encode("utf-8")) > 72:
        return "Password is too long (maximum 72 bytes)."
    return None


def validate_role(role: str) -> Optional[str]:
    return None if role in VALID_ROLES else "Role must be 'admin' or 'worker'."


def validate_required(value: str, label: str, max_len: int = 100) -> Optional[str]:
    if value is None or not str(value).strip():
        return f"{label} is required."
    if len(str(value).strip()) > max_len:
        return f"{label} must be at most {max_len} characters."
    return None


def validate_positive_number(value, label: str, allow_zero: bool = False) -> Optional[str]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{label} must be a number."
    if number != number or number in (float("inf"), float("-inf")):  # NaN / inf
        return f"{label} must be a valid number."
    if allow_zero:
        return None if number >= 0 else f"{label} cannot be negative."
    return None if number > 0 else f"{label} must be greater than zero."


def validate_quantity(value, label: str = "Quantity", allow_zero: bool = False) -> Optional[str]:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return f"{label} must be a whole number."
    if allow_zero:
        return None if number >= 0 else f"{label} cannot be negative."
    return None if number > 0 else f"{label} must be at least 1."


def validate_email(email: str) -> Optional[str]:
    """Email is optional; validate only when provided."""
    if email and not EMAIL_RE.match(email.strip()):
        return "Email address looks invalid."
    return None


def validate_phone(phone: str) -> Optional[str]:
    """Phone is optional; accepts local (07xx...) and international (+254...) formats."""
    if phone and not PHONE_RE.match(phone.strip()):
        return "Phone number looks invalid (use digits, spaces, '-' and an optional leading '+')."
    return None


def validate_not_future(value: date, label: str = "Date") -> Optional[str]:
    if value is None:
        return f"{label} is required."
    if value > date.today():
        return f"{label} cannot be in the future."
    return None


def validate_date_range(start: date, end: date) -> Optional[str]:
    if start and end and start > end:
        return "The 'From' date must be on or before the 'To' date."
    return None
