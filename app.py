# ==========================================================
# Dynamic Product Search Dashboard — Tabbed Layout
# Tab 1: Orders      — Items to order (uncolored rows)
# Tab 2: Stock Value — Yellow PLU stock value by cat/supplier
# Tab 3: Search      — Product search by name / barcode
#
# RE ORDER sheet fixed column positions:
#   A(1)=DESCRIPTION  B(2)=PLU CODE  C(3)=COST
#   D(4)=GROUP        E(5)=STOCK     F(6)=PRICE 1
#   O(15)=USAGE
# ==========================================================

import io
import re
import streamlit as st
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from pathlib import Path

st.set_page_config(page_title="Store Dashboard", layout="wide")

# ----------------------------------------------------------
# CSS
# ----------------------------------------------------------
def load_css():
    css_file = Path(__file__).parent / "styles.css"
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# ----------------------------------------------------------
# Custom tab-bar CSS — makes the radio look like real tabs
# ----------------------------------------------------------
st.markdown("""
<style>
div[data-testid="stRadio"] > label { display: none; }
div[data-testid="stRadio"] > div {
    display: flex !important;
    flex-direction: row !important;
    gap: 4px !important;
    border-bottom: 2px solid #e0e0e0;
    padding-bottom: 0px;
    margin-bottom: 16px;
}
div[data-testid="stRadio"] > div > label {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 10px 24px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    border-radius: 6px 6px 0 0 !important;
    border: 1px solid transparent !important;
    border-bottom: none !important;
    background: #f5f5f5 !important;
    color: #555 !important;
    transition: background 0.15s, color 0.15s !important;
    margin-bottom: -2px !important;
}
div[data-testid="stRadio"] > div > label:hover {
    background: #e8f4fd !important;
    color: #1a73e8 !important;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
    background: #ffffff !important;
    color: #1a73e8 !important;
    border-color: #e0e0e0 !important;
    border-bottom: 2px solid #ffffff !important;
}
div[data-testid="stRadio"] > div > label > div:first-child {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

st.title("🏪 Store Dashboard")

# ----------------------------------------------------------
# FILE UPLOADERS
# ----------------------------------------------------------
u1, u2 = st.columns(2)
with u1:
    st.markdown("#### 📊 Upload EXISTING PRICES Workbook")
    prices_file = st.file_uploader("EXISTING PRICES", type=["xlsx","xlsm"],
                                   label_visibility="collapsed", key="prices_up")
with u2:
    st.markdown("#### 📦 Upload RE ORDER Workbook")
    reorder_file = st.file_uploader("RE ORDER", type=["xlsx","xlsm"],
                                    label_visibility="collapsed", key="reorder_up")

if prices_file is None:
    st.info("Please upload the EXISTING PRICES workbook to begin.")
    st.stop()

PRICES_SHEET  = "EXISTING PRICES"
REORDER_SHEET = "RE ORDER"

# ==========================================================
# COLOUR HELPERS
# ==========================================================
def is_yellow(fill):
    try:
        if not fill or fill.patternType != "solid":
            return False
        fc = fill.fgColor
        if hasattr(fc, "index") and fc.index in [6, 13, 27, 43]:
            return True
        rgb = None
        if hasattr(fc, "rgb"):
            rgb = fc.rgb if isinstance(fc.rgb, str) else str(fc.rgb)
        if rgb and len(rgb) >= 6:
            rgb = rgb[-6:]
            r, g, b = int(rgb[0:2],16), int(rgb[2:4],16), int(rgb[4:6],16)
            return r > 200 and g > 200 and b < 150
    except:
        pass
    return False

def is_blue(fill):
    try:
        if not fill or fill.patternType != "solid":
            return False
        fc = fill.fgColor
        if hasattr(fc, "index") and fc.index in [5, 12, 25, 41]:
            return True
        rgb = None
        if hasattr(fc, "rgb"):
            rgb = fc.rgb if isinstance(fc.rgb, str) else str(fc.rgb)
        if rgb and len(rgb) >= 6:
            rgb = rgb[-6:]
            r, g, b = int(rgb[0:2],16), int(rgb[2:4],16), int(rgb[4:6],16)
            return b > 200 and r < 150 and g < 150
    except:
        pass
    return False

def is_colored(fill):
    if not fill or fill.patternType != "solid":
        return False
    if is_yellow(fill) or is_blue(fill):
        return True
    try:
        fc = fill.fgColor
        if hasattr(fc, "index") and fc.index:
            return True
        rgb = fc.rgb if isinstance(fc.rgb, str) else str(fc.rgb)
        if rgb and rgb not in ["00000000","FFFFFFFF","ffffffff","00FFFFFF"]:
            return True
    except:
        pass
    return False

# ==========================================================
# GROUP HELPERS
# ==========================================================
def clean_group(val):
    if val is None:
        return ""
    return str(val).replace("\r\n","").replace("\r","").replace("\n","").replace("_x000D_","").strip()

def get_category(g):
    parts = re.findall(r"\[([^\]]+)\]", str(g))
    return parts[0].strip() if parts else ""

def get_suppliers(g):
    parts = re.findall(r"\[([^\]]+)\]", str(g))
    return [p.strip() for p in parts[1:] if p.strip()]

def resolve_col(headers, *keys, default=1):
    for k in keys:
        if k in headers:
            return headers[k]
    return default

# ==========================================================
# LOADERS
# ==========================================================
@st.cache_data
def load_prices(file):
    xls = pd.ExcelFile(file)
    if PRICES_SHEET not in xls.sheet_names:
        raise ValueError(f'Sheet "{PRICES_SHEET}" not found.')
    df = pd.read_excel(xls, sheet_name=PRICES_SHEET, engine="openpyxl")
    df.columns = df.columns.str.strip()
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    if "SUPPLIER" not in df.columns:
        for c in df.columns:
            if c.upper() in ["SUPPLIER","SUPP"]:
                df = df.rename(columns={c:"SUPPLIER"}); break
    for col in ["Description","SUPPLIER","Size","Price"]:
        if col not in df.columns:
            raise ValueError(f"Missing column: {col}")
    df["Description"] = df["Description"].astype(str).str.strip()
    df["SUPPLIER"]    = df["SUPPLIER"].astype(str).str.strip()
    df["Size"]        = df["Size"].astype(str).str.strip()
    df["Price"]       = pd.to_numeric(df["Price"], errors="coerce")
    if "BARCODE" not in df.columns:
        raise ValueError("BARCODE column not found.")
    df["BARCODE"] = df["BARCODE"].astype(str).str.strip()
    df = df[df["BARCODE"].notna() & (df["BARCODE"] != "") & (df["BARCODE"].str.lower() != "nan")]
    if "AISLE" in df.columns:
        df["AISLE"] = df["AISLE"].astype(str).str.strip()
    if "Pc. Cost" in df.columns:
        df["Pc. Cost"] = pd.to_numeric(df["Pc. Cost"], errors="coerce")
    skip = ["ITEM NUM","Markup","AISLE","STOCK LOCATION","SUPP"]
    df = df.dropna(subset=[c for c in df.columns if c not in skip])
    df = df.drop(columns=[c for c in ["Markup","STOCK LOCATION","SUPP"] if c in df.columns])
    return df


@st.cache_data
def load_yellow_basic(file):
    try:
        wb = load_workbook(file, data_only=True)
        if REORDER_SHEET not in wb.sheetnames:
            return pd.DataFrame(columns=["PLU CODE","STOCK","USAGE"])
        ws = wb[REORDER_SHEET]
        hdr = {str(c.value).strip().upper(): c.column for c in ws[2] if c.value}
        plu_c   = resolve_col(hdr, "PLU CODE","PLU", default=2)
        stock_c = resolve_col(hdr, "STOCK","STO",    default=5)
        usage_c = resolve_col(hdr, "USAGE",           default=15)
        rows = {}
        for r in range(3, ws.max_row+1):
            cell = ws.cell(r, plu_c)
            if is_yellow(cell.fill):
                plu = str(cell.value).strip() if cell.value else None
                if plu and plu != "None" and plu not in rows:
                    rows[plu] = {
                        "STOCK": ws.cell(r, stock_c).value or "",
                        "USAGE": ws.cell(r, usage_c).value or ""
                    }
        df = pd.DataFrame([{"PLU CODE":p,"STOCK":d["STOCK"],"USAGE":d["USAGE"]} for p,d in rows.items()])
        st.success(f"Loaded {len(df)} yellow PLU items from RE ORDER sheet")
        return df
    except Exception as e:
        st.warning(f"Error loading RE ORDER: {e}")
        return pd.DataFrame(columns=["PLU CODE","STOCK","USAGE"])


@st.cache_data
def load_yellow_full(file):
    try:
        wb = load_workbook(file, data_only=True)
        if REORDER_SHEET not in wb.sheetnames:
            return pd.DataFrame(columns=["PLU CODE","DESCRIPTION","COST","GROUP","STOCK","USAGE"])
        ws = wb[REORDER_SHEET]
        hdr = {str(c.value).strip().upper(): c.column for c in ws[2] if c.value}
        desc_c  = 1
        plu_c   = resolve_col(hdr, "PLU CODE","PLU", default=2)
        cost_c  = 3
        group_c = 4
        stock_c = resolve_col(hdr, "STOCK","STO", default=5)
        usage_c = resolve_col(hdr, "USAGE",        default=15)
        rows = {}
        for r in range(3, ws.max_row+1):
            cell = ws.cell(r, plu_c)
            if is_yellow(cell.fill):
                plu = str(cell.value).strip() if cell.value else None
                if plu and plu != "None":
                    desc = str(ws.cell(r, desc_c).value or "").strip()
                    if plu in rows:
                        if rows[plu]["DESCRIPTION"] != "" or desc == "":
                            continue
                    rows[plu] = {
                        "DESCRIPTION": desc,
                        "COST":        ws.cell(r, cost_c).value,
                        "GROUP":       clean_group(ws.cell(r, group_c).value),
                        "STOCK":       ws.cell(r, stock_c).value or 0,
                        "USAGE":       ws.cell(r, usage_c).value or 0,
                    }
        return pd.DataFrame([
            {"PLU CODE":p,"DESCRIPTION":d["DESCRIPTION"],"COST":d["COST"],
             "GROUP":d["GROUP"],"STOCK":d["STOCK"],"USAGE":d["USAGE"]}
            for p,d in rows.items()
        ])
    except Exception as e:
        st.warning(f"Error loading yellow full data: {e}")
        return pd.DataFrame(columns=["PLU CODE","DESCRIPTION","COST","GROUP","STOCK","USAGE"])


@st.cache_data
def load_unordered(file):
    try:
        wb = load_workbook(file, data_only=True)
        if REORDER_SHEET not in wb.sheetnames:
            return pd.DataFrame(columns=["PLU CODE","DESCRIPTION","COST PRICE","SELLING PRICE","GROUP","STOCK","USAGE"])
        ws = wb[REORDER_SHEET]
        hdr = {str(c.value).strip().upper(): c.column for c in ws[2] if c.value}
        desc_c   = 1
        plu_c    = resolve_col(hdr, "PLU CODE","PLU",  default=2)
        cost_c   = 3
        group_c  = 4
        stock_c  = resolve_col(hdr, "STOCK","STO",     default=5)
        price1_c = resolve_col(hdr, "PRICE 1","PRICE1",default=6)
        usage_c  = resolve_col(hdr, "USAGE",            default=15)
        rows = {}
        for r in range(3, ws.max_row+1):
            cell = ws.cell(r, plu_c)
            if not is_colored(cell.fill):
                plu = str(cell.value).strip() if cell.value else None
                if plu and plu != "None":
                    desc = str(ws.cell(r, desc_c).value or "").strip()
                    if plu in rows:
                        if rows[plu]["DESCRIPTION"] != "" or desc == "":
                            continue
                    rows[plu] = {
                        "DESCRIPTION":   desc,
                        "COST PRICE":    ws.cell(r, cost_c).value,
                        "GROUP":         clean_group(ws.cell(r, group_c).value),
                        "SELLING PRICE": ws.cell(r, price1_c).value,
                        "STOCK":         ws.cell(r, stock_c).value or 0,
                        "USAGE":         ws.cell(r, usage_c).value or 0,
                    }
        return pd.DataFrame([
            {"PLU CODE":p,"DESCRIPTION":d["DESCRIPTION"],"COST PRICE":d["COST PRICE"],
             "SELLING PRICE":d["SELLING PRICE"],"GROUP":d["GROUP"],
             "STOCK":d["STOCK"],"USAGE":d["USAGE"]}
            for p,d in rows.items()
        ])
    except Exception as e:
        st.warning(f"Error loading unordered items: {e}")
        return pd.DataFrame(columns=["PLU CODE","DESCRIPTION","COST PRICE","SELLING PRICE","GROUP","STOCK","USAGE"])


# ==========================================================
# EXCEL ORDER SHEET BUILDER
# ==========================================================
def build_order_excel(df_edited):
    order_df = df_edited[
        df_edited["ORDER QTY"].notna() &
        (pd.to_numeric(df_edited["ORDER QTY"], errors="coerce").fillna(0) > 0)
    ].copy()
    wb = Workbook(); ws = wb.active; ws.title = "Order Sheet"
    hf    = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    hfill = PatternFill("solid", fgColor="1F4E79")
    ha    = Alignment(horizontal="center", vertical="center", wrap_text=True)
    la    = Alignment(horizontal="left",   vertical="center")
    ra    = Alignment(horizontal="right",  vertical="center")
    ca    = Alignment(horizontal="center", vertical="center")
    qfill = PatternFill("solid", fgColor="E2EFDA")
    qfont = Font(name="Arial", bold=True, size=11)
    bdr   = Border(left=Side(style="thin"), right=Side(style="thin"),
                   top=Side(style="thin"),  bottom=Side(style="thin"))
    cols   = ["PLU CODE","DESCRIPTION","COST PRICE","SELLING PRICE","GROUP","STOCK","USAGE","ORDER QTY"]
    widths = [18, 35, 13, 14, 38, 10, 10, 13]
    ws.row_dimensions[1].height = 30
    for ci, (cn, w) in enumerate(zip(cols, widths), 1):
        c = ws.cell(1, ci, cn)
        c.font=hf; c.fill=hfill; c.alignment=ha; c.border=bdr
        ws.column_dimensions[c.column_letter].width = w
    alt = PatternFill("solid", fgColor="F5F5F5")
    for ri, (_, row) in enumerate(order_df.iterrows(), 2):
        ws.row_dimensions[ri].height = 18
        bg = alt if ri % 2 == 0 else None
        for ci, cn in enumerate(cols, 1):
            c = ws.cell(ri, ci, row.get(cn,""))
            c.border=bdr; c.font=Font(name="Arial",size=10)
            if cn in ("COST PRICE","SELLING PRICE","STOCK","USAGE","ORDER QTY"):
                c.alignment = ra
            elif cn == "PLU CODE":
                c.alignment = ca
            else:
                c.alignment = la
            if cn == "ORDER QTY":
                c.fill=qfill; c.font=qfont
            elif bg:
                c.fill = bg
    ws.freeze_panes = "A2"
    sr = len(order_df) + 2
    ws.cell(sr, 1, "TOTAL ITEMS").font = Font(name="Arial", bold=True, size=11)
    ws.cell(sr, 1).alignment = la
    ws.cell(sr, 8, f"=SUM(H2:H{sr-1})").font = Font(name="Arial", bold=True, size=11)
    ws.cell(sr, 8).alignment = ra; ws.cell(sr, 8).fill = qfill
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    return buf.getvalue()


@st.cache_data
def load_reorder_price1(file):
    try:
        wb = load_workbook(file, data_only=True)
        if REORDER_SHEET not in wb.sheetnames:
            return pd.DataFrame(columns=["PLU CODE","PRICE 1"])
        ws = wb[REORDER_SHEET]
        hdr = {str(c.value).strip().upper(): c.column for c in ws[2] if c.value}
        plu_c    = resolve_col(hdr, "PLU CODE","PLU", default=2)
        price1_c = resolve_col(hdr, "PRICE 1","PRICE1", default=6)
        rows = {}
        for r in range(3, ws.max_row+1):
            cell = ws.cell(r, plu_c)
            if is_yellow(cell.fill):
                plu = str(cell.value).strip() if cell.value else None
                if plu and plu != "None" and plu not in rows:
                    rows[plu] = ws.cell(r, price1_c).value
        return pd.DataFrame([{"PLU CODE": p, "PRICE 1": v} for p, v in rows.items()])
    except Exception as e:
        return pd.DataFrame(columns=["PLU CODE","PRICE 1"])

# ==========================================================
# LOAD ALL DATA
# ==========================================================
df_prices = load_prices(prices_file)

if reorder_file is not None:
    df_ybasic    = load_yellow_basic(reorder_file)
    df_yfull     = load_yellow_full(reorder_file)
    df_unordered = load_unordered(reorder_file)
    df_price1    = load_reorder_price1(reorder_file)
    if not df_ybasic.empty:
        df_search = df_prices.merge(df_ybasic, left_on="BARCODE", right_on="PLU CODE", how="left")
        df_search = df_search.drop(columns=["PLU CODE"], errors="ignore")
    else:
        df_search = df_prices.copy()
        df_search["STOCK"] = ""; df_search["USAGE"] = ""
else:
    df_ybasic    = pd.DataFrame(columns=["PLU CODE","STOCK","USAGE"])
    df_yfull     = pd.DataFrame(columns=["PLU CODE","DESCRIPTION","COST","GROUP","STOCK","USAGE"])
    df_unordered = pd.DataFrame(columns=["PLU CODE","DESCRIPTION","COST PRICE","SELLING PRICE","GROUP","STOCK","USAGE"])
    df_price1    = pd.DataFrame(columns=["PLU CODE","PRICE 1"])
    df_search    = df_prices.copy()
    df_search["STOCK"] = ""; df_search["USAGE"] = ""
    st.info("Upload the RE ORDER workbook to unlock all features.")

# ==========================================================
# SESSION STATE
# ==========================================================
for k, v in [("order_clear", 0), ("search_clear", 0), ("active_tab", "📋 Orders & Search")]:
    if k not in st.session_state:
        st.session_state[k] = v

# ==========================================================
# PERSISTENT TAB BAR
# Uses st.radio stored in session_state so the selected tab
# survives every rerun, including st.rerun() calls.
# ==========================================================
TAB_LABELS = ["📋 Orders & Search", "📊 Stock Value", "🔎 Price Comparison"]

active_tab = st.radio(
    "Navigation",
    TAB_LABELS,
    index=TAB_LABELS.index(st.session_state.active_tab),
    horizontal=True,
    label_visibility="collapsed",
    key="tab_radio",
)
st.session_state.active_tab = active_tab

st.markdown("---")


# ======================================================
# TAB 1 — ORDERS & SEARCH
# ======================================================
if active_tab == "📋 Orders & Search":

    st.markdown("## 📋 Items to Order")
    if reorder_file is None or df_unordered.empty:
        st.info("Upload the RE ORDER workbook to see items to order.")
    else:
        parsed_un   = df_unordered["GROUP"].apply(lambda g: (get_category(g), get_suppliers(g)))
        all_cats_un = sorted(set(c for c,_ in parsed_un if c))

        fc, fs, fbtn = st.columns([2.5, 2.5, 1.2])
        with fc:
            sel_cat = st.selectbox("Filter by Category",
                                   ["— All Categories —"] + all_cats_un,
                                   key=f"t1_cat_{st.session_state.order_clear}")
        all_sups_un = sorted(set(
            s for (c, sups) in parsed_un for s in sups
            if (sel_cat == "— All Categories —" or c == sel_cat)
        ))
        with fs:
            sel_sup = st.selectbox("Filter by Supplier",
                                   ["— All Suppliers —"] + all_sups_un,
                                   key=f"t1_sup_{st.session_state.order_clear}")
        with fbtn:
            st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
            if st.button("🔄 Clear", type="secondary", use_container_width=True, key="t1_clear"):
                st.session_state.order_clear += 1
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

        disp = df_unordered.copy()
        if sel_cat != "— All Categories —":
            disp = disp[disp["GROUP"].apply(get_category) == sel_cat]
        if sel_sup != "— All Suppliers —":
            disp = disp[disp["GROUP"].apply(lambda g: sel_sup in get_suppliers(g))]

        for col in ["STOCK","USAGE"]:
            disp[col] = pd.to_numeric(disp[col], errors="coerce").fillna(0)
        for col in ["COST PRICE","SELLING PRICE"]:
            disp[col] = pd.to_numeric(disp[col], errors="coerce")

        disp = disp.sort_values("USAGE", ascending=False).reset_index(drop=True)
        disp["ORDER QTY"] = None

        if sel_sup != "— All Suppliers —":
            mu, mv, _ = st.columns([1.8, 1.8, 5])
            mu.metric("📦 Units on Hand", f"{disp['STOCK'].sum():,.0f}")
            mv.metric("💲 Stock Value",   f"${(disp['STOCK'] * disp['COST PRICE'].fillna(0)).sum():,.2f}")

        st.info(f"Found **{len(disp)}** items to order — enter quantities then download")

        col_cfg = {
            "PLU CODE":      st.column_config.TextColumn(disabled=True),
            "DESCRIPTION":   st.column_config.TextColumn(disabled=True),
            "COST PRICE":    st.column_config.NumberColumn(disabled=True, format="$%.2f"),
            "SELLING PRICE": st.column_config.NumberColumn(disabled=True, format="$%.2f"),
            "GROUP":         st.column_config.TextColumn(disabled=True),
            "STOCK":         st.column_config.NumberColumn(disabled=True, format="%d"),
            "USAGE":         st.column_config.NumberColumn(disabled=True, format="%d"),
            "ORDER QTY":     st.column_config.NumberColumn(
                                 disabled=False, min_value=0, step=1, format="%d",
                                 help="Enter cases/units to order"),
        }
        show_cols = ["PLU CODE","DESCRIPTION","COST PRICE","SELLING PRICE","GROUP","STOCK","USAGE","ORDER QTY"]
        edited = st.data_editor(disp[show_cols], column_config=col_cfg,
                                hide_index=False, use_container_width=True, height=480,
                                key=f"t1_editor_{st.session_state.order_clear}")

        qty_rows = edited[
            edited["ORDER QTY"].notna() &
            (pd.to_numeric(edited["ORDER QTY"], errors="coerce").fillna(0) > 0)
        ]
        n = len(qty_rows)
        ic, dc, _ = st.columns([3, 2, 5])
        with ic:
            if n > 0:
                st.success(f"✅ {n} item(s) ready to download")
            else:
                st.info("Enter quantities above to enable download")
        with dc:
            if n > 0:
                st.download_button("📥 Download Order Sheet (.xlsx)",
                                   data=build_order_excel(edited),
                                   file_name="order_sheet.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   type="secondary", use_container_width=True)

    # ── Product Search ─────────────────────────────────
    st.markdown("---")
    st.markdown("## 🔍 Product Search")
    sc, bc = st.columns([6, 1])
    with sc:
        q = st.text_input("Search", placeholder="e.g. cumin OR 12345 (last 5 digits of barcode)",
                          label_visibility="collapsed",
                          key=f"sq_{st.session_state.search_clear}")
    with bc:
        if st.button("🔄 Clear", type="secondary", use_container_width=True, key="t3_clear"):
            st.session_state.search_clear += 1
            st.rerun()

    if not q or len(q.strip()) < 3:
        st.info("Enter at least 3 characters to search.")
    else:
        q = q.strip()
        df_search["_b5"] = df_search["BARCODE"].astype(str).str[-5:]
        res = df_search[
            df_search["Description"].str.lower().str.contains(q.lower(), na=False) |
            df_search["_b5"].str.contains(q, na=False)
        ].drop(columns=["_b5"])

        if res.empty:
            st.warning("No matching products found.")
        else:
            st.markdown(f"### Results for **'{q}'**")
            f1, f2, f3, f4 = st.columns(4)

            desc_f = f1.text_input("Filter description", key=f"df_{st.session_state.search_clear}")
            if desc_f:
                res = res[res["Description"].str.lower().str.contains(desc_f.lower(), na=False)]

            if "Size" in res.columns:
                sz = f2.multiselect("Filter Size", sorted(res["Size"].unique()),
                                    key=f"szf_{st.session_state.search_clear}")
                if sz:
                    res = res[res["Size"].isin(sz)]

            if "SUPPLIER" in res.columns:
                sup = f3.multiselect("Filter Supplier", sorted(res["SUPPLIER"].unique()),
                                     key=f"spf_{st.session_state.search_clear}")
                if sup:
                    res = res[res["SUPPLIER"].isin(sup)]

            if res.empty:
                st.warning("No items match your filters.")
            else:
                vp = res["Pc. Cost"].dropna() if "Pc. Cost" in res.columns else res["Price"].dropna()
                price_col = "Pc. Cost" if "Pc. Cost" in res.columns else "Price"
                if not vp.empty and vp.min() != vp.max():
                    pr = f4.slider("Pc. Cost Range", float(vp.min()), float(vp.max()),
                                   (float(vp.min()), float(vp.max())),
                                   key=f"prf_{st.session_state.search_clear}")
                    res = res[(res[price_col] >= pr[0]) & (res[price_col] <= pr[1])]

                if res.empty:
                    st.warning("No items match all filters.")
                else:
                    sort_col = "Pc. Cost" if "Pc. Cost" in res.columns else "Price"
                    show = ["BARCODE","ITEM NUM","Description","Size","Pack","Price","Pc. Cost",
                            "Sell Price","SUPPLIER","AISLE","STOCK","USAGE"]
                    show = [c for c in show if c in res.columns]
                    final = res[show].sort_values(sort_col).reset_index(drop=True)
                    final.index += 1

                    st.markdown("---")
                    ma, mb, mc, md, me = st.columns(5)
                    ma.metric("Total Items", len(final))
                    mb.metric("Suppliers", final["SUPPLIER"].nunique() if "SUPPLIER" in final.columns else "N/A")
                    if "Pc. Cost" in final.columns and not final["Pc. Cost"].dropna().empty:
                        mc.metric("Lowest Price", f"${final['Pc. Cost'].min():,.3f}")
                    if "STOCK" in final.columns and "BARCODE" in final.columns:
                        ts = pd.to_numeric(final.groupby("BARCODE")["STOCK"].first(), errors="coerce").fillna(0).sum()
                        md.metric("Total Stock", f"{ts:,.0f}")
                    if "USAGE" in final.columns and "BARCODE" in final.columns:
                        tu = pd.to_numeric(final.groupby("BARCODE")["USAGE"].first(), errors="coerce").fillna(0).sum()
                        me.metric("Total Usage", f"{tu:,.0f}")

                    st.dataframe(final, hide_index=False, height=600, use_container_width=True)
                    st.download_button("📥 Download Results", data=final.to_csv(index=True),
                                       file_name=f"{q}_results.csv", mime="text/csv")


# ======================================================
# TAB 2 — STOCK VALUE
# ======================================================
elif active_tab == "📊 Stock Value":

    st.markdown("## 📊 Stock Value — Current Inventory (Yellow PLU Codes)")
    if reorder_file is None or df_yfull.empty:
        st.info("Upload the RE ORDER workbook to see stock values.")
    else:
        sv = df_yfull.copy()
        sv["STOCK"]       = pd.to_numeric(sv["STOCK"], errors="coerce").fillna(0)
        sv["COST"]        = pd.to_numeric(sv["COST"],  errors="coerce").fillna(0)
        sv["STOCK VALUE"] = sv["STOCK"] * sv["COST"]
        sv["CATEGORY"]    = sv["GROUP"].apply(get_category)
        sv["SUPPLIER"]    = sv["GROUP"].apply(lambda g: ", ".join(get_suppliers(g)))

        ma, mb, mc, md = st.columns(4)
        ma.metric("📦 Total SKUs",        f"{len(sv):,}")
        mb.metric("🔢 Total Units",       f"{sv['STOCK'].sum():,.0f}")
        mc.metric("💲 Total Stock Value", f"${sv['STOCK VALUE'].sum():,.2f}")
        md.metric("✅ SKUs with Stock",   f"{len(sv[sv['STOCK'] > 0]):,}")

        st.markdown("---")

        all_cats_sv = sorted([c for c in sv["CATEGORY"].dropna().unique() if c])
        fmode, fc2, fs2 = st.columns([2, 2.5, 2.5])

        with fmode:
            view_mode = st.radio("View grouped by", ["Category", "Supplier"],
                                 horizontal=True, key="sv_mode")
        with fc2:
            sel_cat2 = st.selectbox("Filter by Category",
                                    ["— All Categories —"] + all_cats_sv, key="sv_cat")
        pool = sv if sel_cat2 == "— All Categories —" else sv[sv["CATEGORY"] == sel_cat2]
        all_sups_sv = sorted(set(s for g in pool["GROUP"] for s in get_suppliers(g) if s))
        with fs2:
            sel_sup2 = st.selectbox("Filter by Supplier",
                                    ["— All Suppliers —"] + all_sups_sv, key="sv_sup")

        filt = sv.copy()
        if sel_cat2 != "— All Categories —":
            filt = filt[filt["CATEGORY"] == sel_cat2]
        if sel_sup2 != "— All Suppliers —":
            filt = filt[filt["GROUP"].apply(lambda g: sel_sup2 in get_suppliers(g))]

        if sel_cat2 != "— All Categories —" or sel_sup2 != "— All Suppliers —":
            label_parts = []
            if sel_cat2 != "— All Categories —": label_parts.append(sel_cat2)
            if sel_sup2 != "— All Suppliers —":  label_parts.append(sel_sup2)
            st.markdown(f"### 📌 Showing: **{' / '.join(label_parts)}**")
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("📦 SKUs",            f"{len(filt):,}")
            r2.metric("🔢 Units on Hand",   f"{filt['STOCK'].sum():,.0f}")
            r3.metric("💲 Stock Value",     f"${filt['STOCK VALUE'].sum():,.2f}")
            r4.metric("✅ SKUs with Stock", f"{len(filt[filt['STOCK'] > 0]):,}")
            st.markdown("---")

        st.markdown(f"### {'📂 By Category' if view_mode == 'Category' else '🏭 By Supplier'}")

        if view_mode == "Category":
            grp = (
                filt.groupby("CATEGORY")
                .agg(SKUs=("PLU CODE","count"),
                     Units=("STOCK","sum"),
                     Stock_Value=("STOCK VALUE","sum"))
                .reset_index()
                .rename(columns={"CATEGORY":"Category","Stock_Value":"Stock Value ($)"})
                .sort_values("Stock Value ($)", ascending=False)
            )
            grp["Stock Value ($)"] = grp["Stock Value ($)"].map("${:,.2f}".format)
            grp["Units"]           = grp["Units"].map("{:,.0f}".format)
            st.dataframe(grp, use_container_width=True, hide_index=True, height=420)
        else:
            sup_rows = []
            for _, row in filt.iterrows():
                sups = get_suppliers(row["GROUP"]) or ["(none)"]
                for s in sups:
                    sup_rows.append({"Supplier":s,"STOCK":row["STOCK"],
                                     "STOCK VALUE":row["STOCK VALUE"],"PLU CODE":row["PLU CODE"]})
            sup_df = pd.DataFrame(sup_rows)
            grp = (
                sup_df.groupby("Supplier")
                .agg(SKUs=("PLU CODE","count"),
                     Units=("STOCK","sum"),
                     Stock_Value=("STOCK VALUE","sum"))
                .reset_index()
                .rename(columns={"Stock_Value":"Stock Value ($)"})
                .sort_values("Stock Value ($)", ascending=False)
            )
            grp["Stock Value ($)"] = grp["Stock Value ($)"].map("${:,.2f}".format)
            grp["Units"]           = grp["Units"].map("{:,.0f}".format)
            st.dataframe(grp, use_container_width=True, hide_index=True, height=420)

        st.markdown("---")

        with st.expander("🔍 View individual items", expanded=False):
            detail = filt[["PLU CODE","DESCRIPTION","CATEGORY","SUPPLIER","COST","STOCK","STOCK VALUE"]].copy()
            detail = detail.sort_values("STOCK VALUE", ascending=False).reset_index(drop=True)
            detail.index += 1
            detail["COST"]        = detail["COST"].map("${:,.2f}".format)
            detail["STOCK VALUE"] = detail["STOCK VALUE"].map("${:,.2f}".format)
            st.dataframe(detail, use_container_width=True, height=420)

            dl = filt[["PLU CODE","DESCRIPTION","CATEGORY","SUPPLIER","COST","STOCK","STOCK VALUE"]].copy()
            st.download_button("📥 Download Stock Value Report (.csv)",
                               data=dl.to_csv(index=False),
                               file_name="stock_value_report.csv",
                               mime="text/csv")


# ======================================================
# TAB 3 — PRICE COMPARISON
# ======================================================
elif active_tab == "🔎 Price Comparison":

    st.markdown("## 🔎 Price Comparison")

    if reorder_file is None:
        st.info("Upload the RE ORDER workbook to see price comparisons.")
    else:
        comp = df_yfull[["PLU CODE","DESCRIPTION","COST"]].copy()
        comp = comp.merge(df_price1, on="PLU CODE", how="left")

        ep_cols  = ["BARCODE","Pc. Cost","Sell Price"]
        ep_avail = [c for c in ep_cols if c in df_prices.columns]
        if "BARCODE" in df_prices.columns:
            ep   = df_prices[ep_avail].drop_duplicates(subset=["BARCODE"])
            comp = comp.merge(ep, left_on="PLU CODE", right_on="BARCODE", how="left")
            comp = comp.drop(columns=["BARCODE"], errors="ignore")

        for col in ["COST","PRICE 1","Pc. Cost","Sell Price"]:
            if col in comp.columns:
                comp[col] = pd.to_numeric(comp[col], errors="coerce")

        TOL = 0.01
        def match_status(a, b):
            if pd.isna(a) or pd.isna(b):
                return "⚠️ Missing"
            return "✅ Match" if abs(a - b) <= TOL else "❌ Mismatch"

        comp["COST MATCH"]    = comp.apply(lambda r: match_status(r["COST"], r.get("Pc. Cost")), axis=1)
        comp["SELLING MATCH"] = comp.apply(lambda r: match_status(r.get("PRICE 1"), r.get("Sell Price")), axis=1)
        comp = comp.reset_index(drop=True)
        comp.index += 1

        st.markdown("---")

        # ── Cost Price ───────────────────────────────────────
        st.markdown("### 💰 Cost Price Comparison")
        st.caption("RE ORDER sheet (col C: COST)  vs  EXISTING PRICES sheet (col G: Pc. Cost)")

        cost_filter = st.selectbox(
            "Filter by match status",
            ["All", "✅ Match", "❌ Mismatch", "⚠️ Missing"],
            key="cost_filter"
        )

        cost_df = comp[["PLU CODE","DESCRIPTION","COST","Pc. Cost","COST MATCH"]].copy()
        cost_df.columns = ["PLU CODE","DESCRIPTION","RE ORDER Cost","Existing Pc. Cost","Status"]
        if cost_filter != "All":
            cost_df = cost_df[cost_df["Status"] == cost_filter]

        all_cost = comp["COST MATCH"].value_counts()
        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("Total",      len(comp))
        cc2.metric("✅ Match",   int(all_cost.get("✅ Match",   0)))
        cc3.metric("❌ Mismatch",int(all_cost.get("❌ Mismatch",0)))
        cc4.metric("⚠️ Missing", int(all_cost.get("⚠️ Missing", 0)))

        st.dataframe(
            cost_df.reset_index(drop=True),
            use_container_width=True,
            height=380,
            column_config={
                "RE ORDER Cost":     st.column_config.NumberColumn(format="$%.2f"),
                "Existing Pc. Cost": st.column_config.NumberColumn(format="$%.2f"),
                "Status":            st.column_config.TextColumn("Status"),
            },
            hide_index=True
        )

        st.markdown("---")

        # ── Selling Price ────────────────────────────────────
        st.markdown("### 🏷️ Selling Price Comparison")
        st.caption("RE ORDER sheet (col F: PRICE 1)  vs  EXISTING PRICES sheet (col H: Sell Price)")

        sell_filter = st.selectbox(
            "Filter by match status",
            ["All", "✅ Match", "❌ Mismatch", "⚠️ Missing"],
            key="sell_filter"
        )

        sell_df = comp[["PLU CODE","DESCRIPTION","PRICE 1","Sell Price","SELLING MATCH"]].copy()
        sell_df.columns = ["PLU CODE","DESCRIPTION","RE ORDER Price 1","Existing Sell Price","Status"]
        if sell_filter != "All":
            sell_df = sell_df[sell_df["Status"] == sell_filter]

        all_sell = comp["SELLING MATCH"].value_counts()
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Total",      len(comp))
        sc2.metric("✅ Match",   int(all_sell.get("✅ Match",   0)))
        sc3.metric("❌ Mismatch",int(all_sell.get("❌ Mismatch",0)))
        sc4.metric("⚠️ Missing", int(all_sell.get("⚠️ Missing", 0)))

        st.dataframe(
            sell_df.reset_index(drop=True),
            use_container_width=True,
            height=380,
            column_config={
                "RE ORDER Price 1":    st.column_config.NumberColumn(format="$%.2f"),
                "Existing Sell Price": st.column_config.NumberColumn(format="$%.2f"),
                "Status":              st.column_config.TextColumn("Status"),
            },
            hide_index=True
        )
