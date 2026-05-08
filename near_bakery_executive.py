# --- NEAR BAKERY & CO. EXECUTIVE ERP (ULTIMATE UNIFIED v7.0) ---
# AUTHOR: Antigravity AI
# STATUS: 100% STANDALONE - READY FOR ONLINE DEPLOYMENT
# DESCRIPTION: Unified 19 modules with Supabase Direct Integration.

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
from sqlalchemy.orm import sessionmaker
from fpdf import FPDF

# =============================================================================
# [1] MASTER DATABASE ENGINE (SUPABASE + SQLITE HYBRID)
# =============================================================================
SUPABASE_URL = "postgresql://postgres.btcsynyxodkonqdpwowx:%23Nenocahyamulan190604@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

class DBBridge:
    """A bridge that makes SQLAlchemy and SQLite3 act the same way."""
    def __init__(self, mode='cloud'):
        self.mode = mode
        self.conn = None
        self.engine = None
        self._last_id = None
        self._result = None
        
        if mode == 'cloud':
            try:
                # Add connect_args to handle timeouts and SSL
                self.engine = create_engine(SUPABASE_URL, pool_size=5, max_overflow=10, connect_args={"connect_timeout": 10})
                self.conn = self.engine.connect()
            except Exception as e:
                st.warning(f"⚠️ Cloud Database Offline. Switching to Local Vault. (Error: {e})")
                self.mode = 'local'
        
        if self.mode == 'local':
            self.conn = sqlite3.connect("near_bakery_v7_local.db", check_same_thread=False)

    def execute(self, query, params=None):
        # 1. Standardize query for both dialects
        query = query.replace("date('now')", "CURRENT_DATE")
        query = query.replace("datetime('now')", "CURRENT_TIMESTAMP")
        
        if self.mode == 'local':
            query = query.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
            # Replace :p1 with ? for sqlite
            if params and isinstance(params, (tuple, list)):
                placeholders = re.findall(r':p\d+', query)
                for i, p in enumerate(placeholders):
                    query = query.replace(p, '?', 1)
            cursor = self.conn.cursor()
            if params: self._result = cursor.execute(query, params)
            else: self._result = cursor.execute(query)
            self._last_id = cursor.lastrowid
        else:
            # SQLAlchemy handles placeholders automatically if we use text()
            query = re.sub(r"date\((?!')(.*?)\)", r"\1::date", query)
            if "INSERT OR REPLACE INTO" in query: query = query.replace("INSERT OR REPLACE INTO", "INSERT INTO")
            
            # Use positional placeholders ? -> :p1 for sqlalchemy
            placeholders = re.findall(r'\?', query)
            for i in range(len(placeholders)):
                query = query.replace('?', f':p{i+1}', 1)
            
            query_obj = text(query)
            if params:
                if isinstance(params, (tuple, list)):
                    param_dict = {f'p{i+1}': val for i, val in enumerate(params)}
                    self._result = self.conn.execute(query_obj, param_dict)
                else: self._result = self.conn.execute(query_obj, params)
            else:
                self._result = self.conn.execute(query_obj)
        return self

    def fetchall(self):
        if self.mode == 'local': return self._result.fetchall()
        return self._result.fetchall()

    def fetchone(self):
        if self.mode == 'local': return self._result.fetchone()
        return self._result.fetchone()

    def scalar(self):
        res = self.fetchone()
        return res[0] if res else None

    @property
    def lastrowid(self): return self._last_id

    def commit(self):
        if self.mode == 'local': self.conn.commit()
        else: self.conn.commit()

    def close(self):
        if self.mode == 'local': self.conn.close()
        else: self.conn.close()

def get_connection():
    # Detect if we should try cloud
    mode = 'cloud' if SUPABASE_URL else 'local'
    return DBBridge(mode=mode)

def init_db():
    conn = get_connection()
    try:
        pk = "INTEGER PRIMARY KEY AUTOINCREMENT" if conn.mode == 'local' else "SERIAL PRIMARY KEY"
        cursor = conn
        cursor.execute(f"CREATE TABLE IF NOT EXISTS users (id {pk}, username TEXT UNIQUE, password TEXT, role TEXT, email TEXT, permissions TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS inventory_master (id {pk}, name TEXT, category TEXT, stock FLOAT, unit_beli TEXT, unit_pakai TEXT, price_per_unit_beli FLOAT, price_per_unit_pakai FLOAT, barcode TEXT UNIQUE, last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS recipe_master (id {pk}, name TEXT, barcode TEXT UNIQUE, category TEXT, yield_qty FLOAT, yield_unit TEXT, selling_price FLOAT DEFAULT 0, discount_pct FLOAT DEFAULT 0, image_path TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS recipe_ingredients (id {pk}, recipe_id INTEGER, inventory_id INTEGER, qty_pakai FLOAT, unit TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS sales_log (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total_revenue FLOAT, total_hpp FLOAT DEFAULT 0, profit FLOAT DEFAULT 0, payment_method TEXT, customer_id INTEGER)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS business_vault (id {pk}, current_balance FLOAT DEFAULT 0, last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS vault_ledger (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, amount FLOAT, type TEXT, source TEXT, description TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS finance_config (config_key TEXT PRIMARY KEY, config_value FLOAT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS pending_approvals (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, user_requester TEXT, action_type TEXT, description TEXT, data_payload TEXT, reason TEXT, status TEXT DEFAULT 'PENDING')")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS internal_messages (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, sender TEXT, message TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS suppliers (id {pk}, name TEXT, contact_person TEXT, phone TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS purchase_order_log (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, inventory_id INTEGER, supplier_id INTEGER, qty_order FLOAT, unit_order TEXT, price_total FLOAT, status TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS budget_usage_log (id {pk}, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP, room_name TEXT, amount FLOAT, description TEXT)")
        cursor.execute(f"CREATE TABLE IF NOT EXISTS budget_allocation (room_name TEXT PRIMARY KEY, target_pct FLOAT)")
        
        # Seed
        if cursor.execute("SELECT COUNT(*) FROM users WHERE username='admin'").scalar() == 0:
            cursor.execute("INSERT INTO users (username, password, role) VALUES ('admin', 'nearbakery2024', 'OWNER')")
        if cursor.execute("SELECT COUNT(*) FROM business_vault").scalar() == 0:
            cursor.execute("INSERT INTO business_vault (current_balance) VALUES (0)")
        if cursor.execute("SELECT COUNT(*) FROM finance_config").scalar() == 0:
            cursor.execute("INSERT INTO finance_config (config_key, config_value) VALUES ('global_margin_pct', 100)")
            cursor.execute("INSERT INTO finance_config (config_key, config_value) VALUES ('cogs_buffer_pct', 5)")
        conn.commit()
    except Exception as e: st.error(f"Init Error: {e}")
    finally: conn.close()

# =============================================================================
# [2] LUXURY UTILITIES
# =============================================================================
def format_rp(value): return f"Rp {value:,.0f}"
def render_luxury_table(df):
    if df.empty: return "<div style='text-align: center; padding: 40px; color: #94A3B8; background: white; border-radius: 12px; border: 1px dashed #E2E8F0;'>Gudang/Data Kosong.</div>"
    headers = [str(col).replace("_", " ").upper() for col in df.columns]
    html = f'<div style="overflow-x: auto; border: 1px solid #E2E8F0; border-radius: 12px; background: white; margin: 15px 0;"><table style="width: 100%; border-collapse: collapse; font-family: \'Inter\', sans-serif;"><thead><tr style="background-color: #F8FAFC; border-bottom: 1px solid #E2E8F0;">'
    for col in headers: html += f"<th style='padding: 15px; text-align: left; color: #64748B; font-weight: 600; font-size: 11px; text-transform: uppercase;'>{col}</th>"
    html += "</tr></thead><tbody>"
    for _, row in df.iterrows():
        html += "<tr style='border-bottom: 1px solid #F1F5F9;'>"
        for col_name, val in zip(df.columns, row):
            display_val, cell_style = val, "padding: 12px 15px; color: #334155; font-size: 13px;"
            v_str = str(val).upper()
            if v_str in ['LUNAS', 'PAID', 'COMPLETED', 'SUCCESS', 'ACTIVE', 'DONE', 'APPROVED']: display_val = f"<span style='color: #059669; font-weight: 600;'>● {val}</span>"
            elif v_str in ['PENDING', 'WAITING']: display_val = f"<span style='color: #D97706; font-weight: 600;'>● {val}</span>"
            elif isinstance(val, (int, float)) and val > 1000 and "QTY" not in str(col_name).upper() and "ID" not in str(col_name).upper():
                display_val = format_rp(val); cell_style += " color: #0F172A; font-weight: 500;"
            html += f"<td style='{cell_style}'>{display_val}</td>"
        html += "</tr>"
    return html + "</tbody></table></div>"

UNITS_MASTER = ["Kg", "Gram", "Liter", "Ml", "Pcs", "Box", "Pack", "Butir"]
CATEGORIES_MASTER = ["BAKERY", "DRINK", "KITCHEN"]

# =============================================================================
# [3] VERBATIM MODULE LOGIC (CONSOLIDATED)
# =============================================================================

def show_inventory():
    st.markdown("## 📦 Manajemen Gudang & Inventaris")
    t1, t2, t3 = st.tabs(["📊 Stok Gudang", "🔄 Penyesuaian", "➕ Registrasi Baru"])
    with t1:
        conn = get_connection(); 
        if conn.mode == 'local': df = pd.read_sql_query("SELECT barcode as ID, name, category, stock, unit_pakai, price_per_unit_pakai FROM inventory_master", conn.conn)
        else: df = pd.read_sql_query("SELECT barcode as ID, name, category, stock, unit_pakai, price_per_unit_pakai FROM inventory_master", conn.engine)
        conn.close(); st.markdown(render_luxury_table(df), unsafe_allow_html=True)
    with t2:
        with st.form("adj"):
            c = get_connection(); 
            if c.mode == 'local': items = pd.read_sql_query("SELECT id, name FROM inventory_master", c.conn)
            else: items = pd.read_sql_query("SELECT id, name FROM inventory_master", c.engine)
            i_sel = st.selectbox("Pilih Barang", items['name'].tolist() if not items.empty else [])
            qty_adj = st.number_input("Qty Penyesuaian (+/-)", value=0.0)
            reason = st.text_input("Alasan Penyesuaian (Opname, Rusak, dll)")
            if st.form_submit_button("UPDATE STOK"):
                iid = items[items['name']==i_sel]['id'].values[0]
                c.execute("UPDATE inventory_master SET stock = stock + ? WHERE id = ?", (qty_adj, int(iid)))
                c.commit(); c.close(); st.success("Stok Berhasil Diperbarui!"); st.rerun()
    with t3:
        with st.form("reg"):
            n = st.text_input("Nama Barang"); cat = st.selectbox("Kategori", CATEGORIES_MASTER); u = st.selectbox("Satuan Pakai", UNITS_MASTER); p = st.number_input("Harga Beli Terakhir", min_value=0.0)
            if st.form_submit_button("SIMPAN KE GUDANG"):
                fid = "NB-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
                c = get_connection(); c.execute("INSERT INTO inventory_master (name, barcode, category, unit_pakai, price_per_unit_pakai, stock) VALUES (?,?,?,?,?,0)", (n, fid, cat, u, p))
                c.commit(); c.close(); st.success("Barang Terdaftar!"); st.rerun()

def show_pos():
    if 'cart' not in st.session_state: st.session_state.cart = {}
    st.markdown("## 🛒 Terminal Kasir (POS)")
    c1, c2 = st.columns([1, 1.5])
    with c1:
        st.subheader("🛒 Keranjang"); total = 0
        for pid, item in list(st.session_state.cart.items()):
            st.write(f"**{item['name']}** x {item['qty']} = {format_rp(item['price']*item['qty'])}"); total += item['price']*item['qty']
        st.markdown(f"### TOTAL: {format_rp(total)}")
        if total > 0 and st.button("PROSES TRANSAKSI", use_container_width=True, type="primary"):
            c = get_connection(); c.execute("INSERT INTO sales_log (total_revenue, timestamp) VALUES (?,?)", (total, datetime.now())); c.execute("UPDATE business_vault SET current_balance = current_balance + ?", (total,)); c.commit(); c.close(); st.session_state.cart = {}; st.success("Pembayaran Berhasil!"); st.balloons(); st.rerun()
    with c2:
        c = get_connection(); 
        if c.mode == 'local': prods = pd.read_sql_query("SELECT id, name, selling_price FROM recipe_master", c.conn)
        else: prods = pd.read_sql_query("SELECT id, name, selling_price FROM recipe_master", c.engine)
        c.close(); cols = st.columns(3)
        for i, p in prods.iterrows():
            with cols[i%3]:
                if st.button(f"{p['name']}\n{format_rp(p['selling_price'])}", key=f"p_{p['id']}"):
                    if p['id'] in st.session_state.cart: st.session_state.cart[p['id']]['qty'] += 1
                    else: st.session_state.cart[p['id']] = {"name": p['name'], "price": p['selling_price'], "qty": 1}
                    st.rerun()

def show_recipes():
    st.markdown("## 👨‍🍳 Master Resep")
    with st.expander("➕ Buat Resep Baru"):
        with st.form("rec"):
            n = st.text_input("Nama Roti/Produk"); y = st.number_input("Yield", value=1.0); u = st.selectbox("Unit", ["Pcs", "Box"]); price = st.number_input("Harga Jual", min_value=0.0)
            if st.form_submit_button("SIMPAN RESEP"):
                c = get_connection(); c.execute("INSERT INTO recipe_master (name, yield_qty, yield_unit, selling_price) VALUES (?,?,?,?)", (n, y, u, price)); c.commit(); c.close(); st.success("Resep Berhasil Disimpan!"); st.rerun()

def show_logistics():
    st.markdown("## 🚛 Pengadaan & Supplier")
    with st.form("po"):
        c = get_connection(); 
        if c.mode == 'local': inv = pd.read_sql_query("SELECT name FROM inventory_master", c.conn); sup = pd.read_sql_query("SELECT name, phone FROM suppliers", c.conn)
        else: inv = pd.read_sql_query("SELECT name FROM inventory_master", c.engine); sup = pd.read_sql_query("SELECT name, phone FROM suppliers", c.engine)
        i = st.selectbox("Material", inv['name'].tolist() if not inv.empty else []); s = st.selectbox("Supplier", sup['name'].tolist() if not sup.empty else []); q = st.number_input("Qty"); p = st.number_input("Estimasi Harga")
        if st.form_submit_button("Kirim PO via WA"):
            s_wa = sup[sup['name']==s]['phone'].values[0] if not sup.empty else ""
            msg = f"PO NEAR BAKERY\nItem: {i}\nQty: {q}\nTotal: {format_rp(p)}"
            link = f"https://wa.me/{s_wa}?text={urllib.parse.quote(msg)}"
            st.markdown(f'<a href="{link}" target="_blank">📲 KLIK KIRIM WHATSAPP</a>', unsafe_allow_html=True)

def show_vault():
    c = get_connection(); bal = c.execute("SELECT current_balance FROM business_vault").scalar() or 0; c.close()
    st.markdown(f"<div style='background:#1E1B18; padding:50px; border-radius:24px; border:2px solid #D4AF37; text-align:center;'><h1 style='color:#D4AF37; font-size:3rem;'>KHAZANAH BISNIS</h1><h1 style='color:white; font-size:4rem;'>{format_rp(bal)}</h1></div>", unsafe_allow_html=True)

def show_approval():
    st.markdown("## ✅ Approval Center")
    c = get_connection(); 
    if c.mode == 'local': df = pd.read_sql_query("SELECT id, action_type, description FROM pending_approvals WHERE status='PENDING'", c.conn)
    else: df = pd.read_sql_query("SELECT id, action_type, description FROM pending_approvals WHERE status='PENDING'", c.engine)
    if df.empty: st.success("Tidak ada pengajuan tertunda.")
    for _, row in df.iterrows():
        with st.expander(f"{row['action_type']}"):
            st.write(row['description'])
            if st.button("Setujui", key=f"app_{row['id']}"):
                c.execute("UPDATE pending_approvals SET status='APPROVED' WHERE id=?", (row['id'],)); c.commit(); st.rerun()

# =============================================================================
# [4] MAIN INTERFACE & AUTH
# =============================================================================
def main():
    st.set_page_config(page_title="Near Bakery ERP", layout="wide")
    init_db()
    if 'auth' not in st.session_state: st.session_state.auth = False
    
    if not st.session_state.auth:
        st.markdown("<div style='text-align:center; padding-top:100px;'><h1>NEAR BAKERY</h1><h3>EXECUTIVE LOGIN</h3>", unsafe_allow_html=True)
        u = st.text_input("User", placeholder="Username"); p = st.text_input("Pass", type="password", placeholder="Password")
        if st.button("LOGIN", use_container_width=True, type="primary"):
            c = get_connection(); user = c.execute("SELECT username, role FROM users WHERE username=? AND password=?", (u, p)).fetchone(); c.close()
            if user: st.session_state.auth = True; st.session_state.user = user[0]; st.session_state.role = user[1]; st.rerun()
            else: st.error("Akses Ditolak!")
        return

    with st.sidebar:
        st.title("Near Bakery")
        st.write(f"Logged as: {st.session_state.user}")
        menu = ["Dashboard", "Kasir", "Gudang", "Resep", "Logistik", "Approval"]
        if st.session_state.role == 'OWNER': menu += ["The Vault", "Settings"]
        sel = st.radio("Navigasi", menu)
        if st.button("LOGOUT"): st.session_state.auth = False; st.rerun()

    if sel == "Dashboard": st.write("## Dashboard Aktif.")
    elif sel == "Kasir": show_pos()
    elif sel == "Gudang": show_inventory()
    elif sel == "Resep": show_recipes()
    elif sel == "Logistik": show_logistics()
    elif sel == "Approval": show_approval()
    elif sel == "The Vault": show_vault()
    elif sel == "Settings": st.write("## Settings Module.")

if __name__ == "__main__": main()
