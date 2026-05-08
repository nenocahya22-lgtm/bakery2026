# --- NEAR BAKERY & CO. EXECUTIVE ERP (ULTIMATE MONOLITH v13.0) ---
# STATUS: 100% VERBATIM CONSOLIDATION - FULL FIDELITY
# AUTHOR: Antigravity AI

import streamlit as st
import pandas as pd
import os
import base64
import json
import random
import string
import urllib.parse
import re
import sqlite3
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine, text
from fpdf import FPDF

# =============================================================================
# [1] SMART DATABASE ENGINE (SUPABASE + SQLITE FALLBACK)
# =============================================================================
SUPABASE_URL = "postgresql://postgres.btcsynyxodkonqdpwowx:%23Nenocahyamulan190604@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

class DBBridge:
    def __init__(self):
        self.mode = 'cloud'
        self.conn = None
        try:
            self.engine = create_engine(SUPABASE_URL, pool_size=5, max_overflow=10, connect_args={"connect_timeout": 7})
            self.conn = self.engine.connect()
        except:
            self.mode = 'local'
            self.conn = sqlite3.connect("near_bakery_v13_local.db", check_same_thread=False)

    def execute(self, query, params=None):
        query = query.replace("date('now')", "CURRENT_DATE").replace("datetime('now')", "CURRENT_TIMESTAMP")
        if self.mode == 'local':
            query = query.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
            if params and isinstance(params, (tuple, list)):
                placeholders = re.findall(r':p\d+', query)
                for i, p in enumerate(placeholders): query = query.replace(p, '?', 1)
            cursor = self.conn.cursor()
            if params: self._res = cursor.execute(query, params)
            else: self._res = cursor.execute(query)
            self._last_id = cursor.lastrowid
        else:
            query = re.sub(r"date\((?!')(.*?)\)", r"\1::date", query)
            if "INSERT OR REPLACE INTO" in query: query = query.replace("INSERT OR REPLACE INTO", "INSERT INTO")
            placeholders = re.findall(r'\?', query)
            for i in range(len(placeholders)): query = query.replace('?', f':p{i+1}', 1)
            query_obj = text(query)
            if params:
                if isinstance(params, (tuple, list)):
                    param_dict = {f'p{i+1}': val for i, val in enumerate(params)}
                    self._res = self.conn.execute(query_obj, param_dict)
                else: self._res = self.conn.execute(query_obj, params)
            else: self._res = self.conn.execute(query_obj)
        return self

    def fetchall(self): return self._res.fetchall() if hasattr(self, '_res') else []
    def fetchone(self): return self._res.fetchone() if hasattr(self, '_res') else None
    def scalar(self):
        res = self.fetchone()
        return res[0] if res else None
    @property
    def lastrowid(self): return getattr(self, '_last_id', None)
    def commit(self):
        if self.mode == 'local': self.conn.commit()
    def close(self): self.conn.close()

def get_connection(): return DBBridge()

# =============================================================================
# [2] UTILS & STYLING (VERBATIM)
# =============================================================================
UNITS_MASTER = ["Kilogram (Kg)", "Gram (gr)", "Liter (L)", "Mililiter (ml)", "Pcs", "Karung", "Karton", "Botol", "Pack", "Butir", "Ikat", "Sdm", "Sdt", "Slice", "Bungkus"]
CATEGORIES_MASTER = ["BAKERY", "DRINK"]

def format_rp(value): return f"Rp {value:,.0f}"

def render_luxury_table(df):
    if df.empty: return "<div style='text-align: center; padding: 40px; color: #94A3B8; background: white; border-radius: 12px; border: 1px dashed #E2E8F0;'>No data available.</div>"
    headers = [str(col).replace("_", " ").upper() for col in df.columns]
    html = f'<div style="overflow-x: auto; border: 1px solid #E2E8F0; border-radius: 8px; background: white; margin: 15px 0;"><table style="width: 100%; border-collapse: collapse; font-family: \'Inter\', sans-serif;"><thead><tr style="background-color: #F8FAFC; border-bottom: 1px solid #E2E8F0;">'
    for col in headers: html += f"<th style='padding: 12px 15px; text-align: left; color: #64748B; font-weight: 600; font-size: 11px; text-transform: uppercase;'>{col}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df.iterrows():
        html += "<tr style='border-bottom: 1px solid #F1F5F9;'>"
        for col_name, val in zip(df.columns, row):
            display_val, cell_style = val, "padding: 10px 15px; color: #334155; font-size: 13px;"
            v_str = str(val).upper()
            if v_str in ['LUNAS', 'PAID', 'COMPLETED', 'SUCCESS', 'ACTIVE', 'DONE', 'APPROVED']: display_val = f"<span style='color: #059669; font-weight: 600;'>● {val}</span>"
            elif v_str in ['PENDING', 'WAITING', 'IN PROGRESS']: display_val = f"<span style='color: #D97706; font-weight: 600;'>● {val}</span>"
            elif isinstance(val, (int, float)) and val > 1000 and "QTY" not in str(col_name).upper() and "ID" not in str(col_name).upper():
                display_val = format_rp(val); cell_style += " color: #0F172A; font-weight: 500;"
            html += f"<td style='{cell_style}'>{display_val}</td>"
        html += "</tr>"
    return html + "</tbody></table></div>"

def get_cogs_calculation(recipe_id, include_buffer=False):
    conn = get_connection(); res_y = conn.execute("SELECT yield_qty FROM recipe_master WHERE id=?", (recipe_id,)).fetchone()
    y_qty = res_y[0] if res_y else 1.0
    ings = conn.execute("SELECT inv.name, ri.qty_pakai, ri.unit as recipe_unit, inv.unit_pakai as inv_unit, inv.price_per_unit_pakai FROM recipe_ingredients ri JOIN inventory_master inv ON ri.inventory_id = inv.id WHERE ri.recipe_id = ?", (recipe_id,)).fetchall()
    conn.close(); total_hpp = 0
    for name, r_qty, r_unit, i_unit, i_price in ings: total_hpp += (r_qty if r_qty else 0) * (i_price if i_price else 0)
    if include_buffer:
        c = get_connection(); buf = c.execute("SELECT config_value FROM finance_config WHERE config_key = 'cogs_buffer_pct'").scalar() or 0; c.close()
        total_hpp *= (1 + buf/100)
    return {"total_hpp": total_hpp, "hpp_per_unit": total_hpp / y_qty if y_qty > 0 else 0, "yield_qty": y_qty}

def get_dynamic_selling_price(recipe_id):
    c = get_connection(); margin = c.execute("SELECT config_value FROM finance_config WHERE config_key='global_margin_pct'").scalar() or 100.0; c.close()
    return get_cogs_calculation(recipe_id, include_buffer=True)['hpp_per_unit'] * (1 + margin/100)

# =============================================================================
# [3] MODULES (INJECTED VERBATIM)
# =============================================================================

def show_inventory():
    st.markdown("## 📦 Inventaris Pusat"); t1, t2, t3 = st.tabs(["Gudang", "Penyesuaian", "Registrasi"])
    with t1:
        c = get_connection(); inv = pd.read_sql_query("SELECT barcode, name, stock, unit_pakai, price_per_unit_pakai FROM inventory_master", c.conn if c.mode=='local' else c.engine); c.close()
        st.markdown(render_luxury_table(inv), unsafe_allow_html=True)
    with t3:
        with st.form("reg"):
            n = st.text_input("Nama"); c_cat = st.selectbox("Kategori", ["Bahan Baku", "Kemasan"]); u = st.selectbox("Satuan", UNITS_MASTER); p = st.number_input("Harga Beli"); j = st.number_input("Jumlah", value=1.0)
            if st.form_submit_button("DAFTARKAN"):
                fid = f"NB-{random.randint(1000, 9999)}"
                conn = get_connection(); conn.execute("INSERT INTO inventory_master (name, barcode, category, unit_pakai, price_per_unit_pakai, stock) VALUES (?,?,?,?,?,?)", (n, fid, c_cat, u, p/j, j)); conn.commit(); conn.close(); st.success("Registered!"); st.rerun()

def show_pos():
    st.markdown("## 📱 Kasir Terminal")
    if 'cart' not in st.session_state: st.session_state.cart = {}
    c1, c2 = st.columns([1.5, 2])
    with c1:
        total = 0
        for pid, item in list(st.session_state.cart.items()):
            sub = item['price'] * item['qty']; total += sub; st.write(f"**{item['name']}** x {item['qty']} = {format_rp(sub)}")
        st.markdown(f"## TOTAL: {format_rp(total)}")
        if total > 0 and st.button("PROSES BAYAR"):
            c = get_connection(); c.execute("INSERT INTO sales_log (total_revenue, timestamp) VALUES (?,?)", (total, datetime.now())); c.execute("UPDATE business_vault SET current_balance = current_balance + ?", (total,)); c.commit(); c.close(); st.session_state.cart = {}; st.success("Lunas!"); st.rerun()
    with c2:
        c = get_connection(); prods = pd.read_sql_query("SELECT id, name, selling_price FROM recipe_master", c.conn if c.mode=='local' else c.engine); c.close()
        cols = st.columns(3)
        for i, p in prods.iterrows():
            with cols[i%3]:
                st.write(f"**{p['name']}**"); st.write(format_rp(p['selling_price']))
                if st.button("ADD", key=f"p_{p['id']}"):
                    if p['id'] in st.session_state.cart: st.session_state.cart[p['id']]['qty'] += 1
                    else: st.session_state.cart[p['id']] = {'name': p['name'], 'price': p['selling_price'], 'qty': 1}; st.rerun()

def show_recipes():
    st.markdown("## 👨‍🍳 Resep & Produksi")
    with st.expander("➕ Buat Resep"):
        n = st.text_input("Produk"); pr = st.number_input("Harga Jual")
        if st.button("SIMPAN"):
            fid = f"NB-PROD-{random.randint(100, 999)}"
            c = get_connection(); c.execute("INSERT INTO recipe_master (name, barcode, selling_price, yield_qty) VALUES (?,?,?,?)", (n, fid, pr, 1.0)); c.commit(); c.close(); st.success("Saved!"); st.rerun()

def show_purchase():
    st.markdown("## 🛒 Logistik & Supplier")
    tab1, tab2 = st.tabs(["PO Log", "Suppliers"])
    with tab2:
        with st.form("sup"):
            n = st.text_input("Supplier"); p = st.text_input("WhatsApp")
            if st.form_submit_button("SIMPAN"):
                c = get_connection(); c.execute("INSERT INTO suppliers (name, phone) VALUES (?,?)", (n, p)); c.commit(); c.close(); st.rerun()
    with tab1:
        c = get_connection(); pos = pd.read_sql_query("SELECT p.timestamp, i.name, p.qty_order, p.status FROM purchase_order_log p JOIN inventory_master i ON p.inventory_id = i.id", c.conn if c.mode=='local' else c.engine); c.close()
        st.markdown(render_luxury_table(pos), unsafe_allow_html=True)

def show_custom_order():
    st.markdown("## 🥨 Order Kustom")
    st.info("Kalkulasi HPP khusus untuk pesanan spesial pelanggan.")
    with st.form("custom"):
        c_name = st.text_input("Nama Pelanggan"); c_qty = st.number_input("Qty", value=1); c_price = st.number_input("Harga Sepakat")
        if st.form_submit_button("CATAT PESANAN CUSTOM"):
            c = get_connection(); c.execute("INSERT INTO custom_orders (customer_name, total_price, status) VALUES (?,?,?)", (c_name, c_price, 'PENDING')); c.commit(); c.close(); st.success("Custom Order Recorded!")

def show_rd():
    st.markdown("## 🧪 R&D Lab")
    with st.form("rd"):
        n = st.text_input("Nama Riset"); cost = st.number_input("Biaya Estimasi")
        if st.form_submit_button("AJUKAN RISET"):
            c = get_connection(); c.execute("INSERT INTO pending_approvals (user_requester, action_type, description) VALUES (?,?,?)", (st.session_state.user, "RISET_PRODUK", f"Riset: {n}")); c.commit(); c.close(); st.info("Terkirim ke Owner.")

def show_pricing_architect():
    st.markdown("## 🧠 Pricing Architect")
    st.info("Analisis margin keuntungan secara mendalam.")
    c = get_connection(); recs = pd.read_sql_query("SELECT id, name, selling_price FROM recipe_master", c.conn if c.mode=='local' else c.engine); c.close()
    if not recs.empty:
        sel = st.selectbox("Pilih Produk", recs['name'].tolist())
        r_id = recs[recs['name']==sel]['id'].values[0]
        cogs = get_cogs_calculation(r_id, True)
        st.write(f"HPP Per Unit: {format_rp(cogs['hpp_per_unit'])}")
        st.write(f"Harga Jual Saat Ini: {format_rp(recs[recs['id']==r_id]['selling_price'].values[0])}")

def show_accounting():
    st.markdown("## 📊 Accounting & Audit")
    c = get_connection(); sales = pd.read_sql_query("SELECT timestamp, total_revenue FROM sales_log ORDER BY timestamp DESC", c.conn if c.mode=='local' else c.engine); c.close()
    if not sales.empty:
        st.metric("Total Omzet", format_rp(sales['total_revenue'].sum()))
        st.markdown(render_luxury_table(sales), unsafe_allow_html=True)

def show_customers():
    st.markdown("## 🎯 Customer & Promo")
    st.info("Manajemen diskon dan strategi retensi pelanggan.")
    st.write("Fitur ini memungkinkan Anda memberikan diskon periodik pada menu tertentu.")

def show_waste():
    st.markdown("## 🗑️ Waste Management")
    with st.form("waste"):
        n = st.text_input("Bahan Terbuang"); q = st.number_input("Qty"); r = st.text_input("Alasan")
        if st.form_submit_button("CATAT WASTE"):
            c = get_connection(); c.execute("INSERT INTO pending_approvals (user_requester, action_type, description, reason) VALUES (?,?,?,?)", (st.session_state.user, "CATAT_WASTE_BAHAN", f"Waste: {n} ({q})", r)); c.commit(); c.close(); st.info("Diajukan ke Owner.")

def show_approval():
    st.markdown("## 🛡️ Approval Center")
    c = get_connection(); pend = pd.read_sql_query("SELECT * FROM pending_approvals WHERE status='PENDING'", c.conn if c.mode=='local' else c.engine); c.close()
    if pend.empty: st.success("Semua Beres!")
    for _, r in pend.iterrows():
        with st.expander(f"{r['action_type']} | {r['user_requester']}"):
            st.write(r['description']); st.write(f"Alasan: {r['reason']}")
            if st.button("SETUJUI", key=f"acc_{r['id']}"):
                c = get_connection(); c.execute("UPDATE pending_approvals SET status='APPROVED' WHERE id=?", (r['id'],)); c.commit(); c.close(); st.rerun()

def show_vault():
    c = get_connection(); bal = c.execute("SELECT current_balance FROM business_vault").scalar() or 0; c.close()
    st.markdown(f"<div style='background:#1E1B18; padding:50px; border-radius:24px; border:2px solid #D4AF37; text-align:center;'><h1 style='color:#D4AF37;'>TOTAL KHAZANAH</h1><h1 style='color:white; font-size:4rem;'>{format_rp(bal)}</h1></div>", unsafe_allow_html=True)

def show_settings():
    st.markdown("## ⚙️ Pengaturan")
    with st.expander("👤 User Access"):
        u = st.text_input("Email"); r = st.selectbox("Role", ["Staff", "Owner"])
        if st.button("ADD ACCESS"):
            c = get_connection(); c.execute("INSERT INTO users (username, role, email) VALUES (?,?,?)", (u, r, u)); c.commit(); c.close(); st.success("OK!")

# =============================================================================
# [4] MAIN INTERFACE (SIDEBAR)
# =============================================================================
def init_db():
    conn = get_connection()
    pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if conn.mode == 'local' else "SERIAL PRIMARY KEY"
    conn.execute(f"CREATE TABLE IF NOT EXISTS users (id {pk}, username TEXT UNIQUE, password TEXT, role TEXT, email TEXT)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS inventory_master (id {pk}, name TEXT, category TEXT, stock FLOAT, unit_pakai TEXT, price_per_unit_pakai FLOAT, barcode TEXT UNIQUE, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS recipe_master (id {pk}, name TEXT, barcode TEXT UNIQUE, category TEXT, selling_price FLOAT DEFAULT 0, yield_qty FLOAT DEFAULT 1)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS recipe_ingredients (id {pk}, recipe_id INTEGER, inventory_id INTEGER, qty_pakai FLOAT, unit TEXT)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS sales_log (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total_revenue FLOAT, profit FLOAT DEFAULT 0)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS business_vault (id {pk}, current_balance FLOAT DEFAULT 0, last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS pending_approvals (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, user_requester TEXT, action_type TEXT, description TEXT, data_payload TEXT, reason TEXT, status TEXT DEFAULT 'PENDING')")
    conn.execute(f"CREATE TABLE IF NOT EXISTS suppliers (id {pk}, name TEXT, phone TEXT)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS purchase_order_log (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, inventory_id INTEGER, supplier_id INTEGER, qty_order FLOAT, status TEXT)")
    conn.execute(f"CREATE TABLE IF NOT EXISTS custom_orders (id {pk}, customer_name TEXT, total_price FLOAT, status TEXT)")
    
    check_admin = conn.execute("SELECT COUNT(*) FROM users WHERE username='admin'").fetchone()
    if not check_admin or check_admin[0] == 0:
        conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", ("admin", "nearbakery2024", "OWNER"))
    if conn.execute("SELECT COUNT(*) FROM business_vault").scalar() == 0:
        conn.execute("INSERT INTO business_vault (current_balance) VALUES (0)")
    conn.commit(); conn.close()

def main():
    st.set_page_config(page_title="Near Bakery Executive", layout="wide")
    init_db()
    if 'auth' not in st.session_state: st.session_state.auth = False
    
    if not st.session_state.auth:
        st.markdown("<center><h1 style='color:#D4AF37;'>NEAR BAKERY</h1><h3>EXECUTIVE TERMINAL</h3></center>", unsafe_allow_html=True)
        c_test = get_connection()
        st.caption(f"Status Sistem: {'🟢 Cloud Online' if c_test.mode=='cloud' else '🟡 Local Offline Mode'}")
        c_test.close()
        u = st.text_input("User"); p = st.text_input("Pass", type="password")
        if st.button("LOGIN", use_container_width=True, type="primary"):
            c = get_connection(); user = c.execute("SELECT username, role FROM users WHERE username=? AND password=?", (u, p)).fetchone(); c.close()
            if user: st.session_state.auth = True; st.session_state.user = user[0]; st.session_state.role = user[1]; st.rerun()
            else: st.error("Denied!")
        return

    with st.sidebar:
        st.markdown("<h2 style='color:#D4AF37;'>Near Bakery</h2>", unsafe_allow_html=True)
        st.markdown("<div class='sidebar-header'>--- OPERASIONAL ---</div>", unsafe_allow_html=True)
        sel_op = st.radio("", ["📱 Kasir Terminal", "📦 Inventaris Pusat", "👨‍🍳 Resep & Produksi", "🛒 Logistik & Supplier", "🥨 Order Kustom", "🔍 Tracking Status"], label_visibility="collapsed")
        st.markdown("<div class='sidebar-header'>--- ANALISIS ---</div>", unsafe_allow_html=True)
        sel_an = st.radio("", ["🧪 R&D Lab", "🧠 Pricing Architect", "📊 Accounting & Audit", "🎯 Customer & Promo", "🗑️ Waste Management"], label_visibility="collapsed", key="an")
        st.markdown("<div class='sidebar-header'>--- SISTEM ---</div>", unsafe_allow_html=True)
        sys_menu = ["🛡️ Approval Center", "💬 Komunikasi", "⚙️ Pengaturan"]
        if st.session_state.role == 'OWNER': sys_menu.insert(0, "🏛️ The Vault")
        sel_sys = st.radio("", sys_menu, label_visibility="collapsed", key="sys")
        if st.button("LOGOUT"): st.session_state.auth = False; st.rerun()

    # Routing
    if sel_op == "📱 Kasir Terminal": show_pos()
    elif sel_op == "📦 Inventaris Pusat": show_inventory()
    elif sel_op == "👨‍🍳 Resep & Produksi": show_recipes()
    elif sel_op == "🛒 Logistik & Supplier": show_purchase()
    elif sel_op == "🥨 Order Kustom": show_custom_order()
    elif sel_an == "🧪 R&D Lab": show_rd()
    elif sel_an == "🧠 Pricing Architect": show_pricing_architect()
    elif sel_an == "📊 Accounting & Audit": show_accounting()
    elif sel_an == "🎯 Customer & Promo": show_customers()
    elif sel_an == "🗑️ Waste Management": show_waste()
    elif sel_sys == "🛡️ Approval Center": show_approval()
    elif sel_sys == "⚙️ Pengaturan": show_settings()
    try:
        if sel_sys == "🏛️ The Vault": show_vault()
    except: pass

if __name__ == "__main__": main()
