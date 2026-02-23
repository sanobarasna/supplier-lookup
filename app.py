# ==========================================================
# Dynamic Product Search Dashboard
# Lowest Price = LOWEST PIECE COST (Pc. Cost)
# Includes STOCK and USAGE from RE ORDER sheet
# Search by Name OR Last 5 Digits of Barcode
# Only shows items WITH barcodes
# Counts STOCK/USAGE once per unique barcode
# Shows items to be ordered (uncolored in RE ORDER sheet)
# Table indices start from 1
# RE ORDER sheet column layout (fixed positions):
#   A(1)=DESCRIPTION  B(2)=PLU CODE  C(3)=COST
#   D(4)=GROUP        E(5)=STOCK     F(6)=PRICE 1
#   O(15)=USAGE
# GROUP stored as raw string: [CATEGORY][SUPPLIER1][SUPPLIER2]
# ORDER QTY column — editable, download only filled rows as .xlsx
# ==========================================================

import io
import streamlit as st
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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

SHEET_NAME_PRICES  = "EXISTING PRICES"
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
    missing_cols  = [col for col in required_cols if col not in df.columns]
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
# HELPER: resolve column index
# ==========================================================
def resolve_col(headers, *keys, default=1):
    for key in keys:
        if key in headers:
            return headers[key]
    return default

# ==========================================================
# LOAD RE ORDER — STOCK & USAGE (yellow rows only)
# ==========================================================
@st.cache_data
def load_reorder_data(file):
    try:
        wb = load_workbook(file, data_only=True)
        if SHEET_NAME_REORDER not in wb.sheetnames:
            st.warning(f"Sheet '{SHEET_NAME_REORDER}' not found. STOCK and USAGE will be empty.")
            return pd.DataFrame(columns=["PLU CODE", "STOCK", "USAGE"])

        ws = wb[SHEET_NAME_REORDER]
        headers = {}
        for cell in ws[2]:
            if cell.value:
                headers[str(cell.value).strip().upper()] = cell.column

        plu_col   = resolve_col(headers, "PLU CODE", "PLU", default=2)
        stock_col = resolve_col(headers, "STOCK", "STO", default=5)
        usage_col = resolve_col(headers, "USAGE", default=15)

        yellow_data = {}
        for row in range(3, ws.max_row + 1):
            plu_cell = ws.cell(row=row, column=plu_col)
            if plu_cell.fill and is_yellow_background(plu_cell.fill):
                plu_code = str(plu_cell.value).strip() if plu_cell.value else None
                if plu_code and plu_code != 'None' and plu_code not in yellow_data:
                    yellow_data[plu_code] = {
                        "STOCK": ws.cell(row=row, column=stock_col).value or "",
                        "USAGE": ws.cell(row=row, column=usage_col).value or ""
                    }

        df_reorder = pd.DataFrame([
            {"PLU CODE": plu, "STOCK": d["STOCK"], "USAGE": d["USAGE"]}
            for plu, d in yellow_data.items()
        ])
        st.success(f"✅ Loaded {len(df_reorder)} items with yellow PLU codes from RE ORDER sheet")
        return df_reorder

    except Exception as e:
        st.warning(f"Error reading RE ORDER sheet: {str(e)}. STOCK and USAGE will be empty.")
        return pd.DataFrame(columns=["PLU CODE", "STOCK", "USAGE"])

# ==========================================================
# LOAD UNORDERED ITEMS (uncolored rows) — v4 (ORDER QTY)
# Fixed column layout:
#   A(1)=DESCRIPTION  B(2)=PLU CODE  C(3)=COST PRICE
#   D(4)=GROUP        E(5)=STOCK     F(6)=SELLING PRICE
#   O(15)=USAGE
# GROUP always read from col 4, _x000D_ stripped.
# ==========================================================
@st.cache_data
def load_unordered_items(file):
    try:
        wb = load_workbook(file, data_only=True)
        if SHEET_NAME_REORDER not in wb.sheetnames:
            return pd.DataFrame(
                columns=["PLU CODE", "DESCRIPTION", "COST PRICE", "SELLING PRICE", "GROUP", "STOCK", "USAGE"]
            )

        ws = wb[SHEET_NAME_REORDER]
        headers = {}
        for cell in ws[2]:
            if cell.value:
                headers[str(cell.value).strip().upper()] = cell.column

        # desc_col=1 and group_col=4 are NEVER overridden — duplicate headers in sheet
        # (col 9 also = DESCRIPTION, col 22 also = GROUP) cause wrong resolution
        desc_col   = 1   # Column A — DESCRIPTION
        plu_col    = 2   # Column B — PLU CODE
        cost_col   = 3   # Column C — COST
        group_col  = 4   # Column D — GROUP
        stock_col  = 5   # Column E — STOCK
        price1_col = 6   # Column F — PRICE 1
        usage_col  = 15  # Column O — USAGE

        # Only override columns with unique header names
        plu_col    = resolve_col(headers, "PLU CODE", "PLU",   default=plu_col)
        cost_col   = resolve_col(headers, "COST",                default=cost_col)
        stock_col  = resolve_col(headers, "STOCK", "STO",       default=stock_col)
        price1_col = resolve_col(headers, "PRICE 1", "PRICE1",  default=price1_col)
        usage_col  = resolve_col(headers, "USAGE",               default=usage_col)
        # desc_col fixed at 1: col 9 also named DESCRIPTION — would resolve wrongly
        # group_col fixed at 4: col 22 also named GROUP — would resolve wrongly

        unordered_data = {}
        for row in range(3, ws.max_row + 1):
            plu_cell = ws.cell(row=row, column=plu_col)
            if not is_colored(plu_cell.fill):
                plu_code = str(plu_cell.value).strip() if plu_cell.value else None
                if plu_code and plu_code != 'None':
                    desc_val_check = str(ws.cell(row=row, column=desc_col).value or "").strip()
                    # Skip if already seen AND (we already have a good description OR this row is also blank)
                    if plu_code in unordered_data:
                        if unordered_data[plu_code]["DESCRIPTION"] != "" or desc_val_check == "":
                            continue
                        # Otherwise fall through: overwrite the blank entry with this better row
                    group_val = ws.cell(row=row, column=group_col).value
                    if group_val is not None:
                        group_raw = str(group_val)
                        group_raw = group_raw.replace('\r\n', '').replace('\r', '').replace('\n', '')
                        group_raw = group_raw.replace('_x000D_', '').strip()
                    else:
                        group_raw = ""

                    unordered_data[plu_code] = {
                        "DESCRIPTION":   str(ws.cell(row=row, column=desc_col).value or "").strip(),
                        "COST PRICE":    ws.cell(row=row, column=cost_col).value,
                        "GROUP":         group_raw,
                        "SELLING PRICE": ws.cell(row=row, column=price1_col).value,
                        "STOCK":         ws.cell(row=row, column=stock_col).value or 0,
                        "USAGE":         ws.cell(row=row, column=usage_col).value or 0,
                    }

        return pd.DataFrame([
            {
                "PLU CODE":      plu,
                "DESCRIPTION":   d["DESCRIPTION"],
                "COST PRICE":    d["COST PRICE"],
                "SELLING PRICE": d["SELLING PRICE"],
                "GROUP":         d["GROUP"],
                "STOCK":         d["STOCK"],
                "USAGE":         d["USAGE"],
            }
            for plu, d in unordered_data.items()
        ])

    except Exception as e:
        st.warning(f"Error reading unordered items: {str(e)}")
        return pd.DataFrame(
            columns=["PLU CODE", "DESCRIPTION", "COST PRICE", "SELLING PRICE", "GROUP", "STOCK", "USAGE"]
        )

# ==========================================================
# BUILD EXCEL DOWNLOAD
# Takes only rows where ORDER QTY > 0, exports as .xlsx
# with professional formatting using openpyxl.
# ==========================================================
def build_order_excel(df_with_qty: pd.DataFrame) -> bytes:
    # Filter to only rows with a quantity entered
    order_df = df_with_qty[
        df_with_qty["ORDER QTY"].notna() &
        (pd.to_numeric(df_with_qty["ORDER QTY"], errors="coerce").fillna(0) > 0)
    ].copy()

    wb = Workbook()
    ws = wb.active
    ws.title = "Order Sheet"

    # Styles
    header_font    = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    header_fill    = PatternFill("solid", fgColor="1F4E79")
    header_align   = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell_align_l   = Alignment(horizontal="left",   vertical="center")
    cell_align_r   = Alignment(horizontal="right",  vertical="center")
    cell_align_c   = Alignment(horizontal="center", vertical="center")
    qty_fill       = PatternFill("solid", fgColor="E2EFDA")   # light green for ORDER QTY
    qty_font       = Font(name="Arial", bold=True, size=11)
    thin_border    = Border(
        left=Side(style="thin"),  right=Side(style="thin"),
        top=Side(style="thin"),   bottom=Side(style="thin")
    )

    # Columns to export and their widths
    export_cols = ["PLU CODE", "DESCRIPTION", "COST PRICE", "SELLING PRICE", "GROUP", "STOCK", "USAGE", "ORDER QTY"]
    col_widths  = [18, 35, 13, 14, 38, 10, 10, 13]

    # Header row
    ws.row_dimensions[1].height = 30
    for col_idx, (col_name, width) in enumerate(zip(export_cols, col_widths), start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align
        cell.border    = thin_border
        ws.column_dimensions[cell.column_letter].width = width

    # Data rows
    alt_fill = PatternFill("solid", fgColor="F5F5F5")

    for row_idx, (_, row_data) in enumerate(order_df.iterrows(), start=2):
        ws.row_dimensions[row_idx].height = 18
        row_bg = alt_fill if row_idx % 2 == 0 else None

        for col_idx, col_name in enumerate(export_cols, start=1):
            val  = row_data.get(col_name, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border
            cell.font   = Font(name="Arial", size=10)

            # Alignment by column type
            if col_name in ("COST PRICE", "SELLING PRICE", "STOCK", "USAGE", "ORDER QTY"):
                cell.alignment = cell_align_r
            elif col_name == "PLU CODE":
                cell.alignment = cell_align_c
            else:
                cell.alignment = cell_align_l

            # ORDER QTY column — green highlight
            if col_name == "ORDER QTY":
                cell.fill = qty_fill
                cell.font = qty_font
            elif row_bg:
                cell.fill = row_bg

    # Freeze header row
    ws.freeze_panes = "A2"

    # Summary row at the bottom
    summary_row = len(order_df) + 2
    ws.cell(row=summary_row, column=1, value="TOTAL ITEMS").font = Font(name="Arial", bold=True, size=11)
    ws.cell(row=summary_row, column=1).alignment = cell_align_l
    ws.cell(row=summary_row, column=8, value=f'=SUM(H2:H{summary_row - 1})').font = Font(name="Arial", bold=True, size=11)
    ws.cell(row=summary_row, column=8).alignment = cell_align_r
    ws.cell(row=summary_row, column=8).fill = qty_fill

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()

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
        columns=["PLU CODE", "DESCRIPTION", "COST PRICE", "SELLING PRICE", "GROUP", "STOCK", "USAGE"]
    )
    st.info("📦 Upload RE ORDER workbook to see STOCK and USAGE data.")

# ==========================================================
# SESSION STATE
# ==========================================================
if 'reorder_clear_counter' not in st.session_state:
    st.session_state.reorder_clear_counter = 0
if 'clear_counter' not in st.session_state:
    st.session_state.clear_counter = 0

# ==========================================================
# ITEMS TO ORDER SECTION
# Layout: [View Items to Order]  [Group search]  [Clear]
# Table uses st.data_editor with ORDER QTY as editable column.
# Download button exports only rows with ORDER QTY > 0 as .xlsx
# ==========================================================
if reorder_file is not None and not df_unordered.empty:
    st.markdown("---")

    btn_col, cat_col, sup_col, clear_col = st.columns([2, 2.5, 2.5, 1.2])

    with btn_col:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("📋 View Items to Order", type="primary", use_container_width=True, key="view_order_btn"):
            st.session_state.show_unordered = not st.session_state.get('show_unordered', False)
        st.markdown("</div>", unsafe_allow_html=True)

    # Parse CATEGORY and SUPPLIER from GROUP strings
    # Format: [CATEGORY][SUPPLIER1][SUPPLIER2]
    def parse_group_parts(g):
        import re as _re
        parts = _re.findall(r"\[([^\]]+)\]", str(g))
        category = parts[0].strip() if len(parts) > 0 else ""
        suppliers = [p.strip() for p in parts[1:] if p.strip()]
        return category, suppliers

    parsed = df_unordered["GROUP"].apply(parse_group_parts)
    all_cats = sorted(set(c for c, _ in parsed if c))

    with cat_col:
        selected_cat = st.selectbox(
            "Filter by Category",
            options=["— All Categories —"] + all_cats,
            index=0,
            key=f"cat_filter_{st.session_state.reorder_clear_counter}"
        )

    # Build supplier list — filtered by selected category if one is chosen
    if selected_cat == "— All Categories —":
        all_sups = sorted(set(s for _, sups in parsed for s in sups if s))
    else:
        all_sups = sorted(set(
            s for (c, sups) in parsed if c == selected_cat
            for s in sups if s
        ))

    with sup_col:
        selected_sup = st.selectbox(
            "Filter by Supplier",
            options=["— All Suppliers —"] + all_sups,
            index=0,
            key=f"sup_filter_{st.session_state.reorder_clear_counter}"
        )

    with clear_col:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("🔄 Clear", type="secondary", use_container_width=True, key="reorder_clear_btn"):
            st.session_state.reorder_clear_counter += 1
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.get('show_unordered', False):
        st.markdown("### 📋 Items to Order (Uncolored in RE ORDER sheet)")

        # Apply CATEGORY and SUPPLIER filters
        display_df = df_unordered.copy()

        import re as _re2
        def _get_cat(g):
            parts = _re2.findall(r"\[([^\]]+)\]", str(g))
            return parts[0].strip() if parts else ""
        def _get_sups(g):
            parts = _re2.findall(r"\[([^\]]+)\]", str(g))
            return [p.strip() for p in parts[1:]]

        if selected_cat != "— All Categories —":
            display_df = display_df[display_df["GROUP"].apply(_get_cat) == selected_cat]

        if selected_sup != "— All Suppliers —":
            display_df = display_df[display_df["GROUP"].apply(lambda g: selected_sup in _get_sups(g))]

        # Numeric conversions
        display_df["STOCK"]         = pd.to_numeric(display_df["STOCK"],         errors='coerce').fillna(0)
        display_df["USAGE"]         = pd.to_numeric(display_df["USAGE"],         errors='coerce').fillna(0)
        display_df["COST PRICE"]    = pd.to_numeric(display_df["COST PRICE"],    errors='coerce')
        display_df["SELLING PRICE"] = pd.to_numeric(display_df["SELLING PRICE"], errors='coerce')

        # Sort by USAGE descending
        display_df = display_df.sort_values("USAGE", ascending=False).reset_index(drop=True)

        # Add ORDER QTY column (blank/None by default)
        display_df["ORDER QTY"] = None

        st.info(f"Found **{len(display_df)}** items that need to be ordered — enter quantities below then download")

        # DEBUG EXPANDER
        blank_desc = display_df[display_df["DESCRIPTION"].isna() | (display_df["DESCRIPTION"] == "")]
        if not blank_desc.empty:
            with st.expander(f"🔍 Debug: {len(blank_desc)} items with blank descriptions — click to inspect", expanded=False):
                st.markdown("**Header map detected in RE ORDER sheet row 2:**")
                try:
                    _wb2 = load_workbook(reorder_file, data_only=True)
                    _ws2 = _wb2[SHEET_NAME_REORDER]
                    _hmap = {_c.column: f"Col {_c.column} = {repr(str(_c.value).strip())}" for _c in _ws2[2] if _c.value}
                    st.write(_hmap)
                    st.markdown("**Raw columns A-J for first blank PLU:**")
                    _sample_plu = str(blank_desc.iloc[0]["PLU CODE"])
                    for _r in range(3, _ws2.max_row + 1):
                        if str(_ws2.cell(row=_r, column=2).value or "").strip() == _sample_plu:
                            _vals = {f"Col {_ci}": _ws2.cell(row=_r, column=_ci).value for _ci in range(1, 11)}
                            st.write(f"Row {_r}:", _vals)
                            break
                except Exception as _e:
                    st.write(f"Debug error: {_e}")

        # Column order: PLU CODE, DESCRIPTION, COST PRICE, SELLING PRICE, GROUP, STOCK, USAGE, ORDER QTY
        show_cols = ["PLU CODE", "DESCRIPTION", "COST PRICE", "SELLING PRICE", "GROUP", "STOCK", "USAGE", "ORDER QTY"]
        show_cols = [c for c in show_cols if c in display_df.columns]

        # Build column config — only ORDER QTY is editable
        column_config = {
            "PLU CODE":      st.column_config.TextColumn("PLU CODE",      disabled=True),
            "DESCRIPTION":   st.column_config.TextColumn("DESCRIPTION",   disabled=True),
            "COST PRICE":    st.column_config.NumberColumn("COST PRICE",  disabled=True, format="$%.2f"),
            "SELLING PRICE": st.column_config.NumberColumn("SELLING PRICE", disabled=True, format="$%.2f"),
            "GROUP":         st.column_config.TextColumn("GROUP",         disabled=True),
            "STOCK":         st.column_config.NumberColumn("STOCK",       disabled=True, format="%d"),
            "USAGE":         st.column_config.NumberColumn("USAGE",       disabled=True, format="%d"),
            "ORDER QTY":     st.column_config.NumberColumn(
                                "ORDER QTY",
                                disabled=False,
                                help="Enter the number of cases/units to order",
                                min_value=0,
                                step=1,
                                format="%d"
                             ),
        }

        edited_df = st.data_editor(
            display_df[show_cols],
            column_config=column_config,
            hide_index=False,
            use_container_width=True,
            height=450,
            key=f"order_editor_{st.session_state.reorder_clear_counter}"
        )

        # Count how many rows have a quantity entered
        qty_filled = edited_df[
            edited_df["ORDER QTY"].notna() &
            (pd.to_numeric(edited_df["ORDER QTY"], errors="coerce").fillna(0) > 0)
        ]
        n_filled = len(qty_filled)

        # Download row — show count and download button side by side
        dl_info_col, dl_btn_col, dl_spacer = st.columns([3, 2, 5])

        with dl_info_col:
            if n_filled > 0:
                st.success(f"✅ {n_filled} item(s) with quantities ready to download")
            else:
                st.info("Enter quantities above to enable download")

        with dl_btn_col:
            if n_filled > 0:
                excel_bytes = build_order_excel(edited_df)
                st.download_button(
                    label="📥 Download Order Sheet (.xlsx)",
                    data=excel_bytes,
                    file_name="order_sheet.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="secondary",
                    use_container_width=True
                )

        st.markdown("---")

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
    unique_stock = final_df.groupby("BARCODE")["STOCK"].first()
    total_stock  = pd.to_numeric(unique_stock, errors="coerce").fillna(0).sum()
    colD.metric("Total Stock", f"{total_stock:,.0f}")
else:
    colD.metric("Total Stock", "N/A")

if "USAGE" in final_df.columns and "BARCODE" in final_df.columns:
    unique_usage = final_df.groupby("BARCODE")["USAGE"].first()
    total_usage  = pd.to_numeric(unique_usage, errors="coerce").fillna(0).sum()
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
