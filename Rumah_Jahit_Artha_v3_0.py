import os
import sqlite3
import shutil
import uuid
import hashlib
import base64
from pathlib import Path
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from PIL import Image

# ============================================================
# KONFIGURASI APLIKASI — RUMAH JAHIT ARTHA v2.0
# ============================================================

st.set_page_config(
    page_title="Rumah Jahit Artha",
    page_icon="🪡",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_NAME = "Rumah Jahit Artha"
APP_VERSION = "3.0"
DB_PATH = Path("tailormate.db")
UPLOAD_DIR = Path("uploads")
BACKUP_DIR = Path("backup")
MAX_UPLOAD_MB = 5
PDF_DIR = Path("invoices")
PDF_DIR.mkdir(parents=True, exist_ok=True)

PRODUCTION_STAGES = [
    "Diterima", "Pengukuran", "Pemotongan Pola", "Pemotongan Kain",
    "Penjahitan", "Fitting", "Finishing", "Siap Diambil", "Selesai"
]

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

STATUS_LIST = [
    "Diterima",
    "Pengukuran",
    "Pemotongan Pola",
    "Pemotongan Kain",
    "Penjahitan",
    "Fitting",
    "Finishing",
    "Siap Diambil",
    "Selesai",
    "Dibatalkan",
]

JENIS_PAKAIAN = [
    "Kemeja Pria",
    "Kemeja Wanita",
    "Batik",
    "Gaun/Pesta",
    "Bridesmaid",
    "Kebaya",
    "Jas",
    "Blazer",
    "Celana Formal",
    "Rok",
    "Seragam",
    "Vermak",
    "Lainnya",
]

STATUS_COLORS = {
    "Diterima": "🔵",
    "Pengukuran": "📏",
    "Pemotongan Pola": "📐",
    "Pemotongan Kain": "✂️",
    "Penjahitan": "🧵",
    "Fitting": "👗",
    "Finishing": "✨",
    "Siap Diambil": "📦",
    "Selesai": "✅",
    "Dibatalkan": "❌",
}

# ============================================================
# STYLE PREMIUM
# ============================================================

st.markdown(
    """
<style>
    .main .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    [data-testid="stMetric"] {
        border: 1px solid rgba(128,128,128,.18);
        border-radius: 14px;
        padding: 14px 16px;
        background: rgba(128,128,128,.045);
    }
    .artha-card {
        border: 1px solid rgba(128,128,128,.18);
        border-radius: 16px;
        padding: 18px;
        margin-bottom: 12px;
        background: rgba(128,128,128,.035);
    }
    .artha-title {font-size: 1.8rem; font-weight: 800; margin-bottom: 0;}
    .artha-subtitle {opacity: .72; margin-top: 2px;}
    .small-muted {font-size: .85rem; opacity: .68;}
    div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
    .stButton > button {border-radius: 10px;}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# DATABASE
# ============================================================

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def column_exists(conn, table_name, column_name):
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == column_name for row in rows)


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pelanggan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                telepon TEXT NOT NULL,
                lingkar_dada REAL DEFAULT 0,
                lingkar_pinggang REAL DEFAULT 0,
                panjang_lengan REAL DEFAULT 0,
                lebar_bahu REAL DEFAULT 0,
                panjang_baju REAL DEFAULT 0,
                lingkar_pinggul REAL DEFAULT 0,
                panjang_celana REAL DEFAULT 0,
                lingkar_paha REAL DEFAULT 0,
                lingkar_lengan REAL DEFAULT 0,
                catatan TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pesanan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pelanggan_id INTEGER NOT NULL,
                jenis_pakaian TEXT NOT NULL,
                deskripsi_pesanan TEXT DEFAULT '',
                tgl_terima TEXT NOT NULL,
                tgl_deadline TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Diterima',
                total_biaya INTEGER DEFAULT 0,
                dp INTEGER DEFAULT 0,
                foto_desain TEXT DEFAULT '',
                catatan_internal TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pelanggan_id)
                    REFERENCES pelanggan(id)
                    ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pembayaran (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pesanan_id INTEGER NOT NULL,
                jumlah INTEGER NOT NULL,
                metode TEXT DEFAULT 'Tunai',
                tanggal TEXT NOT NULL,
                catatan TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pesanan_id)
                    REFERENCES pesanan(id)
                    ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS produksi_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pesanan_id INTEGER NOT NULL,
                status_lama TEXT,
                status_baru TEXT NOT NULL,
                waktu TEXT NOT NULL,
                catatan TEXT DEFAULT '',
                FOREIGN KEY (pesanan_id)
                    REFERENCES pesanan(id)
                    ON DELETE CASCADE
            )
        """)

        pelanggan_columns = {
            "panjang_baju": "REAL DEFAULT 0",
            "lingkar_pinggul": "REAL DEFAULT 0",
            "panjang_celana": "REAL DEFAULT 0",
            "lingkar_paha": "REAL DEFAULT 0",
            "lingkar_lengan": "REAL DEFAULT 0",
            "created_at": "TEXT DEFAULT ''",
        }
        for column, definition in pelanggan_columns.items():
            if not column_exists(conn, "pelanggan", column):
                conn.execute(
                    f"ALTER TABLE pelanggan ADD COLUMN {column} {definition}"
                )

        pesanan_columns = {
            "deskripsi_pesanan": "TEXT DEFAULT ''",
            "catatan_internal": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT DEFAULT ''",
        }
        for column, definition in pesanan_columns.items():
            if not column_exists(conn, "pesanan", column):
                conn.execute(
                    f"ALTER TABLE pesanan ADD COLUMN {column} {definition}"
                )


        conn.execute("""
            CREATE TABLE IF NOT EXISTS pengeluaran (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tanggal TEXT NOT NULL,
                kategori TEXT NOT NULL,
                deskripsi TEXT DEFAULT '',
                jumlah INTEGER NOT NULL,
                metode TEXT DEFAULT 'Tunai',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS bahan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL UNIQUE,
                satuan TEXT NOT NULL DEFAULT 'pcs',
                stok REAL NOT NULL DEFAULT 0,
                stok_minimum REAL NOT NULL DEFAULT 0,
                harga_satuan INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS mutasi_bahan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bahan_id INTEGER NOT NULL,
                jenis TEXT NOT NULL,
                jumlah REAL NOT NULL,
                keterangan TEXT DEFAULT '',
                tanggal TEXT NOT NULL,
                FOREIGN KEY (bahan_id) REFERENCES bahan(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS karyawan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                peran TEXT NOT NULL,
                telepon TEXT DEFAULT '',
                aktif INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pekerjaan_karyawan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pesanan_id INTEGER NOT NULL,
                karyawan_id INTEGER NOT NULL,
                pekerjaan TEXT NOT NULL,
                status TEXT DEFAULT 'Belum Mulai',
                catatan TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (pesanan_id) REFERENCES pesanan(id) ON DELETE CASCADE,
                FOREIGN KEY (karyawan_id) REFERENCES karyawan(id) ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'Admin',
                aktif INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Buat user owner default hanya jika belum ada.
        if conn.execute("SELECT COUNT(*) FROM app_users").fetchone()[0] == 0:
            default_password = hashlib.sha256("artha123".encode()).hexdigest()
            conn.execute(
                """
                INSERT INTO app_users (username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                ("owner", default_password, "Owner"),
            )

        conn.commit()


init_db()

# ============================================================
# HELPER
# ============================================================

def rupiah(value):
    try:
        value = int(value or 0)
    except Exception:
        value = 0
    return f"Rp {value:,.0f}".replace(",", ".")


def today_string():
    return date.today().isoformat()


def format_date(value):
    if not value:
        return "-"
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d-%m-%Y")
    except Exception:
        return str(value)


def safe_filename(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in [".jpg", ".jpeg", ".png"]:
        raise ValueError("Format file harus JPG, JPEG, atau PNG.")
    if uploaded_file.size > MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"Ukuran gambar maksimal {MAX_UPLOAD_MB} MB.")

    filename = (
        f"desain_{datetime.now().strftime('%Y%m%d_%H%M%S')}_"
        f"{uuid.uuid4().hex[:10]}{extension}"
    )
    path = UPLOAD_DIR / filename
    with open(path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    try:
        with Image.open(path) as img:
            img.verify()
    except Exception:
        if path.exists():
            path.unlink()
        raise ValueError("File bukan gambar yang valid.")

    return filename


def delete_file(filename):
    if not filename:
        return
    path = UPLOAD_DIR / str(filename)
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def backup_database():
    if not DB_PATH.exists():
        return None
    filename = (
        f"tailormate_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )
    destination = BACKUP_DIR / filename
    shutil.copy2(DB_PATH, destination)
    return destination


def get_customers():
    with get_connection() as conn:
        return pd.read_sql_query(
            "SELECT * FROM pelanggan ORDER BY nama COLLATE NOCASE", conn
        )


def get_orders():
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                p.id,
                p.pelanggan_id,
                pl.nama,
                pl.telepon,
                p.jenis_pakaian,
                p.deskripsi_pesanan,
                p.tgl_terima,
                p.tgl_deadline,
                p.status,
                p.total_biaya,
                p.dp,
                COALESCE(
                    (SELECT SUM(x.jumlah) FROM pembayaran x
                     WHERE x.pesanan_id = p.id), 0
                ) AS pembayaran_tambahan,
                p.foto_desain,
                p.catatan_internal,
                p.created_at,
                p.updated_at
            FROM pesanan p
            JOIN pelanggan pl ON p.pelanggan_id = pl.id
            ORDER BY p.id DESC
            """,
            conn,
        )

    if not df.empty:
        df["total_dibayar"] = (
            df["dp"].fillna(0) + df["pembayaran_tambahan"].fillna(0)
        )
        df["sisa_bayar"] = (
            df["total_biaya"].fillna(0) - df["total_dibayar"]
        ).clip(lower=0)
    else:
        df["total_dibayar"] = pd.Series(dtype="int64")
        df["sisa_bayar"] = pd.Series(dtype="int64")
    return df


def get_order(order_id):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT p.*, pl.nama, pl.telepon,
                   pl.lingkar_dada, pl.lingkar_pinggang,
                   pl.panjang_lengan, pl.lebar_bahu,
                   pl.panjang_baju, pl.lingkar_pinggul,
                   pl.panjang_celana, pl.lingkar_paha,
                   pl.lingkar_lengan, pl.catatan AS catatan_pelanggan
            FROM pesanan p
            JOIN pelanggan pl ON p.pelanggan_id = pl.id
            WHERE p.id = ?
            """,
            (order_id,),
        ).fetchone()


def get_payments(order_id):
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, jumlah, metode, tanggal, catatan
            FROM pembayaran
            WHERE pesanan_id = ?
            ORDER BY tanggal DESC, id DESC
            """,
            conn,
            params=(order_id,),
        )


def log_production(order_id, old_status, new_status, note=""):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO produksi_log
            (pesanan_id, status_lama, status_baru, waktu, catatan)
            VALUES (?, ?, ?, ?, ?)
            """,
            (order_id, old_status, new_status, datetime.now().isoformat(), note),
        )
        conn.commit()


def production_progress(status):
    if status in ["Selesai"]:
        return 1.0
    if status == "Dibatalkan":
        return 0.0
    try:
        idx = STATUS_LIST.index(status)
        return idx / (len(STATUS_LIST) - 2)
    except Exception:
        return 0.0


def is_late(row):
    return (
        str(row["status"]) not in ["Selesai", "Dibatalkan"]
        and str(row["tgl_deadline"]) < today_string()
    )


def whatsapp_url(phone, text):
    digits = "".join(ch for ch in str(phone) if ch.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return f"https://wa.me/{digits}?text={text.replace(' ', '%20')}"



# ============================================================
# FITUR v3.0 — HELPER
# ============================================================

def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate(username, password):
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT username, role FROM app_users
            WHERE username=? AND password_hash=? AND aktif=1
            """,
            (username.strip(), hash_password(password)),
        ).fetchone()
    return row


def calculate_profit(orders, expenses):
    omzet = int(orders["total_biaya"].sum()) if not orders.empty else 0
    biaya = int(expenses["jumlah"].sum()) if not expenses.empty else 0
    return omzet - biaya


def invoice_number(order_id):
    return f"AR-{datetime.now().year}-{int(order_id):05d}"


def generate_invoice_html(order):
    invoice = invoice_number(order["id"])
    payments = get_payments(order["id"])
    paid = int(payments["jumlah"].sum()) if not payments.empty else int(order["dp"])
    paid = max(paid, int(order["dp"]))
    remaining = max(0, int(order["total_biaya"]) - paid)

    return f"""
<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8">
<title>{invoice}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 40px; color: #222; }}
.header {{ display:flex; justify-content:space-between; border-bottom:2px solid #222; padding-bottom:15px; }}
h1 {{ margin:0; }}
table {{ width:100%; border-collapse:collapse; margin-top:25px; }}
th,td {{ border:1px solid #ddd; padding:10px; text-align:left; }}
.total {{ font-size:18px; font-weight:bold; }}
.small {{ color:#666; }}
</style>
</head>
<body>
<div class="header">
<div>
<h1>RUMAH JAHIT ARTHA</h1>
<div>Custom Made By Order</div>
<div>Perum. Grand Kampoeng Kito (Paal Merah), Jambi</div>
</div>
<div>
<strong>INVOICE</strong><br>{invoice}<br>
<span class="small">{format_date(order["tgl_terima"])}</span>
</div>
</div>

<h3>Pelanggan</h3>
<p><strong>{order["nama"]}</strong><br>{order["telepon"]}</p>

<table>
<tr><th>Item</th><th>Deadline</th><th>Status</th><th>Total</th></tr>
<tr>
<td>{order["jenis_pakaian"]}<br>{order["deskripsi_pesanan"] or ""}</td>
<td>{format_date(order["tgl_deadline"])}</td>
<td>{order["status"]}</td>
<td>{rupiah(order["total_biaya"])}</td>
</tr>
</table>

<table>
<tr><td>Sudah Dibayar</td><td>{rupiah(paid)}</td></tr>
<tr class="total"><td>Sisa Pembayaran</td><td>{rupiah(remaining)}</td></tr>
</table>

<p class="small">Terima kasih telah mempercayakan kebutuhan busana kepada Rumah Jahit Artha.</p>
</body>
</html>
"""


def add_expense(tanggal, kategori, deskripsi, jumlah, metode):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO pengeluaran
            (tanggal, kategori, deskripsi, jumlah, metode)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(tanggal), kategori, deskripsi.strip(), jumlah, metode),
        )
        conn.commit()


def get_expenses():
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, tanggal, kategori, deskripsi, jumlah, metode
            FROM pengeluaran ORDER BY tanggal DESC, id DESC
            """,
            conn,
        )


def get_materials():
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, nama, satuan, stok, stok_minimum,
                   harga_satuan, updated_at
            FROM bahan ORDER BY nama COLLATE NOCASE
            """,
            conn,
        )


def add_material(nama, satuan, stok, minimum, harga):
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO bahan
            (nama, satuan, stok, stok_minimum, harga_satuan, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (nama.strip(), satuan, stok, minimum, harga, datetime.now().isoformat()),
        )
        conn.commit()


def material_mutation(material_id, jenis, jumlah, keterangan):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT stok FROM bahan WHERE id=?", (material_id,)
        ).fetchone()
        if not row:
            raise ValueError("Bahan tidak ditemukan.")

        stok_baru = float(row["stok"])
        if jenis == "Masuk":
            stok_baru += jumlah
        else:
            stok_baru -= jumlah

        if stok_baru < 0:
            raise ValueError("Stok tidak boleh menjadi negatif.")

        conn.execute(
            "UPDATE bahan SET stok=?, updated_at=? WHERE id=?",
            (stok_baru, datetime.now().isoformat(), material_id),
        )
        conn.execute(
            """
            INSERT INTO mutasi_bahan
            (bahan_id, jenis, jumlah, keterangan, tanggal)
            VALUES (?, ?, ?, ?, ?)
            """,
            (material_id, jenis, jumlah, keterangan.strip(), today_string()),
        )
        conn.commit()


def get_employees():
    with get_connection() as conn:
        return pd.read_sql_query(
            """
            SELECT id, nama, peran, telepon, aktif
            FROM karyawan ORDER BY nama COLLATE NOCASE
            """,
            conn,
        )


# ============================================================
# LOGIN v3.0
# ============================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

if not st.session_state.authenticated:
    st.markdown(
        """
        <div style="max-width:560px;margin:70px auto 0 auto;
        padding:28px;border:1px solid rgba(128,128,128,.2);
        border-radius:20px;background:rgba(128,128,128,.04);">
        <h1>🪡 Rumah Jahit Artha</h1>
        <p>Masuk ke sistem manajemen versi 3.0</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("🔐 Masuk", use_container_width=True)

    if login:
        user = authenticate(username, password)
        if user:
            st.session_state.authenticated = True
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Username atau password salah.")

    st.info("Login awal: **owner** / **artha123**. Segera ganti password setelah masuk.")
    st.stop()

# ============================================================
# HEADER
# ============================================================

st.markdown(
    f"""
<div class="artha-card">
    <div class="artha-title">🪡 {APP_NAME}</div>
    <div class="artha-subtitle">
        Sistem Manajemen Pelanggan • Pesanan • Ukuran • Produksi • Pembayaran • Desain
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.title("🪡 Rumah Jahit Artha")
st.sidebar.caption(
    "Custom Made By Order | Graduation | Engagement | "
    "Bridesmaid | Kemeja | Kebaya | Vermak"
)
st.sidebar.markdown(
    "**📍 Lokasi**  \n"
    "Perum. Grand Kampoeng Kito (Paal Merah), Jambi"
)
st.sidebar.divider()

menu = st.sidebar.radio(
    "MENU UTAMA",
    [
        "📊 Dashboard",
        "🛒 Pesanan",
        "👤 Pelanggan",
        "📏 Data Ukuran",
        "🎨 Galeri Desain",
        "📋 Produksi",
        "💰 Keuangan",
        "📦 Stok Bahan",
        "👷 Karyawan",
        "📈 Laporan",
        "✨ Referensi Model",
        "⚙️ Pengaturan",
    ],
)

st.sidebar.divider()
st.sidebar.caption(f"Database: {DB_PATH.name}")
st.sidebar.caption(f"Versi aplikasi: {APP_VERSION}")
st.sidebar.caption(f"Login: {st.session_state.username} ({st.session_state.role})")
if st.sidebar.button("🚪 Keluar", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

# ============================================================
# DASHBOARD
# ============================================================

if menu == "📊 Dashboard":
    st.subheader("📊 Dashboard Rumah Jahit")

    orders = get_orders()
    customers = get_customers()

    total_orders = len(orders)
    total_customers = len(customers)

    if not orders.empty:
        selesai = int((orders["status"] == "Selesai").sum())
        proses = int(
            (~orders["status"].isin(["Selesai", "Dibatalkan"])).sum()
        )
        omzet = int(orders["total_biaya"].sum())
        total_dibayar = int(orders["total_dibayar"].sum())
        sisa = int(orders["sisa_bayar"].sum())
        terlambat = int(orders.apply(is_late, axis=1).sum())
    else:
        selesai = proses = omzet = total_dibayar = sisa = terlambat = 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👤 Pelanggan", total_customers)
    c2.metric("🛒 Total Pesanan", total_orders)
    c3.metric("🔧 Dalam Produksi", proses)
    c4.metric("⚠️ Terlambat", terlambat)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("💰 Nilai Pesanan", rupiah(omzet))
    c6.metric("💵 Sudah Dibayar", rupiah(total_dibayar))
    c7.metric("🧾 Piutang", rupiah(sisa))
    c8.metric("✅ Selesai", selesai)

    st.divider()

    if not orders.empty:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown("### 📌 Distribusi Status")
            status_count = (
                orders["status"].value_counts()
                .reindex(STATUS_LIST, fill_value=0)
            )
            st.bar_chart(status_count)

        with col2:
            st.markdown("### 💰 Ringkasan Keuangan")
            finance = pd.DataFrame(
                {
                    "Kategori": ["Nilai Pesanan", "Sudah Dibayar", "Piutang"],
                    "Nominal": [omzet, total_dibayar, sisa],
                }
            ).set_index("Kategori")
            st.bar_chart(finance)

        st.markdown("### 🕒 Pesanan Terbaru")
        display = orders.head(10).copy()
        display["tgl_deadline"] = display["tgl_deadline"].apply(format_date)
        display["total_biaya"] = display["total_biaya"].apply(rupiah)
        display["total_dibayar"] = display["total_dibayar"].apply(rupiah)
        display["sisa_bayar"] = display["sisa_bayar"].apply(rupiah)
        display = display[
            [
                "id", "nama", "jenis_pakaian", "tgl_deadline",
                "status", "total_biaya", "total_dibayar", "sisa_bayar"
            ]
        ]
        display.columns = [
            "ID", "Pelanggan", "Jenis", "Deadline",
            "Status", "Total", "Dibayar", "Sisa"
        ]
        st.dataframe(display, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada pesanan. Silakan masukkan pesanan pertama.")

# ============================================================
# PESANAN
# ============================================================

elif menu == "🛒 Pesanan":
    st.subheader("🛒 Manajemen Pesanan")

    tab1, tab2, tab3 = st.tabs(
        ["➕ Pesanan Baru", "🔎 Daftar Pesanan", "✏️ Detail / Edit"]
    )
    customers = get_customers()

    with tab1:
        if customers.empty:
            st.warning("Belum ada pelanggan. Tambahkan pelanggan terlebih dahulu.")
        else:
            customer_map = {
                f"{row['nama']} — {row['telepon']}": int(row["id"])
                for _, row in customers.iterrows()
            }
            selected_customer = st.selectbox(
                "Pelanggan", list(customer_map.keys())
            )

            with st.form("new_order"):
                c1, c2 = st.columns(2)
                with c1:
                    jenis = st.selectbox("Jenis Pakaian", JENIS_PAKAIAN)
                    deskripsi = st.text_area(
                        "Deskripsi Pesanan",
                        placeholder="Model, warna, kain, payet, bordir, dll."
                    )
                    tanggal_terima = st.date_input("Tanggal Terima", value=date.today())
                    deadline = st.date_input(
                        "Tanggal Deadline",
                        value=date.today() + timedelta(days=7)
                    )

                with c2:
                    ongkos = st.number_input(
                        "Ongkos Jahit", min_value=0, step=10000
                    )
                    bahan = st.number_input(
                        "Bahan / Aksesoris", min_value=0, step=5000
                    )
                    dp = st.number_input("DP", min_value=0, step=10000)
                    foto = st.file_uploader(
                        "Foto Desain", type=["jpg", "jpeg", "png"]
                    )
                    catatan_internal = st.text_area(
                        "Catatan Internal",
                        placeholder="Catatan untuk penjahit/tim produksi."
                    )

                total = ongkos + bahan
                st.info(
                    f"**Total:** {rupiah(total)}  •  "
                    f"**Sisa:** {rupiah(total - dp)}"
                )
                submit = st.form_submit_button(
                    "💾 Simpan Pesanan", use_container_width=True
                )

                if submit:
                    if deadline < tanggal_terima:
                        st.error("Deadline tidak boleh sebelum tanggal terima.")
                    elif dp > total:
                        st.error("DP tidak boleh melebihi total biaya.")
                    else:
                        filename = ""
                        try:
                            if foto:
                                filename = safe_filename(foto)
                            now = datetime.now().isoformat()
                            with get_connection() as conn:
                                cur = conn.execute(
                                    """
                                    INSERT INTO pesanan (
                                        pelanggan_id, jenis_pakaian,
                                        deskripsi_pesanan, tgl_terima,
                                        tgl_deadline, status, total_biaya,
                                        dp, foto_desain, catatan_internal,
                                        created_at, updated_at
                                    )
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                    """,
                                    (
                                        customer_map[selected_customer],
                                        jenis,
                                        deskripsi.strip(),
                                        str(tanggal_terima),
                                        str(deadline),
                                        "Diterima",
                                        total,
                                        dp,
                                        filename,
                                        catatan_internal.strip(),
                                        now,
                                        now,
                                    ),
                                )
                                order_id = cur.lastrowid
                                if dp > 0:
                                    conn.execute(
                                        """
                                        INSERT INTO pembayaran
                                        (pesanan_id, jumlah, metode, tanggal, catatan)
                                        VALUES (?, ?, ?, ?, ?)
                                        """,
                                        (
                                            order_id, dp, "DP",
                                            str(tanggal_terima), "DP saat pesanan dibuat"
                                        ),
                                    )
                                conn.commit()

                            log_production(order_id, "", "Diterima", "Pesanan baru")
                            st.success(f"Pesanan #{order_id} berhasil dibuat.")
                        except Exception as e:
                            if filename:
                                delete_file(filename)
                            st.error(f"Gagal menyimpan pesanan: {e}")

    with tab2:
        orders = get_orders()
        if orders.empty:
            st.info("Belum ada pesanan.")
        else:
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                search = st.text_input(
                    "🔎 Cari",
                    placeholder="Nama, jenis pakaian, nomor pesanan..."
                )
            with c2:
                status_filter = st.selectbox("Status", ["Semua"] + STATUS_LIST)
            with c3:
                late_only = st.checkbox("⚠️ Hanya terlambat")

            filtered = orders.copy()
            if search.strip():
                keyword = search.lower()
                filtered = filtered[
                    filtered.apply(
                        lambda row:
                        keyword in str(row["nama"]).lower()
                        or keyword in str(row["jenis_pakaian"]).lower()
                        or keyword in str(row["id"]).lower(),
                        axis=1,
                    )
                ]
            if status_filter != "Semua":
                filtered = filtered[filtered["status"] == status_filter]
            if late_only:
                filtered = filtered[filtered.apply(is_late, axis=1)]

            st.caption(f"{len(filtered)} pesanan ditemukan.")

            if filtered.empty:
                st.warning("Tidak ada pesanan yang sesuai.")
            else:
                display = filtered.copy()
                display["tgl_deadline"] = display["tgl_deadline"].apply(format_date)
                display["total_biaya"] = display["total_biaya"].apply(rupiah)
                display["total_dibayar"] = display["total_dibayar"].apply(rupiah)
                display["sisa_bayar"] = display["sisa_bayar"].apply(rupiah)
                display = display[
                    [
                        "id", "nama", "telepon", "jenis_pakaian",
                        "tgl_deadline", "status",
                        "total_biaya", "total_dibayar", "sisa_bayar"
                    ]
                ]
                display.columns = [
                    "ID", "Pelanggan", "Telepon", "Jenis",
                    "Deadline", "Status", "Total", "Dibayar", "Sisa"
                ]
                st.dataframe(
                    display,
                    use_container_width=True,
                    hide_index=True,
                )

                csv = filtered.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "⬇️ Export CSV",
                    csv,
                    "pesanan_rumah_jahit_artha.csv",
                    "text/csv",
                )

    with tab3:
        orders = get_orders()
        if orders.empty:
            st.info("Belum ada pesanan.")
        else:
            order_map = {
                f"#{row['id']} — {row['nama']} — {row['jenis_pakaian']}":
                int(row["id"])
                for _, row in orders.iterrows()
            }
            selected_order = st.selectbox(
                "Pilih Pesanan", list(order_map.keys())
            )
            order_id = order_map[selected_order]
            order = get_order(order_id)

            if order:
                progress = production_progress(order["status"])
                st.markdown(
                    f"### {STATUS_COLORS.get(order['status'], '🔧')} "
                    f"Pesanan #{order['id']}"
                )
                st.progress(progress)
                st.caption(
                    f"Progress produksi: {round(progress * 100)}% • "
                    f"Status: {order['status']}"
                )

                a, b, c = st.columns(3)
                a.metric("Total", rupiah(order["total_biaya"]))
                payments = get_payments(order_id)
                paid = int(payments["jumlah"].sum()) if not payments.empty else int(order["dp"])
                c_paid = max(paid, int(order["dp"]))
                b.metric("Dibayar", rupiah(c_paid))
                c.metric(
                    "Sisa",
                    rupiah(max(0, int(order["total_biaya"]) - c_paid))
                )

                st.divider()

                edit_tab, payment_tab, history_tab = st.tabs(
                    ["✏️ Edit Pesanan", "💵 Pembayaran", "🕒 Riwayat Produksi"]
                )

                with edit_tab:
                    with st.form(f"edit_order_{order_id}"):
                        new_status = st.selectbox(
                            "Status",
                            STATUS_LIST,
                            index=STATUS_LIST.index(order["status"])
                            if order["status"] in STATUS_LIST else 0,
                        )
                        new_deadline = st.date_input(
                            "Deadline",
                            value=datetime.strptime(
                                order["tgl_deadline"], "%Y-%m-%d"
                            ).date(),
                        )
                        new_total = st.number_input(
                            "Total Biaya",
                            min_value=0,
                            value=int(order["total_biaya"]),
                            step=10000,
                        )
                        new_description = st.text_area(
                            "Deskripsi",
                            value=order["deskripsi_pesanan"] or "",
                        )
                        new_internal = st.text_area(
                            "Catatan Internal",
                            value=order["catatan_internal"] or "",
                        )
                        note = st.text_input(
                            "Catatan perubahan status (opsional)"
                        )

                        update = st.form_submit_button(
                            "💾 Simpan Perubahan",
                            use_container_width=True,
                        )

                    if update:
                        if new_deadline < datetime.strptime(
                            order["tgl_terima"], "%Y-%m-%d"
                        ).date():
                            st.error("Deadline tidak boleh sebelum tanggal terima.")
                        else:
                            old_status = order["status"]
                            with get_connection() as conn:
                                conn.execute(
                                    """
                                    UPDATE pesanan
                                    SET status=?, tgl_deadline=?,
                                        total_biaya=?,
                                        deskripsi_pesanan=?,
                                        catatan_internal=?,
                                        updated_at=?
                                    WHERE id=?
                                    """,
                                    (
                                        new_status,
                                        str(new_deadline),
                                        new_total,
                                        new_description.strip(),
                                        new_internal.strip(),
                                        datetime.now().isoformat(),
                                        order_id,
                                    ),
                                )
                                conn.commit()
                            if old_status != new_status:
                                log_production(
                                    order_id, old_status, new_status, note.strip()
                                )
                            st.success("Pesanan berhasil diperbarui.")
                            st.rerun()

                with payment_tab:
                    payments = get_payments(order_id)
                    if not payments.empty:
                        payment_view = payments.copy()
                        payment_view["jumlah"] = payment_view["jumlah"].apply(rupiah)
                        payment_view["tanggal"] = payment_view["tanggal"].apply(format_date)
                        payment_view.columns = [
                            "ID", "Jumlah", "Metode", "Tanggal", "Catatan"
                        ]
                        st.dataframe(
                            payment_view,
                            use_container_width=True,
                            hide_index=True,
                        )

                    with st.form(f"payment_{order_id}"):
                        amount = st.number_input(
                            "Jumlah Pembayaran",
                            min_value=0,
                            step=10000,
                        )
                        method = st.selectbox(
                            "Metode",
                            ["Tunai", "Transfer", "QRIS", "Debit", "Lainnya"],
                        )
                        payment_date = st.date_input(
                            "Tanggal", value=date.today()
                        )
                        payment_note = st.text_input("Catatan")
                        add_payment = st.form_submit_button(
                            "➕ Catat Pembayaran",
                            use_container_width=True,
                        )

                    if add_payment:
                        current = get_orders()
                        current_row = current[current["id"] == order_id]
                        if current_row.empty:
                            st.error("Pesanan tidak ditemukan.")
                        else:
                            remaining = int(current_row.iloc[0]["sisa_bayar"])
                            if amount <= 0:
                                st.error("Jumlah pembayaran harus lebih dari 0.")
                            elif amount > remaining:
                                st.error(
                                    f"Pembayaran melebihi sisa tagihan "
                                    f"({rupiah(remaining)})."
                                )
                            else:
                                with get_connection() as conn:
                                    conn.execute(
                                        """
                                        INSERT INTO pembayaran
                                        (pesanan_id, jumlah, metode, tanggal, catatan)
                                        VALUES (?, ?, ?, ?, ?)
                                        """,
                                        (
                                            order_id,
                                            amount,
                                            method,
                                            str(payment_date),
                                            payment_note.strip(),
                                        ),
                                    )
                                    conn.commit()
                                st.success("Pembayaran berhasil dicatat.")
                                st.rerun()

                    if c_paid >= int(order["total_biaya"]):
                        st.success("✅ Pesanan ini sudah lunas.")

                with history_tab:
                    with get_connection() as conn:
                        history = pd.read_sql_query(
                            """
                            SELECT status_lama, status_baru, waktu, catatan
                            FROM produksi_log
                            WHERE pesanan_id=?
                            ORDER BY waktu DESC, id DESC
                            """,
                            conn,
                            params=(order_id,),
                        )
                    if history.empty:
                        st.info("Belum ada riwayat perubahan status.")
                    else:
                        history["waktu"] = pd.to_datetime(
                            history["waktu"], errors="coerce"
                        ).dt.strftime("%d-%m-%Y %H:%M")
                        history.columns = [
                            "Status Lama", "Status Baru", "Waktu", "Catatan"
                        ]
                        st.dataframe(
                            history,
                            use_container_width=True,
                            hide_index=True,
                        )

                st.divider()
                invoice_html = generate_invoice_html(order)
                st.download_button(
                    "🧾 Download Invoice HTML",
                    data=invoice_html.encode("utf-8"),
                    file_name=f"{invoice_number(order['id'])}.html",
                    mime="text/html",
                    use_container_width=True,
                )

                wa_text = (
                    f"Halo {order['nama']}, pesanan #{order['id']} "
                    f"({order['jenis_pakaian']}) saat ini berstatus "
                    f"{order['status']}. Deadline {format_date(order['tgl_deadline'])}."
                )
                st.link_button(
                    "💬 Hubungi Pelanggan via WhatsApp",
                    whatsapp_url(order["telepon"], wa_text),
                )

                confirm = st.checkbox(
                    "Saya yakin ingin menghapus pesanan ini.",
                    key=f"confirm_delete_{order_id}",
                )
                if st.button(
                    "🗑️ Hapus Pesanan",
                    type="secondary",
                    key=f"delete_{order_id}",
                ):
                    if not confirm:
                        st.warning("Centang konfirmasi terlebih dahulu.")
                    else:
                        filename = order["foto_desain"]
                        with get_connection() as conn:
                            conn.execute(
                                "DELETE FROM pesanan WHERE id=?", (order_id,)
                            )
                            conn.commit()
                        delete_file(filename)
                        st.success("Pesanan berhasil dihapus.")
                        st.rerun()

# ============================================================
# PELANGGAN
# ============================================================

elif menu == "👤 Pelanggan":
    st.subheader("👤 Data Pelanggan")
    customers = get_customers()

    tab1, tab2, tab3 = st.tabs(
        ["➕ Tambah Pelanggan", "📋 Daftar Pelanggan", "✏️ Edit Pelanggan"]
    )

    with tab1:
        with st.form("customer_form"):
            c1, c2 = st.columns(2)
            with c1:
                nama = st.text_input("Nama Lengkap *")
                telepon = st.text_input("Nomor Telepon / WhatsApp *")
                lingkar_dada = st.number_input("Lingkar Dada", 0.0, step=0.5)
                lingkar_pinggang = st.number_input("Lingkar Pinggang", 0.0, step=0.5)
                lingkar_pinggul = st.number_input("Lingkar Pinggul", 0.0, step=0.5)
                lingkar_paha = st.number_input("Lingkar Paha", 0.0, step=0.5)
            with c2:
                lebar_bahu = st.number_input("Lebar Bahu", 0.0, step=0.5)
                panjang_lengan = st.number_input("Panjang Lengan", 0.0, step=0.5)
                panjang_baju = st.number_input("Panjang Baju", 0.0, step=0.5)
                panjang_celana = st.number_input("Panjang Celana", 0.0, step=0.5)
                lingkar_lengan = st.number_input("Lingkar Lengan", 0.0, step=0.5)
                catatan = st.text_area("Catatan Pelanggan")

            submit = st.form_submit_button(
                "💾 Simpan Pelanggan",
                use_container_width=True,
            )

        if submit:
            nama = nama.strip()
            telepon = telepon.strip()
            if not nama or not telepon:
                st.error("Nama dan nomor telepon wajib diisi.")
            else:
                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO pelanggan (
                            nama, telepon, lingkar_dada, lingkar_pinggang,
                            panjang_lengan, lebar_bahu, panjang_baju,
                            lingkar_pinggul, panjang_celana, lingkar_paha,
                            lingkar_lengan, catatan, created_at
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            nama, telepon, lingkar_dada, lingkar_pinggang,
                            panjang_lengan, lebar_bahu, panjang_baju,
                            lingkar_pinggul, panjang_celana, lingkar_paha,
                            lingkar_lengan, catatan.strip(),
                            datetime.now().isoformat(),
                        ),
                    )
                    conn.commit()
                st.success(f"Pelanggan {nama} berhasil ditambahkan.")
                st.rerun()

    with tab2:
        if customers.empty:
            st.info("Belum ada pelanggan.")
        else:
            search_customer = st.text_input(
                "🔎 Cari pelanggan",
                placeholder="Nama atau nomor telepon..."
            )
            display = customers.copy()
            if search_customer.strip():
                keyword = search_customer.lower()
                display = display[
                    display.apply(
                        lambda row:
                        keyword in str(row["nama"]).lower()
                        or keyword in str(row["telepon"]).lower(),
                        axis=1,
                    )
                ]

            view = display[
                [
                    "id", "nama", "telepon",
                    "lingkar_dada", "lingkar_pinggang", "lingkar_pinggul",
                    "lebar_bahu", "panjang_lengan", "panjang_baju",
                    "panjang_celana"
                ]
            ].copy()
            view.columns = [
                "ID", "Nama", "Telepon", "Dada", "Pinggang", "Pinggul",
                "Bahu", "Lengan", "Panjang Baju", "Panjang Celana"
            ]
            st.dataframe(view, use_container_width=True, hide_index=True)

            csv = display.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Export Data Pelanggan",
                csv,
                "pelanggan_rumah_jahit_artha.csv",
                "text/csv",
            )

    with tab3:
        if customers.empty:
            st.info("Belum ada pelanggan.")
        else:
            customer_map = {
                f"#{row['id']} — {row['nama']} — {row['telepon']}":
                int(row["id"])
                for _, row in customers.iterrows()
            }
            selected = st.selectbox("Pilih Pelanggan", list(customer_map.keys()))
            customer_id = customer_map[selected]
            row = customers[customers["id"] == customer_id].iloc[0]

            with st.form(f"edit_customer_{customer_id}"):
                c1, c2 = st.columns(2)
                with c1:
                    n_nama = st.text_input("Nama", value=row["nama"])
                    n_telepon = st.text_input("Telepon", value=row["telepon"])
                    n_dada = st.number_input("Lingkar Dada", 0.0, value=float(row["lingkar_dada"]), step=0.5)
                    n_pinggang = st.number_input("Lingkar Pinggang", 0.0, value=float(row["lingkar_pinggang"]), step=0.5)
                    n_pinggul = st.number_input("Lingkar Pinggul", 0.0, value=float(row["lingkar_pinggul"]), step=0.5)
                    n_paha = st.number_input("Lingkar Paha", 0.0, value=float(row["lingkar_paha"]), step=0.5)
                with c2:
                    n_bahu = st.number_input("Lebar Bahu", 0.0, value=float(row["lebar_bahu"]), step=0.5)
                    n_lengan = st.number_input("Panjang Lengan", 0.0, value=float(row["panjang_lengan"]), step=0.5)
                    n_baju = st.number_input("Panjang Baju", 0.0, value=float(row["panjang_baju"]), step=0.5)
                    n_celana = st.number_input("Panjang Celana", 0.0, value=float(row["panjang_celana"]), step=0.5)
                    n_lingkar_lengan = st.number_input("Lingkar Lengan", 0.0, value=float(row["lingkar_lengan"]), step=0.5)
                    n_catatan = st.text_area("Catatan", value=row["catatan"] or "")

                save = st.form_submit_button(
                    "💾 Simpan Data Pelanggan",
                    use_container_width=True,
                )

            if save:
                if not n_nama.strip() or not n_telepon.strip():
                    st.error("Nama dan telepon wajib diisi.")
                else:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE pelanggan
                            SET nama=?, telepon=?, lingkar_dada=?,
                                lingkar_pinggang=?, panjang_lengan=?,
                                lebar_bahu=?, panjang_baju=?,
                                lingkar_pinggul=?, panjang_celana=?,
                                lingkar_paha=?, lingkar_lengan=?, catatan=?
                            WHERE id=?
                            """,
                            (
                                n_nama.strip(), n_telepon.strip(), n_dada,
                                n_pinggang, n_lengan, n_bahu, n_baju,
                                n_pinggul, n_celana, n_paha,
                                n_lingkar_lengan, n_catatan.strip(), customer_id
                            ),
                        )
                        conn.commit()
                    st.success("Data pelanggan berhasil diperbarui.")
                    st.rerun()

# ============================================================
# DATA UKURAN
# ============================================================

elif menu == "📏 Data Ukuran":
    st.subheader("📏 Data Ukuran Pelanggan")
    customers = get_customers()

    if customers.empty:
        st.info("Belum ada data pelanggan.")
    else:
        customer_map = {
            f"{row['nama']} — {row['telepon']}": int(row["id"])
            for _, row in customers.iterrows()
        }
        selected = st.selectbox("Pilih Pelanggan", list(customer_map.keys()))
        customer = customers[
            customers["id"] == customer_map[selected]
        ].iloc[0]

        st.markdown(f"### 👤 {customer['nama']}")
        measurements = [
            ("Lingkar Dada", customer["lingkar_dada"]),
            ("Lingkar Pinggang", customer["lingkar_pinggang"]),
            ("Lingkar Pinggul", customer["lingkar_pinggul"]),
            ("Lebar Bahu", customer["lebar_bahu"]),
            ("Panjang Lengan", customer["panjang_lengan"]),
            ("Panjang Baju", customer["panjang_baju"]),
            ("Panjang Celana", customer["panjang_celana"]),
            ("Lingkar Paha", customer["lingkar_paha"]),
            ("Lingkar Lengan", customer["lingkar_lengan"]),
        ]
        cols = st.columns(3)
        for i, (label, value) in enumerate(measurements):
            cols[i % 3].metric(label, f"{value} cm")

        st.divider()
        st.subheader("📝 Catatan")
        st.write(customer["catatan"] or "Tidak ada catatan.")

# ============================================================
# GALERI
# ============================================================

elif menu == "🎨 Galeri Desain":
    st.subheader("🎨 Galeri Desain Pesanan")
    orders = get_orders()
    orders = orders[
        orders["foto_desain"].notna() & (orders["foto_desain"] != "")
    ]

    if orders.empty:
        st.info("Belum ada desain yang diupload.")
    else:
        cols = st.columns(3)
        for index, row in orders.iterrows():
            with cols[index % 3]:
                with st.container(border=True):
                    path = UPLOAD_DIR / str(row["foto_desain"])
                    if path.exists():
                        try:
                            image = Image.open(path)
                            st.image(image, use_container_width=True)
                        except Exception:
                            st.error("Gambar rusak.")
                    else:
                        st.warning("File tidak ditemukan.")

                    st.markdown(
                        f"### #{row['id']} — {row['jenis_pakaian']}"
                    )
                    st.write(f"👤 {row['nama']}")
                    st.write(
                        f"📅 Deadline: {format_date(row['tgl_deadline'])}"
                    )
                    st.write(
                        f"{STATUS_COLORS.get(row['status'], '🔧')} "
                        f"**{row['status']}**"
                    )
                    if row["deskripsi_pesanan"]:
                        with st.expander("Lihat Deskripsi"):
                            st.write(row["deskripsi_pesanan"])

# ============================================================
# PRODUKSI
# ============================================================

elif menu == "📋 Produksi":
    st.subheader("📋 Monitoring Produksi")
    orders = get_orders()

    if orders.empty:
        st.info("Belum ada pesanan.")
    else:
        active = orders[
            ~orders["status"].isin(["Selesai", "Dibatalkan"])
        ].copy()

        if active.empty:
            st.success("🎉 Tidak ada pekerjaan aktif.")
        else:
            # Ringkasan kapasitas
            counts = (
                active["status"].value_counts()
                .reindex(STATUS_LIST, fill_value=0)
            )
            st.bar_chart(counts)

            for status in STATUS_LIST:
                status_orders = active[active["status"] == status]
                if status_orders.empty:
                    continue

                st.markdown(
                    f"### {STATUS_COLORS.get(status, '🔧')} {status}"
                )
                for _, row in status_orders.iterrows():
                    late = is_late(row)
                    progress = production_progress(status)
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 2, 1])
                        with c1:
                            st.write(
                                f"**#{row['id']} — {row['nama']}**  \n"
                                f"{row['jenis_pakaian']}"
                            )
                        with c2:
                            st.write(
                                f"Deadline: **{format_date(row['tgl_deadline'])}**"
                            )
                            st.progress(progress)
                        with c3:
                            if late:
                                st.error("TERLAMBAT")
                            else:
                                st.success("ON TRACK")

# ============================================================
# KEUANGAN
# ============================================================

elif menu == "💰 Keuangan":
    st.subheader("💰 Keuangan & Laba Rugi")
    orders = get_orders()
    expenses = get_expenses()

    tab_finance, tab_expense = st.tabs(["📊 Ringkasan", "➕ Pengeluaran"])

    with tab_finance:
        total = int(orders["total_biaya"].sum()) if not orders.empty else 0
        paid = int(orders["total_dibayar"].sum()) if not orders.empty else 0
        sisa = int(orders["sisa_bayar"].sum()) if not orders.empty else 0
        expense_total = int(expenses["jumlah"].sum()) if not expenses.empty else 0
        profit = total - expense_total

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Omzet", rupiah(total))
        c2.metric("Dibayar", rupiah(paid))
        c3.metric("Piutang", rupiah(sisa))
        c4.metric("Laba Kotor", rupiah(profit))

        st.divider()
        st.subheader("🧾 Detail Piutang")
        if orders.empty:
            st.info("Belum ada pesanan.")
        else:
            belum_lunas = orders[orders["sisa_bayar"] > 0]
            if belum_lunas.empty:
                st.success("Semua pesanan sudah lunas.")
            else:
                for _, row in belum_lunas.iterrows():
                    st.warning(
                        f"#{row['id']} — {row['nama']} — "
                        f"Sisa: **{rupiah(row['sisa_bayar'])}**"
                    )

        st.subheader("📉 Pengeluaran")
        if expenses.empty:
            st.info("Belum ada pengeluaran.")
        else:
            view = expenses.copy()
            view["jumlah"] = view["jumlah"].apply(rupiah)
            view["tanggal"] = view["tanggal"].apply(format_date)
            view.columns = [
                "ID", "Tanggal", "Kategori", "Deskripsi", "Jumlah", "Metode"
            ]
            st.dataframe(view, use_container_width=True, hide_index=True)

        chart = pd.DataFrame(
            {
                "Kategori": ["Omzet", "Pengeluaran", "Laba Kotor", "Piutang"],
                "Nominal": [total, expense_total, profit, sisa],
            }
        ).set_index("Kategori")
        st.bar_chart(chart)

    with tab_expense:
        st.markdown("### ➕ Catat Pengeluaran Usaha")
        with st.form("expense_form"):
            expense_date = st.date_input("Tanggal", value=date.today())
            expense_category = st.selectbox(
                "Kategori",
                [
                    "Bahan", "Gaji", "Listrik", "Air", "Sewa",
                    "Transportasi", "Operasional", "Marketing", "Lainnya"
                ],
            )
            expense_desc = st.text_input("Deskripsi")
            expense_amount = st.number_input(
                "Jumlah", min_value=0, step=1000
            )
            expense_method = st.selectbox(
                "Metode", ["Tunai", "Transfer", "Debit", "Lainnya"]
            )
            save_expense = st.form_submit_button(
                "💾 Simpan Pengeluaran", use_container_width=True
            )

        if save_expense:
            if expense_amount <= 0:
                st.error("Jumlah pengeluaran harus lebih dari 0.")
            else:
                add_expense(
                    expense_date,
                    expense_category,
                    expense_desc,
                    expense_amount,
                    expense_method,
                )
                st.success("Pengeluaran berhasil dicatat.")
                st.rerun()


# ============================================================
# STOK BAHAN v3.0
# ============================================================

elif menu == "📦 Stok Bahan":
    st.subheader("📦 Manajemen Stok Bahan")
    materials = get_materials()

    tab1, tab2, tab3 = st.tabs(
        ["📋 Stok", "➕ Tambah Bahan", "🔄 Mutasi Stok"]
    )

    with tab1:
        if materials.empty:
            st.info("Belum ada bahan.")
        else:
            view = materials.copy()
            view["Status"] = view.apply(
                lambda r: "⚠️ Kritis" if r["stok"] <= r["stok_minimum"] else "✅ Aman",
                axis=1,
            )
            view.columns = [
                "ID", "Nama", "Satuan", "Stok",
                "Minimum", "Harga/Satuan", "Update", "Status"
            ]
            st.dataframe(view, use_container_width=True, hide_index=True)

            critical = materials[
                materials["stok"] <= materials["stok_minimum"]
            ]
            if not critical.empty:
                st.warning(
                    f"⚠️ {len(critical)} bahan berada pada atau di bawah stok minimum."
                )

    with tab2:
        with st.form("add_material"):
            nama_bahan = st.text_input("Nama Bahan *")
            satuan = st.selectbox(
                "Satuan", ["meter", "pcs", "lusin", "kg", "roll", "yard"]
            )
            stok_awal = st.number_input("Stok Awal", min_value=0.0, step=0.5)
            minimum = st.number_input("Stok Minimum", min_value=0.0, step=0.5)
            harga = st.number_input(
                "Harga Satuan", min_value=0, step=1000
            )
            save_material = st.form_submit_button(
                "💾 Simpan Bahan", use_container_width=True
            )

        if save_material:
            if not nama_bahan.strip():
                st.error("Nama bahan wajib diisi.")
            else:
                try:
                    add_material(
                        nama_bahan, satuan, stok_awal, minimum, harga
                    )
                    st.success("Bahan berhasil ditambahkan.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Bahan dengan nama tersebut sudah ada.")

    with tab3:
        if materials.empty:
            st.info("Tambahkan bahan terlebih dahulu.")
        else:
            material_map = {
                f"#{row['id']} — {row['nama']} ({row['stok']} {row['satuan']})":
                int(row["id"])
                for _, row in materials.iterrows()
            }
            selected_material = st.selectbox(
                "Pilih Bahan", list(material_map.keys())
            )
            with st.form("material_mutation"):
                mutation_type = st.radio(
                    "Jenis Mutasi", ["Masuk", "Keluar"], horizontal=True
                )
                quantity = st.number_input(
                    "Jumlah", min_value=0.01, step=0.5
                )
                mutation_note = st.text_input("Keterangan")
                submit_mutation = st.form_submit_button(
                    "🔄 Simpan Mutasi", use_container_width=True
                )

            if submit_mutation:
                try:
                    material_mutation(
                        material_map[selected_material],
                        mutation_type,
                        quantity,
                        mutation_note,
                    )
                    st.success("Mutasi stok berhasil disimpan.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))


# ============================================================
# KARYAWAN v3.0
# ============================================================

elif menu == "👷 Karyawan":
    st.subheader("👷 Manajemen Karyawan")
    employees = get_employees()

    tab1, tab2 = st.tabs(["📋 Daftar Karyawan", "➕ Tambah Karyawan"])

    with tab1:
        if employees.empty:
            st.info("Belum ada karyawan.")
        else:
            view = employees.copy()
            view["Aktif"] = view["aktif"].map({1: "Ya", 0: "Tidak"})
            view.columns = ["ID", "Nama", "Peran", "Telepon", "Aktif"]
            st.dataframe(view, use_container_width=True, hide_index=True)

    with tab2:
        with st.form("new_employee"):
            employee_name = st.text_input("Nama Karyawan *")
            employee_role = st.selectbox(
                "Peran",
                ["Admin", "Penjahit", "Potong", "Finishing", "Kasir", "Owner"]
            )
            employee_phone = st.text_input("Telepon")
            save_employee = st.form_submit_button(
                "💾 Simpan Karyawan", use_container_width=True
            )

        if save_employee:
            if not employee_name.strip():
                st.error("Nama karyawan wajib diisi.")
            else:
                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO karyawan (nama, peran, telepon)
                        VALUES (?, ?, ?)
                        """,
                        (
                            employee_name.strip(),
                            employee_role,
                            employee_phone.strip(),
                        ),
                    )
                    conn.commit()
                st.success("Karyawan berhasil ditambahkan.")
                st.rerun()


# ============================================================
# KEUANGAN v3.0 — TAMBAHAN PENGELUARAN & LABA
# ============================================================

# ============================================================
# REFERENSI MODEL
# ============================================================

elif menu == "✨ Referensi Model":
    st.subheader("✨ Referensi Model Busana")
    st.info(
        "Gunakan bagian ini sebagai referensi konsultasi dengan pelanggan."
    )

    kategori = st.selectbox(
        "Kategori",
        [
            "Gaun Bridesmaid / Pesta",
            "Kebaya Modern / Wisuda",
            "Kemeja Batik Pria",
            "Jas / Blazer",
            "Seragam",
            "Vermak",
        ],
    )
    warna = st.selectbox(
        "Warna",
        [
            "Sage Green", "Dusty Pink", "Navy", "Maroon",
            "Hitam", "Cream", "Custom",
        ],
    )
    model = st.selectbox(
        "Model",
        [
            "A-Line", "Slim Fit", "Mermaid",
            "Puff Sleeve", "Peplum", "Oversized",
        ],
    )
    detail = st.text_area(
        "Detail yang diinginkan pelanggan",
        placeholder="Contoh: V-neck, payet mutiara, lengan panjang, rok A-line..."
    )

    st.divider()
    st.markdown(
        f"""
### 📋 Ringkasan Konsultasi
**Kategori:** {kategori}

**Warna:** {warna}

**Model:** {model}

**Detail:** {detail if detail else "-"}
"""
    )
    st.success("Referensi siap digunakan untuk konsultasi dan pencatatan pesanan.")

# ============================================================
# PENGATURAN
# ============================================================

elif menu == "⚙️ Pengaturan":
    st.subheader("⚙️ Pengaturan Aplikasi")

    st.markdown("### 👤 Manajemen Akun")

    with st.expander("➕ Tambah Akun Pengguna"):
        with st.form("new_app_user"):
            new_username = st.text_input("Username")
            new_password = st.text_input("Password", type="password")
            new_role = st.selectbox(
                "Role", ["Owner", "Admin", "Kasir", "Penjahit"]
            )
            create_user = st.form_submit_button(
                "Buat Akun", use_container_width=True
            )

        if create_user:
            if len(new_username.strip()) < 3 or len(new_password) < 6:
                st.error("Username minimal 3 karakter dan password minimal 6 karakter.")
            else:
                try:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO app_users
                            (username, password_hash, role)
                            VALUES (?, ?, ?)
                            """,
                            (
                                new_username.strip(),
                                hash_password(new_password),
                                new_role,
                            ),
                        )
                        conn.commit()
                    st.success("Akun berhasil dibuat.")
                except sqlite3.IntegrityError:
                    st.error("Username sudah digunakan.")

    st.markdown("### 💾 Backup Database")
    st.write(
        "Backup menyimpan seluruh data pelanggan, pesanan, pembayaran, "
        "dan riwayat produksi."
    )

    if st.button("💾 Buat Backup Database", use_container_width=True):
        try:
            backup = backup_database()
            if backup:
                st.success(f"Backup berhasil dibuat: {backup.name}")
        except Exception as e:
            st.error(f"Backup gagal: {e}")

    st.divider()
    st.markdown("### 📦 Backup yang tersedia")

    backups = sorted(BACKUP_DIR.glob("*.db"), reverse=True)
    if backups:
        backup_table = pd.DataFrame(
            [
                {
                    "File": p.name,
                    "Ukuran": f"{p.stat().st_size / 1024:.1f} KB",
                    "Dibuat": datetime.fromtimestamp(
                        p.stat().st_mtime
                    ).strftime("%d-%m-%Y %H:%M"),
                }
                for p in backups[:20]
            ]
        )
        st.dataframe(backup_table, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada backup.")

    st.divider()
    st.markdown("### ⬇️ Download Database")

    if DB_PATH.exists():
        with open(DB_PATH, "rb") as database_file:
            st.download_button(
                label="⬇️ Download tailormate.db",
                data=database_file,
                file_name=f"tailormate_{datetime.now().strftime('%Y%m%d')}.db",
                mime="application/octet-stream",
                use_container_width=True,
            )

    st.divider()
    st.markdown("### ℹ️ Tentang Aplikasi")
    st.write(
        f"""
**{APP_NAME}**

Versi **{APP_VERSION}**

Fitur utama:
- Data pelanggan & ukuran
- Pesanan custom made
- Monitoring produksi
- Galeri desain
- Pembayaran & riwayat transaksi
- Piutang pelanggan
- Dashboard analitik
- Laporan bulanan
- Export CSV
- WhatsApp pelanggan
- Backup database
- Migrasi database versi lama
- Login & role pengguna
- Stok bahan dan mutasi
- Pengeluaran usaha & laba kotor
- Manajemen karyawan
- Invoice pesanan
"""
    )
