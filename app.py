# ==========================================================
# Dynamic Product Search Dashboard
# Lowest Price = LOWEST PIECE COST (Pc. Cost)
# Includes STOCK and USAGE from RE ORDER sheet
# Search by Name OR Last 5 Digits of Barcode
# Only shows items WITH barcodes
# Counts STOCK/USAGE once per unique barcode
# Shows items to be ordered (uncolored in RE ORDER sheet)
# Table indices start from 1
# Columns: PLU CODE, DESCRIPTION, COST, GROUP, PRICE 1, STOCK, USAGE
# Category & Supplier filters parsed from GROUP column
# ==========================================================

import streamlit as st
import pandas as pd
import re
from openpyxl import load_workbook
from pathlib import Path

st.set_page_config(
    page_title="Dynamic Product Search",
    layout="wide"
)

# ==========================================================
# LOAD CUSTOM CSS
# ==========================================================
def load_css():
    css_file = Path(__file__).parent / "styles.css"
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    else:
        st.warning("CSS file not found. Using default styling.")

load_css()

st.title("🔍 Product Search & Supplier View")

# ==========================================================
# TWO FILE UPLOADERS
# ==========================================================
col_upload1, col_upload2 = st.columns(2)

with col_upload1:
    st.markdown("#### 📊 Upload EXISTING PRICES Workbook")
    prices_file = st.file_uploader(
        "EXISTING PRICES",
        type=["xlsx", "xlsm"],
        label_visibility="collapsed",
        key="prices_uploader"
    )

with col_upload2:
    st.markdown("#### 📦 Upload RE ORDER Workbook")
    reorder_file = st.file_uploader(
        "RE ORDER",
        type=["xlsx", "xlsm"],
        label_visibility="collapsed",
        key="reorder_uploader"
    )

if prices_file is None:
    st.info("📊 Please upload the EXISTING PRICES workbook to begin.")
    st.stop()

SHEET_NAME_PRICES = "EXISTING PRICES"
SHEET_NAME_REORDER = "RE ORDER"

# ==========================================================
# COLOR DETECTION HELPERS
# ==========================================================
def is_yellow_background(fill):
    try:
        if fill and fill.patternType == 'solid':
            if fill.fgColor:
                rgb = None
                if hasattr(fill.fgColor, 'rgb') and isinstance(fill.fgColor.rgb, str):
                    rgb = fill.fgColor.rgb
                elif hasattr(fill.fgColor, 'rgb'):
                    try:
                        rgb = str(fill.fgColor.rgb)
                    except:
                        pass
                if hasattr(fill.fgColor, 'index') and fill.fgColor.index:
                    if fill.fgColor.index in [6, 13, 27, 43]:
                        return True
                if rgb and isinstance(rgb, str) and len(rgb) >= 6:
                    if len(rgb) == 8:
                        rgb = rgb[2:]
                    try:
                        r = int(rgb[0:2], 16)
                        g = int(rgb[2:4], 16)
                        b = int(rgb[4:6], 16)
                        return r > 200 and g > 200 and b < 150
                    except:
                        pass
    except:
        pass
    return False

def is_blue_background(fill):
    try:
        if fill and fill.patternType == 'solid':
            if fill.fgColor:
                rgb = None
                if hasattr(fill.fgColor, 'rgb') and isinstance(fill.fgColor.rgb, str):
                    rgb = fill.fgColor.rgb
                elif hasattr(fill.fgColor, 'rgb'):
                    try:
                        rgb = str(fill.fgColor.rgb)
                    except:
                        pass
                if hasattr(fill.fgColor, 'index') and fill.fgColor.index:
                    if fill.fgColor.index in [5, 12, 25, 41]:
                        return True
                if rgb and isinstance(rgb, str) and len(rgb) >= 6:
                    if len(rgb) == 8:
                        rgb = rgb[2:]
                    try:
                        r = int(rgb[0:2], 16)
                        g = int(rgb[2:4], 16)
                        b = int(rgb[4:6], 16)
                        return b > 200 and r < 150 and g < 150
                    except:
                        pass
    except:
        pass
    return False

def is_colored(fill):
    if not fill or fill.patternType != 'solid':
        return False
    if is_yellow_background(fill) or is_blue_background(fill):
        return True
    if fill.fgColor:
        if hasattr(fill.fgColor, 'index') and fill.fgColor.index:
            return True
        if hasattr(fill.fgColor, 'rgb'):
            try:
                rgb = fill.fgColor.rgb if isinstance(fill.fgColor.rgb, str) else str(fill.fgColor.rgb)
                if rgb and rgb not in ['00000000', 'FFFFFFFF', 'ffffffff', '00FFFFFF']:
                    return True
            except:
                pass
    return False

# ==========================================================
# PARSE GROUP COLUMN  →  CATEGORY & SUPPLIERS
# Format: [CATEGORY][SUPPLIER 1][SUPPLIER 2]
# ==========================================================
def parse_group(group_str):
    """Return (category, suppliers_list) from a GROUP cell value."""
    if not group_str or str(group_str).strip() in ['', 'nan', 'None']:
        return "", []
    parts = re.findall(r'\[([^\]]+)\]', str(group_str))
    if not parts:
        return str(group_str).strip(), []
    category = parts[0].strip()
    suppliers = [p.strip() for p in parts[1:] if p.strip()]
    return category, suppliers

# ==========================================================
# LOAD EXISTING PRICES
# ==========================================================
@st.cache_data
def load_prices_data(file):
    xls = pd.ExcelFile(file)
    if SHEET_NAME_PRICES not in xls.sheet_names:
        raise ValueError(
            f'Sheet "{SHEET_NAME_PRICES}" not found.\n'
            f"Available sheets: {', '.join(xls.sheet_names)}"
        )
    df = pd.read_excel(xls, sheet_name=SHEET_NAME_PRICES, engine="openpyxl")
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]

    if "SUPPLIER" not in df.columns:
        for col in df.columns:
            if col.upper() in ["SUPPLIER", "SUPP"]:
                df = df.rename(columns={col: "SUPPLIER"})
                break

    required_cols = ["Description", "SUPPLIER", "Size", "Price"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}")

    df["Description"] = df["Description"].astype(str).str.strip()
    df["SUPPLIER"]    = df["SUPPLIER"].astype(str).str.strip()
    df["Size"]        = df["Size"].astype(str).str.strip()
    df["Price"]       = pd.to_numeric(df["Price"], errors="coerce")

    if "BARCODE" in df.columns:
        df["BARCODE"] = df["BARCODE"].astype(str).str.strip()
        df = df[
            df["BARCODE"].notna() &
            (df["BARCODE"] != "") &
            (df["BARCODE"].str.lower() != "nan")
        ]
    else:
        raise ValueError("BARCODE column is required but not found in EXISTING PRICES sheet")

    if "AISLE" in df.columns:
        df["AISLE"] = df["AISLE"].astype(str).str.strip()

    if "Pc. Cost" in df.columns:
        df["Pc. Cost"] = pd.to_numeric(df["Pc. Cost"], errors="coerce")

    columns_that_can_be_blank = ["ITEM NUM", "Markup", "AISLE", "STOCK LOCATION", "SUPP"]
    columns_to_check = [col for col in df.columns if col not in columns_that_can_be_blank]
    df = df.dropna(subset=columns_to_check)

    drop_cols = ["Markup", "STOCK LOCATION", "SUPP"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    return df

# ==========================================================
# LOAD RE ORDER — STOCK & USAGE (yellow rows)
# ==========================================================
@st.cache_data
def load_reorder_data(file):
    try:
        wb = load_workbook(file, data_only=True)
        if SHEET_NAME_REORDER not in wb.sheetnames:
            st.warning(f"Sheet '{SHEET_NAME_REORDER}' not found. STOCK and USAGE will be empty.")
            return pd.DataFrame(columns=["PLU CODE", "STOCK", "USAGE"])

        ws = wb[SHEET_NAME_REORDER]
        header_row = 2
        headers = {}
        for cell in ws[header_row]:
            if cell.value:
                headers[str(cell.value).strip().upper()] = cell.column

        plu_col   = headers.get("PLU CODE", 2)
        stock_col = 5    # Column E
        usage_col = 15   # Column O

        yellow_data = {}
        for row in range(3, ws.max_row + 1):
            plu_cell = ws.cell(row=row, column=plu_col)
            if plu_cell.fill and is_yellow_background(plu_cell.fill):
                plu_code = str(plu_cell.value).strip() if plu_cell.value else None
                if plu_code and plu_code != 'None' and plu_code not in yellow_data:
                    stock_value = ws.cell(row=row, column=stock_col).value
                    usage_value = ws.cell(row=row, column=usage_col).value
                    yellow_data[plu_code] = {
                        "STOCK": stock_value if stock_value is not None else "",
                        "USAGE": usage_value if usage_value is not None else ""
                    }

        df_reorder = pd.DataFrame([
            {"PLU CODE": plu, "STOCK": data["STOCK"], "USAGE": data["USAGE"]}
            for plu, data in yellow_data.items()
        ])
        st.success(f"✅ Loaded {len(df_reorder)} items with yellow PLU codes from RE ORDER sheet")
        return df_reorder

    except Exception as e:
        st.warning(f"Error reading RE ORDER sheet: {str(e)}. STOCK and USAGE will be empty.")
        return pd.DataFrame(columns=["PLU CODE", "STOCK", "USAGE"])

# ==========================================================
# LOAD UNORDERED ITEMS (uncolored rows) — NOW WITH COST, GROUP, PRICE 1
# Columns used:
#   A = DESCRIPTION  (col 1)
#   B = PLU CODE     (col 2)
#   C = COST         (col 3)
#   D = GROUP        (col 4)
#   E = STOCK        (col 5)
#   F = PRICE 1      (col 6)
#   O = USAGE        (col 15)
# ==========================================================
@st.cache_data
def load_unordered_items(file):
    try:
        wb = load_workbook(file, data_only=True)
        if SHEET_NAME_REORDER not in wb.sheetnames:
            return pd.DataFrame(columns=["PLU CODE", "DESCRIPTION", "COST", "GROUP", "PRICE 1", "STOCK", "USAGE"])

        ws = wb[SHEET_NAME_REORDER]
        header_row = 2
        headers = {}
        for cell in ws[header_row]:
            if cell.value:
                headers[str(cell.value).strip().upper()] = cell.column

        plu_col    = headers.get("PLU CODE",  2)
        desc_col   = headers.get("DESCRIPTION", 1)
        cost_col   = headers.get("COST",       3)   # Column C
        group_col  = headers.get("GROUP",      4)   # Column D
        stock_col  = headers.get("STO",        5)   # Column E  (header may be truncated)
        price1_col = headers.get("PRICE 1",    6)   # Column F
        usage_col  = 15                              # Column O  (USAGE / weekly usage)

        # Also check alternate header names for STOCK
        if "STOCK" in headers:
            stock_col = headers["STOCK"]
        elif "STO" in headers:
            stock_col = headers["STO"]

        # Also check alternate header name for PRICE 1
        if "PRICE 1" in headers:
            price1_col = headers["PRICE 1"]
        elif "PRICE1" in headers:
            price1_col = headers["PRICE1"]
        elif "PRI" in headers:
            price1_col = headers["PRI"]

        unordered_data = {}
        for row in range(3, ws.max_row + 1):
            plu_cell = ws.cell(row=row, column=plu_col)
            if not is_colored(plu_cell.fill):
                plu_code = str(plu_cell.value).strip() if plu_cell.value else None
                if plu_code and plu_code != 'None' and plu_code not in unordered_data:
                    desc_value   = ws.cell(row=row, column=desc_col).value
                    cost_value   = ws.cell(row=row, column=cost_col).value
                    group_value  = ws.cell(row=row, column=group_col).value
                    stock_value  = ws.cell(row=row, column=stock_col).value
                    price1_value = ws.cell(row=row, column=price1_col).value
                    usage_value  = ws.cell(row=row, column=usage_col).value

                    unordered_data[plu_code] = {
                        "DESCRIPTION": str(desc_value).strip() if desc_value else "",
                        "COST":        cost_value  if cost_value  is not None else "",
                        "GROUP":       str(group_value).strip() if group_value else "",
                        "PRICE 1":     price1_value if price1_value is not None else "",
                        "STOCK":       stock_value  if stock_value  is not None else 0,
                        "USAGE":       usage_value  if usage_value  is not None else 0,
                    }

        df_unordered = pd.DataFrame([
            {
                "PLU CODE":    plu,
                "DESCRIPTION": data["DESCRIPTION"],
                "COST":        data["COST"],
                "GROUP":       data["GROUP"],
                "PRICE 1":     data["PRICE 1"],
                "STOCK":       data["STOCK"],
                "USAGE":       data["USAGE"],
            }
            for plu, data in unordered_data.items()
        ])

        # Parse CATEGORY and SUPPLIER(S) from GROUP
        parsed = df_unordered["GROUP"].apply(parse_group)
        df_unordered["CATEGORY"]  = parsed.apply(lambda x: x[0])
        df_unordered["SUPPLIERS"] = parsed.apply(lambda x: x[1])  # list

        return df_unordered

    except Exception as e:
        st.warning(f"Error reading unordered items: {str(e)}")
        return pd.DataFrame(columns=["PLU CODE", "DESCRIPTION", "COST", "GROUP", "PRICE 1", "STOCK", "USAGE", "CATEGORY", "SUPPLIERS"])

# ==========================================================
# LOAD DATA
# ==========================================================
df_prices = load_prices_data(prices_file)

if reorder_file is not None:
    df_reorder   = load_reorder_data(reorder_file)
    df_unordered = load_unordered_items(reorder_file)

    if "BARCODE" in df_prices.columns and not df_reorder.empty:
        df = df_prices.merge(
            df_reorder,
            left_on="BARCODE",
            right_on="PLU CODE",
            how="left"
        )
        df = df.drop(columns=["PLU CODE"], errors="ignore")
    else:
        df = df_prices.copy()
        df["STOCK"] = ""
        df["USAGE"] = ""
else:
    df = df_prices.copy()
    df["STOCK"] = ""
    df["USAGE"] = ""
    df_unordered = pd.DataFrame(
        columns=["PLU CODE", "DESCRIPTION", "COST", "GROUP", "PRICE 1", "STOCK", "USAGE", "CATEGORY", "SUPPLIERS"]
    )
    st.info("📦 Upload RE ORDER workbook to see STOCK and USAGE data.")

# ==========================================================
# SHOW ITEMS TO ORDER — Button + Category + Supplier filters
# ==========================================================
if reorder_file is not None and not df_unordered.empty:
    st.markdown("---")

    # --- Build unique category and supplier lists for dropdowns ---
    all_categories = sorted(df_unordered["CATEGORY"].dropna().unique().tolist())
    all_categories = [c for c in all_categories if c]

    # Flatten all supplier lists
    all_suppliers_raw = []
    for sup_list in df_unordered["SUPPLIERS"]:
        all_suppliers_raw.extend(sup_list)
    all_suppliers = sorted(set(all_suppliers_raw))
    all_suppliers = [s for s in all_suppliers if s]

    # --- Row: [View Items to Order]  [Category dropdown]  [Supplier dropdown] ---
    btn_col, cat_col, sup_col, spacer_col = st.columns([2, 2, 2, 4])

    with btn_col:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("📋 View Items to Order", type="primary", use_container_width=True, key="view_order_btn"):
            st.session_state.show_unordered = not st.session_state.get('show_unordered', False)
        st.markdown("</div>", unsafe_allow_html=True)

    with cat_col:
        selected_category = st.selectbox(
            "Filter by Category",
            options=["All Categories"] + all_categories,
            key="category_filter"
        )

    with sup_col:
        selected_supplier = st.selectbox(
            "Filter by Supplier",
            options=["All Suppliers"] + all_suppliers,
            key="supplier_filter"
        )

    # --- Display table when toggled ---
    if st.session_state.get('show_unordered', False):
        st.markdown("### 📋 Items to Order (Uncolored in RE ORDER sheet)")

        # Apply filters dynamically
        display_df = df_unordered.copy()

        if selected_category != "All Categories":
            display_df = display_df[display_df["CATEGORY"] == selected_category]

        if selected_supplier != "All Suppliers":
            display_df = display_df[
                display_df["SUPPLIERS"].apply(lambda sup_list: selected_supplier in sup_list)
            ]

        st.info(f"Found **{len(display_df)}** items that need to be ordered")

        # Numeric conversions
        display_df["STOCK"]   = pd.to_numeric(display_df["STOCK"],   errors='coerce').fillna(0)
        display_df["USAGE"]   = pd.to_numeric(display_df["USAGE"],   errors='coerce').fillna(0)
        display_df["COST"]    = pd.to_numeric(display_df["COST"],    errors='coerce')
        display_df["PRICE 1"] = pd.to_numeric(display_df["PRICE 1"], errors='coerce')

        # Sort by USAGE descending
        display_df = display_df.sort_values("USAGE", ascending=False).reset_index(drop=True)
        display_df.index = display_df.index + 1

        # Select display columns (drop parsed helper columns)
        show_cols = ["PLU CODE", "DESCRIPTION", "COST", "GROUP", "PRICE 1", "STOCK", "USAGE"]
        show_cols = [c for c in show_cols if c in display_df.columns]

        st.dataframe(
            display_df[show_cols],
            use_container_width=True,
            height=400
        )

        # Download
        st.download_button(
            "📥 Download Items to Order",
            data=display_df[show_cols].to_csv(index=True),
            file_name="items_to_order.csv",
            mime="text/csv"
        )

        st.markdown("---")

# ==========================================================
# SESSION STATE
# ==========================================================
if 'clear_counter' not in st.session_state:
    st.session_state.clear_counter = 0

# ==========================================================
# SEARCH — BY NAME OR LAST 5 DIGITS OF BARCODE
# ==========================================================
st.markdown("### 🔎 Search Product (min 3 letters or last 5 digits of barcode)")

search_col, button_col = st.columns([6, 1])

with search_col:
    search_query = st.text_input(
        "Search product",
        placeholder="e.g. cumin OR 12345 (last 5 digits of barcode)",
        label_visibility="collapsed",
        key=f"search_input_{st.session_state.clear_counter}"
    )

with button_col:
    if st.button("🔄 Clear All", type="secondary", use_container_width=True, key="clear_button"):
        st.session_state.clear_counter += 1
        st.rerun()

if not search_query or len(search_query.strip()) < 3:
    st.stop()

search_query = search_query.strip()

df["barcode_last5"] = df["BARCODE"].astype(str).str[-5:]
filtered_df = df[
    df["Description"].str.lower().str.contains(search_query.lower(), na=False) |
    df["barcode_last5"].str.contains(search_query, na=False)
]
filtered_df = filtered_df.drop(columns=["barcode_last5"])

if filtered_df.empty:
    st.warning("No matching products found.")
    st.stop()

st.markdown(f"### Results for '{search_query}'")

# ==========================================================
# FILTERS
# ==========================================================
col1, col2, col3, col4 = st.columns(4)

desc_filter = col1.text_input(
    "Filter Description (e.g. powder, whole)",
    key=f"desc_filter_{st.session_state.clear_counter}"
)
if desc_filter:
    filtered_df = filtered_df[
        filtered_df["Description"].str.lower().str.contains(desc_filter.lower(), na=False)
    ]

if not filtered_df.empty and "Size" in filtered_df.columns:
    sizes = sorted(filtered_df["Size"].unique())
    selected_sizes = col2.multiselect(
        "Filter Size",
        sizes,
        key=f"size_filter_{st.session_state.clear_counter}"
    )
    if selected_sizes:
        filtered_df = filtered_df[filtered_df["Size"].isin(selected_sizes)]

if not filtered_df.empty and "SUPPLIER" in filtered_df.columns:
    suppliers = sorted(filtered_df["SUPPLIER"].unique())
    selected_suppliers = col3.multiselect(
        "Filter Supplier",
        suppliers,
        key=f"supplier_filter_{st.session_state.clear_counter}"
    )
    if selected_suppliers:
        filtered_df = filtered_df[filtered_df["SUPPLIER"].isin(selected_suppliers)]

if filtered_df.empty:
    st.warning("No items match your filters.")
    st.stop()

valid_prices = filtered_df["Price"].dropna()
min_price = float(valid_prices.min())
max_price = float(valid_prices.max())

if min_price != max_price:
    price_range = col4.slider(
        "Price Range",
        min_value=min_price,
        max_value=max_price,
        value=(min_price, max_price),
        key=f"price_slider_{st.session_state.clear_counter}"
    )
    filtered_df = filtered_df[
        (filtered_df["Price"] >= price_range[0]) &
        (filtered_df["Price"] <= price_range[1])
    ]

if filtered_df.empty:
    st.warning("No items match all selected filters.")
    st.stop()

# ==========================================================
# DISPLAY DATA
# ==========================================================
base_display_cols = [
    "BARCODE", "ITEM NUM", "Description", "Size", "Pack",
    "Price", "Pc. Cost", "Sell Price", "SUPPLIER", "AISLE", "STOCK", "USAGE"
]
display_cols = [col for col in base_display_cols if col in filtered_df.columns]
sort_column  = "Pc. Cost" if "Pc. Cost" in filtered_df.columns else "Price"

final_df = (
    filtered_df[display_cols]
    .sort_values(sort_column)
    .reset_index(drop=True)
)
final_df.index = final_df.index + 1

# ==========================================================
# METRICS
# ==========================================================
st.markdown("---")
colA, colB, colC, colD, colE = st.columns(5)

colA.metric("Total Items", len(final_df))
colB.metric("Suppliers", final_df["SUPPLIER"].nunique())

if "Pc. Cost" in final_df.columns and not final_df["Pc. Cost"].dropna().empty:
    colC.metric("Lowest Price", f"${final_df['Pc. Cost'].min():,.3f}")
else:
    colC.metric("Lowest Price", "N/A")

if "STOCK" in final_df.columns and "BARCODE" in final_df.columns:
    unique_stock  = final_df.groupby("BARCODE")["STOCK"].first()
    total_stock   = pd.to_numeric(unique_stock, errors="coerce").fillna(0).sum()
    colD.metric("Total Stock", f"{total_stock:,.0f}")
else:
    colD.metric("Total Stock", "N/A")

if "USAGE" in final_df.columns and "BARCODE" in final_df.columns:
    unique_usage  = final_df.groupby("BARCODE")["USAGE"].first()
    total_usage   = pd.to_numeric(unique_usage, errors="coerce").fillna(0).sum()
    colE.metric("Total Usage", f"{total_usage:,.0f}")
else:
    colE.metric("Total Usage", "N/A")

# ==========================================================
# TABLE
# ==========================================================
st.dataframe(
    final_df,
    hide_index=False,
    height=600
)

# ==========================================================
# DOWNLOAD
# ==========================================================
st.download_button(
    "Download Filtered Results",
    data=final_df.to_csv(index=True),
    file_name=f"{search_query}_filtered_results.csv",
    mime="text/csv"
)
