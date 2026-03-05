# 🏪 Store Dashboard

A real-time store inventory and ordering dashboard built with Streamlit, powered by Supabase. Data is synced automatically from local Excel workbooks to Supabase database tables — no file uploads needed.

---

## 📋 Description

The dashboard reads live data from two Excel workbooks maintained on a local machine and syncs them to Supabase tables via a background file watcher. A Streamlit app deployed on Streamlit Cloud then queries the tables directly, providing three views:

- **Orders & Search** — Browse unordered items (uncolored PLU rows), filter by category/supplier, enter order quantities and download an order sheet. Includes a full product search by name or barcode.
- **Stock Value** — View current inventory value for all yellow-highlighted PLU codes, grouped by category or supplier.
- **Price Comparison** — Compare cost and selling prices between the RE ORDER sheet and the EXISTING PRICES sheet to spot discrepancies.

---

## 🗂️ Files

| File | Purpose |
|---|---|
| `app.py` | Streamlit dashboard — deploy to Streamlit Cloud |
| `sync_to_supabase.py` | Local file watcher — runs on the machine with the Excel files |
| `schema.sql` | Supabase table definitions — run once to set up the database |

---

## ✅ Requirements

### Supabase
- A [Supabase](https://supabase.com) account (free tier works)
- Project URL and API keys (anon key for dashboard reads, service role key for watcher writes)

### Excel Workbooks (local machine)
- `INVOICE ENTRY MACRO ENABLED.xlsm` — contains the **EXISTING PRICES** sheet
- `ORDER SHEET.xlsx` — contains the **RE ORDER** sheet
- Both files must be accessible on the machine running the watcher (e.g. via OneDrive sync)

### Python (local machine — for the watcher)
- Python 3.11 recommended
- Dependencies:
```
pip install pandas openpyxl watchdog supabase
```

### Streamlit Cloud (for the dashboard)
- A [Streamlit Cloud](https://streamlit.io/cloud) account
- GitHub repo connected to Streamlit Cloud
- Secrets configured in Streamlit Cloud settings (see below)

---

## ⚙️ Setup

### Step 1 — Supabase Database
1. Go to your Supabase project → SQL Editor
2. Run the full contents of `schema.sql` to create the `existing_prices` and `re_order` tables with the correct indexes and RLS policies

### Step 2 — Configure the Watcher
Open `sync_to_supabase.py` and update the CONFIG section at the top:
```python
SUPABASE_URL  = "https://your-project.supabase.co"
SUPABASE_KEY  = "your-service-role-key"          # Settings → API → service_role
PRICES_FILE   = r"C:\Users\yourname\OneDrive\...\INVOICE ENTRY MACRO ENABLED_DASHBOARD_COPY.xlsx"
REORDER_FILE  = r"C:\Users\yourname\OneDrive\...\ORDER SHEET.xlsx"
```

> ⚠️ Use the **service role key** (not anon key) for the watcher — it needs write access.

### Step 3 — Run the Watcher
```bash
py -3.11 sync_to_supabase.py
```
The watcher performs a full sync on startup, then watches for file changes automatically. Only one machine needs to run the watcher at a time.

### Step 4 — Auto-start on Boot (optional)
To run the watcher silently on startup without a terminal window:
1. Create a `start_watcher.bat` file pointing to `sync_to_supabase.py`
2. Open **Task Scheduler** → Create Basic Task → trigger: **When I log on**
3. Set the action program to `pythonw.exe` (find path with `where pythonw`)
4. Set arguments to `sync_to_supabase.py` and start-in to the folder path

### Step 5 — Deploy the Dashboard
1. Push this repo to GitHub
2. Connect the repo to [Streamlit Cloud](https://streamlit.io/cloud)
3. In Streamlit Cloud → App settings → **Secrets**, add:
```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-public-key"             # Settings → API → anon public
```

---

## 🔌 VBA Macro (Excel)

The watcher detects changes to the `.xlsx` copy of the macro-enabled workbook. The VBA macro in `ThisWorkbook` auto-saves this copy whenever you save the `.xlsm` file.

To install: open the `.xlsm` file → press `Alt + F11` → double-click **ThisWorkbook** → paste the macro below → update `savePath` to match your local folder → save.

```vb
Private Sub Workbook_AfterSave(ByVal Success As Boolean)
    If Not Success Then Exit Sub

    Dim savePath As String
    savePath = "C:\Users\yourname\OneDrive\...\INVOICE ENTRY MACRO ENABLED_DASHBOARD_COPY.xlsx"

    Application.DisplayAlerts = False
    On Error GoTo SaveError
    ThisWorkbook.SaveCopyAs Filename:=savePath
    On Error GoTo 0
    Application.DisplayAlerts = True

    Application.StatusBar = "Dashboard copy saved: " & savePath
    Application.Wait Now + TimeValue("00:00:03")
    Application.StatusBar = False
    Exit Sub

SaveError:
    Application.DisplayAlerts = True
    MsgBox "Could not save dashboard copy." & vbNewLine & _
           "Error: " & Err.Description & vbNewLine & vbNewLine & _
           "Check the savePath in the macro matches your local folder.", _
           vbExclamation, "Dashboard Copy Failed"
End Sub
```

> ⚠️ Make sure macros are **enabled** when Excel opens the file. The `savePath` must match the `PRICES_FILE` path in `sync_to_supabase.py`.

---

## 🔄 Data Flow

```
Excel .xlsm (edited & saved)
        ↓  VBA macro
Excel .xlsx copy (local OneDrive folder)
        ↓  sync_to_supabase.py (file watcher)
Supabase tables (existing_prices, re_order)
        ↓  app.py queries
Streamlit Cloud dashboard
```

---

## 💡 Notes

- The watcher uses the **service role key** — never expose this in the dashboard or commit it to GitHub
- The dashboard uses the **anon key** — safe for read-only public access via Streamlit secrets
- Supabase database queries are free and incur **zero Storage egress costs**
- Data auto-refreshes every 5 minutes on the dashboard; click **Refresh Data** to reload immediately
