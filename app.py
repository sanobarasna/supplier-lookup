# ==========================================================
# Dynamic Product Search Dashboard
# Lowest Price = LOWEST PIECE COST (Pc. Cost)
# Includes STOCK and USAGE from RE ORDER sheet
# Search by Name OR Last 5 Digits of Barcode
# Only shows items WITH barcodes
# Counts STOCK/USAGE once per unique barcode
# Shows items to be ordered (uncolored in RE ORDER sheet)
# Table indices start from 1
# ==========================================================

import streamlit as st
import pandas as pd
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

def is_blue_background(fill):
    """Check if cell has blue-ish background color"""
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
                
                # Check indexed colors for blue
                if hasattr(fill.fgColor, 'index') and fill.fgColor.index:
                    if fill.fgColor.index in [5, 12, 25, 41]:  # Various blue indices
                        return True
                
                if rgb and isinstance(rgb, str) and len(rgb) >= 6:
                    if len(rgb) == 8:
                        rgb = rgb[2:]
                    
                    try:
                        r = int(rgb[0:2], 16)
                        g = int(rgb[2:4], 16)
                        b = int(rgb[4:6], 16)
                        # Blue if B is high (>200) and R, G are low (<150)
                        return b > 200 and r < 150 and g < 150
                    except:
                        pass
    except:
        pass
    
    return False

def is_colored(fill):
    """Check if cell has any background color"""
    if not fill or fill.patternType != 'solid':
        return False
    
    # Check if it's yellow or blue
    if is_yellow_background(fill) or is_blue_background(fill):
        return True
    
    # Check if fill has any color
    if fill.fgColor:
        if hasattr(fill.fgColor, 'index') and fill.fgColor.index:
            return True
        if hasattr(fill.fgColor, 'rgb'):
            try:
                rgb = fill.fgColor.rgb if isinstance(fill.fgColor.rgb, str) else str(fill.fgColor.rgb)
                # Check if it's not white/no color (FFFFFFFF or 00000000)
                if rgb and rgb not in ['00000000', 'FFFFFFFF', 'ffffffff', '00FFFFFF']:
                    return True
            except:
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

@st.cache_data
def load_unordered_items(file):
    """Load items to be ordered (uncolored PLU CODE rows from RE ORDER sheet)"""
    
    try:
        wb = load_workbook(file, data_only=True)
        
        if SHEET_NAME_REORDER not in wb.sheetnames:
            return pd.DataFrame(columns=["PLU CODE", "DESCRIPTION", "STOCK", "USAGE"])
        
        ws = wb[SHEET_NAME_REORDER]
        
        # Find column indices (headers are in row 2)
        header_row = 2
        headers = {}
        for cell in ws[header_row]:
            if cell.value:
                col_name = str(cell.value).strip().upper()
                headers[col_name] = cell.column
        
        # Get column indices
        plu_col = headers.get("PLU CODE", 2)  # Column B
        desc_col = headers.get("DESCRIPTION", 1)  # Column A
        stock_col = 5  # Column E
        usage_col = 15  # Column O
        
        # Extract UNCOLORED PLU CODE rows
        unordered_data = {}
        
        # Start from row 3 (after header row 2)
        for row in range(3, ws.max_row + 1):
            plu_cell = ws.cell(row=row, column=plu_col)
            
            # Check if PLU CODE cell has NO color
            if not is_colored(plu_cell.fill):
                plu_code = str(plu_cell.value).strip() if plu_cell.value else None
                
                if plu_code and plu_code != 'None' and plu_code not in unordered_data:
                    desc_value = ws.cell(row=row, column=desc_col).value
                    stock_value = ws.cell(row=row, column=stock_col).value
                    usage_value = ws.cell(row=row, column=usage_col).value
                    
                    unordered_data[plu_code] = {
                        "DESCRIPTION": str(desc_value).strip() if desc_value else "",
                        "STOCK": stock_value if stock_value is not None else 0,
                        "USAGE": usage_value if usage_value is not None else 0
                    }
        
        # Convert to DataFrame
        df_unordered = pd.DataFrame([
            {
                "PLU CODE": plu,
                "DESCRIPTION": data["DESCRIPTION"],
                "STOCK": data["STOCK"],
                "USAGE": data["USAGE"]
            }
            for plu, data in unordered_data.items()
        ])
        
        return df_unordered
    
    except Exception as e:
        st.warning(f"Error reading unordered items: {str(e)}")
        return pd.DataFrame(columns=["PLU CODE", "DESCRIPTION", "STOCK", "USAGE"])

# ==========================================================
# LOAD DATA
# ==========================================================
df_prices = load_prices_data(prices_file)

# Load RE ORDER data if file is uploaded
if reorder_file is not None:
    df_reorder = load_reorder_data(reorder_file)
    df_unordered = load_unordered_items(reorder_file)
    
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
    df_unordered = pd.DataFrame(columns=["PLU CODE", "DESCRIPTION", "STOCK", "USAGE"])
    st.info("📦 Upload RE ORDER workbook to see STOCK and USAGE data.")

# ==========================================================
# SHOW ITEMS TO ORDER BUTTON
# ==========================================================
if reorder_file is not None and not df_unordered.empty:
    st.markdown("---")
    if st.button("📋 View Items to Order", type="primary", use_container_width=False):
        st.session_state.show_unordered = not st.session_state.get('show_unordered', False)
    
    if st.session_state.get('show_unordered', False):
        st.markdown("### 📋 Items to Order (Uncolored in RE ORDER sheet)")
        st.info(f"Found **{len(df_unordered)}** items that need to be ordered")
        
        # Convert numeric columns
        df_unordered['STOCK'] = pd.to_numeric(df_unordered['STOCK'], errors='coerce').fillna(0)
        df_unordered['USAGE'] = pd.to_numeric(df_unordered['USAGE'], errors='coerce').fillna(0)
        
        # Sort by USAGE (highest first)
        df_unordered_display = df_unordered.sort_values('USAGE', ascending=False).reset_index(drop=True)
        
        # Reset index to start from 1
        df_unordered_display.index = df_unordered_display.index + 1
        
        st.dataframe(
            df_unordered_display,
            use_container_width=True,
            height=400
        )
        
        # Download button for unordered items
        st.download_button(
            "📥 Download Items to Order",
            data=df_unordered_display.to_csv(index=True),
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
    if st.button("🔄 Clear All", type="secondary", use_container_width=True, key="clear_button"):
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

# Reset index to start from 1
final_df.index = final_df.index + 1

# ==========================================================
# METRICS - COUNTS STOCK/USAGE ONCE PER UNIQUE BARCODE
# ==========================================================
st.markdown("---")

colA, colB, colC, colD, colE = st.columns(5)

# Total Items
colA.metric("Total Items", len(final_df))

# Suppliers
colB.metric("Suppliers", final_df["SUPPLIER"].nunique())

# Lowest Price (Piece Cost)
if "Pc. Cost" in final_df.columns and not final_df["Pc. Cost"].dropna().empty:
    lowest_piece_cost = final_df["Pc. Cost"].min()
    colC.metric("Lowest Price", f"${lowest_piece_cost:,.3f}")
else:
    colC.metric("Lowest Price", "N/A")

# Total Stock - Count each barcode only once
if "STOCK" in final_df.columns and "BARCODE" in final_df.columns:
    # Group by BARCODE and take first occurrence for each barcode
    unique_stock = final_df.groupby("BARCODE")["STOCK"].first()
    stock_numeric = pd.to_numeric(unique_stock, errors="coerce").fillna(0)
    total_stock = stock_numeric.sum()
    colD.metric("Total Stock", f"{total_stock:,.0f}")
else:
    colD.metric("Total Stock", "N/A")

# Total Usage - Count each barcode only once
if "USAGE" in final_df.columns and "BARCODE" in final_df.columns:
    # Group by BARCODE and take first occurrence for each barcode
    unique_usage = final_df.groupby("BARCODE")["USAGE"].first()
    usage_numeric = pd.to_numeric(unique_usage, errors="coerce").fillna(0)
    total_usage = usage_numeric.sum()
    colE.metric("Total Usage", f"{total_usage:,.0f}")
else:
    colE.metric("Total Usage", "N/A")

# ==========================================================
# TABLE
# ==========================================================
st.dataframe(
    final_df,
    hide_index=False,  # Show index starting from 1
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
