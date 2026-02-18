# ==========================================================
# Dynamic Product Search Dashboard
# Lowest Price = LOWEST PIECE COST (Pc. Cost)
# Includes STOCK and USAGE from RE ORDER sheet
# Search by Name OR Last 5 Digits of Barcode
# Only shows items WITH barcodes
# ==========================================================

import streamlit as st
import pandas as pd
from openpyxl import load_workbook

st.set_page_config(
    page_title="Dynamic Product Search",
    layout="wide"
)

# ==========================================================
# GLOBAL BIG FONT CSS (EVERYTHING BIGGER!)
# ==========================================================
st.markdown("""
<style>

/* ---------- METRICS ---------- */
[data-testid="stMetricValue"] {
    font-size: 42px !important;
    font-weight: 600 !important;
}

[data-testid="stMetricLabel"] {
    font-size: 26px !important;
    font-weight: 600 !important;
}

/* ---------- TABLE HEADER ---------- */
[data-testid="stDataFrame"] thead tr th {
    font-size: 20px !important;
    font-weight: 700 !important;
    padding: 16px 12px !important;
}

/* ---------- TABLE BODY ---------- */
[data-testid="stDataFrame"] tbody tr td {
    font-size: 20px !important;
    padding: 16px 12px !important;
    font-weight: 500 !important;
}

/* ---------- FORCE ALL TABLE TEXT BIG ---------- */
[data-testid="stDataFrame"],
[data-testid="stDataFrame"] *,
div[data-testid="stDataFrame"] div[role="grid"],
div[data-testid="stDataFrame"] div[role="grid"] * {
    font-size: 20px !important;
}

/* Remove extra blank column spacing */
[data-testid="stDataFrame"] > div {
    overflow: auto !important;
}

/* ---------- BUTTON TEXT ---------- */
button[kind="secondary"] p {
    font-weight: 700 !important;
    font-size: 16px !important;
}

</style>
""", unsafe_allow_html=True)

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

def is_yellow_background(fill):
    """Check if cell has yellow-ish background color"""
    try:
        if fill and fill.patternType == 'solid':
            if fill.fgColor:
                # Try to get RGB value
                rgb = None
                
                # Check if it's a string (hex format)
                if hasattr(fill.fgColor, 'rgb') and isinstance(fill.fgColor.rgb, str):
                    rgb = fill.fgColor.rgb
                # Check if it has RGB attributes directly
                elif hasattr(fill.fgColor, 'rgb'):
                    # Try to convert RGB object to string
                    try:
                        rgb = str(fill.fgColor.rgb)
                    except:
                        pass
                
                # Also check indexed colors (common for yellow highlighting)
                if hasattr(fill.fgColor, 'index') and fill.fgColor.index:
                    # Index 6 is typically yellow in Excel
                    if fill.fgColor.index in [6, 13, 27, 43]:  # Various yellow indices
                        return True
                
                # If we got an RGB value, check if it's yellowish
                if rgb and isinstance(rgb, str) and len(rgb) >= 6:
                    # Remove 'FF' prefix if present (ARGB format)
                    if len(rgb) == 8:
                        rgb = rgb[2:]
                    
                    try:
                        r = int(rgb[0:2], 16)
                        g = int(rgb[2:4], 16)
                        b = int(rgb[4:6], 16)
                        # Yellow if R and G are high (>200) and B is low (<150)
                        return r > 200 and g > 200 and b < 150
                    except:
                        pass
    except Exception as e:
        pass
    
    return False

@st.cache_data
def load_prices_data(file):
    """Load EXISTING PRICES sheet"""
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
    df["SUPPLIER"] = df["SUPPLIER"].astype(str).str.strip()
    df["Size"] = df["Size"].astype(str).str.strip()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")

    # Clean BARCODE column
    if "BARCODE" in df.columns:
        df["BARCODE"] = df["BARCODE"].astype(str).str.strip()
        
        # *** FILTER OUT ITEMS WITHOUT BARCODE ***
        # Remove rows where BARCODE is NaN, empty string, or 'nan'
        df = df[
            df["BARCODE"].notna() & 
            (df["BARCODE"] != "") & 
            (df["BARCODE"].str.lower() != "nan")
        ]
    else:
        raise ValueError("BARCODE column is required but not found in EXISTING PRICES sheet")

    # Clean AISLE column if it exists
    if "AISLE" in df.columns:
        df["AISLE"] = df["AISLE"].astype(str).str.strip()

    # Convert Piece Cost to numeric
    if "Pc. Cost" in df.columns:
        df["Pc. Cost"] = pd.to_numeric(df["Pc. Cost"], errors="coerce")

    # BARCODE is now REQUIRED, so remove it from blank exceptions
    columns_that_can_be_blank = ["ITEM NUM", "Markup", "AISLE", "STOCK LOCATION", "SUPP"]
    columns_to_check = [col for col in df.columns if col not in columns_that_can_be_blank]

    df = df.dropna(subset=columns_to_check)

    drop_cols = ["Markup", "STOCK LOCATION", "SUPP"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    return df

@st.cache_data
def load_reorder_data(file):
    """Load RE ORDER sheet and extract yellow PLU CODE rows with STOCK and USAGE"""
    
    try:
        # Load workbook with openpyxl to access cell formatting
        wb = load_workbook(file, data_only=True)
        
        if SHEET_NAME_REORDER not in wb.sheetnames:
            st.warning(f"Sheet '{SHEET_NAME_REORDER}' not found in RE ORDER workbook. STOCK and USAGE will be empty.")
            return pd.DataFrame(columns=["PLU CODE", "STOCK", "USAGE"])
        
        ws = wb[SHEET_NAME_REORDER]
        
        # Find column indices (headers are in row 2)
        header_row = 2
        headers = {}
        for cell in ws[header_row]:
            if cell.value:
                col_name = str(cell.value).strip().upper()
                headers[col_name] = cell.column
        
        # Get column index for PLU CODE (should be column B = 2)
        plu_col = headers.get("PLU CODE", 2)  # Default to column B
        stock_col = 5  # Column E
        usage_col = 15  # Column O
        
        # Extract yellow PLU CODE rows (first occurrence only)
        yellow_data = {}
        
        # Start from row 3 (after header row 2)
        for row in range(3, ws.max_row + 1):
            plu_cell = ws.cell(row=row, column=plu_col)
            
            # Check if PLU CODE cell has yellow background
            if plu_cell.fill and is_yellow_background(plu_cell.fill):
                plu_code = str(plu_cell.value).strip() if plu_cell.value else None
                
                if plu_code and plu_code != 'None' and plu_code not in yellow_data:  # First occurrence only
                    stock_value = ws.cell(row=row, column=stock_col).value
                    usage_value = ws.cell(row=row, column=usage_col).value
                    
                    yellow_data[plu_code] = {
                        "STOCK": stock_value if stock_value is not None else "",
                        "USAGE": usage_value if usage_value is not None else ""
                    }
        
        # Convert to DataFrame
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
# LOAD DATA
# ==========================================================
df_prices = load_prices_data(prices_file)

# Load RE ORDER data if file is uploaded
if reorder_file is not None:
    df_reorder = load_reorder_data(reorder_file)
    
    # Merge with prices data (BARCODE = PLU CODE)
    if "BARCODE" in df_prices.columns and not df_reorder.empty:
        df = df_prices.merge(
            df_reorder,
            left_on="BARCODE",
            right_on="PLU CODE",
            how="left"
        )
        # Drop the duplicate PLU CODE column
        df = df.drop(columns=["PLU CODE"], errors="ignore")
    else:
        # Add empty STOCK and USAGE columns
        df = df_prices.copy()
        df["STOCK"] = ""
        df["USAGE"] = ""
else:
    # No RE ORDER file uploaded - add empty columns
    df = df_prices.copy()
    df["STOCK"] = ""
    df["USAGE"] = ""
    st.info("📦 Upload RE ORDER workbook to see STOCK and USAGE data.")

# ==========================================================
# SESSION STATE
# ==========================================================
if 'clear_counter' not in st.session_state:
    st.session_state.clear_counter = 0

# ==========================================================
# SEARCH - BY NAME OR LAST 5 DIGITS OF BARCODE
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
    st.markdown("<div style='padding-top: 6px;'></div>", unsafe_allow_html=True)
    if st.button("🔄 Clear All", type="secondary", use_container_width=True):
        st.session_state.clear_counter += 1
        st.rerun()

if not search_query or len(search_query.strip()) < 3:
    st.stop()

search_query = search_query.strip()

# Search by EITHER Description OR Last 5 Digits of Barcode
# Create a column with last 5 digits of barcode for searching
df["barcode_last5"] = df["BARCODE"].astype(str).str[-5:]

# Search in both Description and last 5 digits of Barcode
filtered_df = df[
    df["Description"].str.lower().str.contains(search_query.lower(), na=False) |
    df["barcode_last5"].str.contains(search_query, na=False)
]

# Drop the temporary column
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

# Price range filter
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
# DISPLAY DATA - NOW WITH STOCK AND USAGE
# ==========================================================
base_display_cols = [
    "BARCODE",
    "ITEM NUM",
    "Description",
    "Size",
    "Pack",
    "Price",
    "Pc. Cost",
    "Sell Price",
    "SUPPLIER",
    "AISLE",
    "STOCK",
    "USAGE"
]

display_cols = [col for col in base_display_cols if col in filtered_df.columns]

sort_column = "Pc. Cost" if "Pc. Cost" in filtered_df.columns else "Price"

final_df = (
    filtered_df[display_cols]
    .sort_values(sort_column)
    .reset_index(drop=True)
)

# ==========================================================
# METRICS
# ==========================================================
st.markdown("---")

colA, colB, colC = st.columns(3)

colA.metric("Total Items", len(final_df))
colB.metric("Suppliers", final_df["SUPPLIER"].nunique())

if "Pc. Cost" in final_df.columns and not final_df["Pc. Cost"].dropna().empty:
    lowest_piece_cost = final_df["Pc. Cost"].min()
    colC.metric("Lowest Price", f"${lowest_piece_cost:,.3f}")
else:
    colC.metric("Lowest Price", "N/A")

# ==========================================================
# TABLE
# ==========================================================
st.dataframe(
    final_df,
    hide_index=True,
    height=600
)

# ==========================================================
# DOWNLOAD
# ==========================================================
st.download_button(
    "Download Filtered Results",
    data=final_df.to_csv(index=False),
    file_name=f"{search_query}_filtered_results.csv",
    mime="text/csv"
)
