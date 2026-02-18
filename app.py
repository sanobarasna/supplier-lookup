# ==========================================================
# Dynamic Product Search Dashboard
# Lowest Price = LOWEST PIECE COST (Pc. Cost)
# Sheet: "EXISTING PRICES"
# ==========================================================

import streamlit as st
import pandas as pd

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

    # Clean AISLE column if it exists
    if "AISLE" in df.columns:
        df["AISLE"] = df["AISLE"].astype(str).str.strip()

    # Convert Piece Cost to numeric
    if "Pc. Cost" in df.columns:
        df["Pc. Cost"] = pd.to_numeric(df["Pc. Cost"], errors="coerce")

    # AISLE can be blank - keep it in the exceptions list
    columns_that_can_be_blank = ["ITEM NUM", "Markup", "AISLE", "STOCK LOCATION", "SUPP"]
    columns_to_check = [col for col in df.columns if col not in columns_that_can_be_blank]

    df = df.dropna(subset=columns_to_check)

    # Drop unwanted columns - REMOVED "AISLE" FROM THIS LIST
    drop_cols = ["Markup", "STOCK LOCATION", "SUPP"]
    df = df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")

    return df


df = load_data(uploaded_file)

# ==========================================================
# SESSION STATE
# ==========================================================
if 'clear_counter' not in st.session_state:
    st.session_state.clear_counter = 0

# ==========================================================
# SEARCH
# ==========================================================
st.markdown("### 🔎 Search Product (min 3 letters)")

search_col, button_col = st.columns([6, 1])

with search_col:
    search_query = st.text_input(
        "Search product",
        placeholder="e.g. cumin",
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

search_query = search_query.lower().strip()

filtered_df = df[
    df["Description"].str.lower().str.contains(search_query, na=False)
]

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
# DISPLAY DATA (SORT BY PIECE COST) - NOW INCLUDES AISLE
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
    "AISLE"
]

display_cols = [col for col in base_display_cols if col in filtered_df.columns]

sort_column = "Pc. Cost" if "Pc. Cost" in filtered_df.columns else "Price"

final_df = (
    filtered_df[display_cols]
    .sort_values(sort_column)
    .reset_index(drop=True)
)

# ==========================================================
# METRICS  (LOWEST PRICE = LOWEST PIECE COST)
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
