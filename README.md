# Fraximus Business Dashboard

Streamlit business-intelligence app for small businesses: sales, products & stock,
customers, expenses, KPI dashboard and a 30-day sales forecast.

## Run

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

`business.db` is created automatically on first launch with a default admin account:

| Username | Password   |
|----------|------------|
| admin    | admin123   |

**Change the password immediately** (Home → My Account).

## Roles

| Capability                          | Admin | Worker |
|-------------------------------------|:-----:|:------:|
| View dashboard                      |  ✅   |   ✅   |
| ML sales forecast                   |  ✅   |   ❌   |
| Add sales / products / customers / expenses | ✅ | ✅ |
| Edit / delete records               |  ✅   |   ❌   |
| Add / remove team members           |  ✅   |   ❌   |

## Structure

```
app.py              Login, landing page, role-based menu, admin panel
pages/              Dashboard, Sales, Products, Customers, Expenses
database/           connection.py (schema + SQLite), queries.py (CRUD)
ml/forecasting.py   Linear-regression sales forecast (Pandas + scikit-learn + Plotly)
utils/              calculations.py, validation.py, ui.py (theme, header, footer, auth guard)
assets/logo.png     Logo used in the header, sidebar and login page
.streamlit/         Light cream theme config
```

## Notes

- Passwords are hashed with bcrypt; plain-text passwords are never stored.
- Each sale stores the product's cost at the time of sale, so profit stays accurate if costs change later.
- Recording / editing / deleting a sale automatically adjusts product stock.
- Currency is shown as KES; change `format_currency` in `utils/calculations.py` to use another.
