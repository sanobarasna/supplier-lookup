# ==========================================================
# Dynamic Product Search Dashboard
# Lists ALL matching items + Column Filters
# Sheet: "EXISTING PRICES"
# ==========================================================

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Dynamic Product Search",
    layout="wide"
)

# Custom CSS for larger font and remove extra cells
st.markdown("""
<style>
    /* Increase font size in dataframe - BIGGER */
    [data-testid="stDataFrame"] {
        font-size: 20px !important;
    }
    
    /* Target the actual data cells - BIGGER */
    [data-testid="stDataFrame"] tbody tr td {
        font-size: 20px !important;
        padding: 12px 8px !important;
    }
    
    /* Target header cells */
    [data-testid="stDataFrame"] thead tr th {
        font-size: 20px !important;
        font-weight: 700 !important;
        padding: 12px 8px !important;
    }
    
    /* Remove extra scrollbar space */
    [data-testid="stDataFrame"] > div {
        overflow: auto !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🔍 Product Search & Supplier View")

uploaded_file = st.file_uploader(
    "Upload Excel Workbook",
    type=["xlsx", "xlsm"],
    label_visibility="collapsed"
)

if uploaded_file is None:
    st.info("Upload workbook to begin.")
    st.stop()

SHEET_NAME = "EXISTING PRICES"

@st.cache_data
def load_data(file):
    xls = pd.ExcelFile(file)

    if SHEET_NAME not in xls.sheet_names:
        raise ValueError(
            f'Sheet "{SHEET_NAME}" not found.\n'
            f"Available sheets: {', '.join(xls.sheet_names)}"
        )

    df = pd.read_excel(xls, sheet_name=SHEET_NAME, engine="openpyxl")
    
    # Clean column names - make them consistent
    df.columns = df.columns.str.strip()

    # Drop unwanted columns (unnamed ones)
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    
    # Check if SUPPLIER column exists, if not, look for variations
    if "SUPPLIER" not in df.columns:
        # Check for common variations
        for col in df.columns:
            if col.upper() == "SUPPLIER" or col.upper() == "SUPP":
                df = df.rename(columns={col: "SUPPLIER"})
                break
    
    # Verify required columns exist
    required_cols = ["Description", "SUPPLIER", "Size", "Price"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Missing required columns: {', '.join(missing_cols)}\nAvailable columns: {', '.join(df.columns)}")
    
    # Clean types
    df["Description"] = df["Description"].astype(str).str.strip()
    df["SUPPLIER"] = df["SUPPLIER"].astype(str).str.strip()
    df["Size"] = df["Size"].astype(str).str.strip()
    df["Price"] = pd.to_numeric(df["Price"], errors="coerce")

    # *** REMOVE ROWS WITH BLANK VALUES ***
    # Exception: ITEM NUM, Markup, AISLE, STOCK LOCATION, SUPP can be blank
    columns_that_can_be_blank = ["ITEM NUM", "Markup", "AISLE", "STOCK LOCATION", "SUPP"]
    
    # Get columns that MUST be filled (all columns except the exceptions)
    columns_to_check = [col for col in df.columns if col not in columns_that_can_be_blank]
    
    # Drop rows where ANY of the required columns have blank values
    df = df.dropna(subset=columns_to_check)

    # NOW drop the unwanted columns AFTER filtering
    drop_cols = ["Markup", "AISLE", "STOCK LOCATION", "SUPP"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    return df


df = load_data(uploaded_file)

# ----------------------------------------------------------
# MAIN SEARCH
# ----------------------------------------------------------
st.markdown("### 🔎 Search Product (min 3 letters)")

search_query = st.text_input(
    "Search product",
    placeholder="e.g. cumin",
    label_visibility="collapsed"
)

if not search_query or len(search_query.strip()) < 3:
    st.stop()

search_query = search_query.lower().strip()

filtered_df = df[df["Description"].str.lower().str.contains(search_query, na=False)]

if filtered_df.empty:
    st.warning("No matching products found.")
    st.stop()

st.markdown(f"### Results for '{search_query}'")

# ----------------------------------------------------------
# COLUMN FILTERS
# ----------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

# Description keyword filter
desc_filter = col1.text_input("Filter Description (e.g. powder, whole)")

if desc_filter:
    filtered_df = filtered_df[
        filtered_df["Description"].str.lower().str.contains(desc_filter.lower(), na=False)
    ]

# Size filter
if not filtered_df.empty and "Size" in filtered_df.columns:
    sizes = sorted(filtered_df["Size"].unique())
    selected_sizes = col2.multiselect("Filter Size", sizes)

    if selected_sizes:
        filtered_df = filtered_df[filtered_df["Size"].isin(selected_sizes)]

# Supplier filter
if not filtered_df.empty and "SUPPLIER" in filtered_df.columns:
    suppliers = sorted(filtered_df["SUPPLIER"].unique())
    selected_suppliers = col3.multiselect("Filter Supplier", suppliers)

    if selected_suppliers:
        filtered_df = filtered_df[filtered_df["SUPPLIER"].isin(selected_suppliers)]

# Price range filter - WITH PROPER ERROR HANDLING
if filtered_df.empty:
    col4.warning("No items match your filters")
    st.stop()
else:
    # Get valid prices
    valid_prices = filtered_df["Price"].dropna()
    
    if valid_prices.empty:
        col4.error("No valid price data available")
        st.stop()
    
    min_price = float(valid_prices.min())
    max_price = float(valid_prices.max())
    
    # Check for NaN values explicitly
    if pd.isna(min_price) or pd.isna(max_price):
        col4.error("Invalid price data detected")
        st.stop()
    
    if min_price == max_price:
        col4.info(f"Only one price available: ${min_price:,.2f}")
        price_range = (min_price, max_price)
    else:
        price_range = col4.slider(
            "Price Range",
            min_value=min_price,
            max_value=max_price,
            value=(min_price, max_price)
        )

    # Apply price filter
    filtered_df = filtered_df[
        (filtered_df["Price"] >= price_range[0]) &
        (filtered_df["Price"] <= price_range[1])
    ]

# Final check after all filters
if filtered_df.empty:
    st.warning("No items match all selected filters.")
    st.stop()

# ----------------------------------------------------------
# CLEAN DISPLAY COLUMNS
# ----------------------------------------------------------
# Only include columns that actually exist
base_display_cols = [
    "BARCODE",
    "ITEM NUM",
    "Description",
    "Size",
    "Pack",
    "Price",
    "Pc. Cost",
    "Sell Price",
    "SUPPLIER"
]

display_cols = [col for col in base_display_cols if col in filtered_df.columns]

final_df = filtered_df[display_cols].sort_values("Price").reset_index(drop=True)

# ----------------------------------------------------------
# METRICS
# ----------------------------------------------------------
st.markdown("---")

colA, colB, colC = st.columns(3)
colA.metric("Total Items", len(final_df))

if "SUPPLIER" in final_df.columns:
    colB.metric("Suppliers", final_df["SUPPLIER"].nunique())
else:
    colB.metric("Suppliers", "N/A")

colC.metric("Lowest Price", f"${final_df['Price'].min():,.2f}")

# ----------------------------------------------------------
# DISPLAY TABLE WITH AUTO-SIZED COLUMNS
# ----------------------------------------------------------
# Configure column widths to auto-fit content
column_config = {
    "BARCODE": st.column_config.TextColumn(
        "BARCODE",
        width="medium",
    ),
    "ITEM NUM": st.column_config.TextColumn(
        "ITEM NUM",
        width="small",
    ),
    "Description": st.column_config.TextColumn(
        "Description",
        width="large",
    ),
    "Size": st.column_config.TextColumn(
        "Size",
        width="small",
    ),
    "Pack": st.column_config.NumberColumn(
        "Pack",
        width="small",
    ),
    "Price": st.column_config.NumberColumn(
        "Price",
        format="$%.2f",
        width="small",
    ),
    "Pc. Cost": st.column_config.NumberColumn(
        "Pc. Cost",
        format="%.4f",
        width="small",
    ),
    "Sell Price": st.column_config.NumberColumn(
        "Sell Price",
        format="%.2f",
        width="small",
    ),
    "SUPPLIER": st.column_config.TextColumn(
        "SUPPLIER",
        width="medium",
    ),
}

# Display with auto-width (no use_container_width to prevent extra cells)
st.dataframe(
    final_df,
    column_config=column_config,
    hide_index=True,
    height=500
)

# ----------------------------------------------------------
# DOWNLOAD
# ----------------------------------------------------------
st.download_button(
    "Download Filtered Results",
    data=final_df.to_csv(index=False),
    file_name=f"{search_query}_filtered_results.csv",
    mime="text/csv"
)

