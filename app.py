# ==========================================================
# ITEMS TO ORDER VIEW (WITH CATEGORY + SUPPLIER FILTERS)
# NOW SUPPORTS .XLSX AND .XLSM FILES
# ==========================================================

import streamlit as st
import pandas as pd
import re

st.set_page_config(layout="wide")

# ==========================================================
# LOAD EXTERNAL CSS
# ==========================================================
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.markdown("## 📋 Items to Order (Uncolored in RE ORDER sheet)")

# ==========================================================
# FILE UPLOADS (NOW ALLOW XLSM)
# ==========================================================
col1, col2 = st.columns(2)

with col1:
    existing_file = st.file_uploader(
        "Upload EXISTING PRICES sheet",
        type=["xlsx", "xlsm"]
    )

with col2:
    reorder_file = st.file_uploader(
        "Upload RE ORDER sheet",
        type=["xlsx", "xlsm"]
    )

if not existing_file or not reorder_file:
    st.stop()

# ==========================================================
# READ FILES (USE OPENPYXL FOR XLSM SUPPORT)
# ==========================================================
existing_df = pd.read_excel(
    existing_file,
    sheet_name="EXISTING PRICES",
    engine="openpyxl"
)

reorder_df = pd.read_excel(
    reorder_file,
    sheet_name=0,
    engine="openpyxl"
)

# Clean headers
existing_df.columns = existing_df.columns.str.strip()
reorder_df.columns = reorder_df.columns.str.strip()

# ==========================================================
# EXTRACT PLU CODES
# (Keeping your current logic structure intact)
# ==========================================================
yellow_plu_codes = set(
    reorder_df["PLU CODE"].dropna().astype(str)
)

# ==========================================================
# MATCH ITEMS
# ==========================================================
items_to_order = existing_df[
    existing_df["PLU CODE"].astype(str).isin(yellow_plu_codes)
].copy()

if items_to_order.empty:
    st.warning("No matching items found.")
    st.stop()

# ==========================================================
# KEEP REQUIRED COLUMNS
# ==========================================================
required_cols = [
    "PLU CODE",
    "DESCRIPTION",
    "STOCK",
    "USAGE",
    "COST",
    "GROUP",
    "PRICE 1"
]

items_to_order = items_to_order[required_cols]

# ==========================================================
# SPLIT GROUP INTO CATEGORY + SUPPLIERS
# FORMAT: [CATEGORY][SUPPLIER 1][SUPPLIER 2]
# ==========================================================
def extract_parts(group_text):
    matches = re.findall(r"\[(.*?)\]", str(group_text))
    category = matches[0] if len(matches) > 0 else None
    suppliers = matches[1:] if len(matches) > 1 else []
    return category, suppliers

items_to_order["Category"] = items_to_order["GROUP"].apply(
    lambda x: extract_parts(x)[0]
)

items_to_order["Suppliers_List"] = items_to_order["GROUP"].apply(
    lambda x: extract_parts(x)[1]
)

# Flatten supplier list for dropdown
all_suppliers = sorted(
    {supplier for sublist in items_to_order["Suppliers_List"] for supplier in sublist}
)

all_categories = sorted(
    items_to_order["Category"].dropna().unique()
)

# ==========================================================
# BUTTON + FILTERS ROW
# Layout:
# [View Items to Order] [Category] [Supplier]
# ==========================================================
btn_col, cat_col, sup_col = st.columns([2, 2, 2])

with btn_col:
    view_button = st.button("📋 View Items to Order", type="primary")

with cat_col:
    selected_category = st.selectbox(
        "Category",
        options=["All"] + all_categories,
        index=0
    )

with sup_col:
    selected_supplier = st.selectbox(
        "Supplier",
        options=["All"] + all_suppliers,
        index=0
    )

# ==========================================================
# DISPLAY TABLE AFTER BUTTON CLICK
# ==========================================================
if view_button:

    filtered_display = items_to_order.copy()

    if selected_category != "All":
        filtered_display = filtered_display[
            filtered_display["Category"] == selected_category
        ]

    if selected_supplier != "All":
        filtered_display = filtered_display[
            filtered_display["Suppliers_List"].apply(
                lambda x: selected_supplier in x
            )
        ]

    filtered_display = filtered_display.reset_index(drop=True)
    filtered_display.index += 1

    st.markdown(
        f"### Found {len(filtered_display)} items that need to be ordered"
    )

    st.dataframe(
        filtered_display[
            [
                "PLU CODE",
                "DESCRIPTION",
                "STOCK",
                "USAGE",
                "COST",
                "GROUP",
                "PRICE 1"
            ]
        ],
        use_container_width=True,
        height=600
    )

    st.download_button(
        "Download Items to Order",
        filtered_display.to_csv(index=False),
        "items_to_order.csv",
        "text/csv"
    )
