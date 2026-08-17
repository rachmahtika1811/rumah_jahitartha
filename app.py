import os
import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
from datetime import datetime

# Directori folder untuk menyimpan foto baju/desain
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- 1. INISIALISASI & MIGRASI DATABASE ---
def init_db():
    conn = sqlite3.connect("tailormate.db")
    c = conn.cursor()
    # Tabel Pelanggan
    c.execute('''CREATE TABLE IF NOT EXISTS pelanggan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nama TEXT NOT NULL,
                    telepon TEXT,
                    lingkar_dada REAL,
                    lingkar_pinggang REAL,
                    panjang_lengan REAL,
                    lebar_bahu REAL,
                    catatan TEXT
                )''')
    # Tabel Pesanan
    c.execute('''CREATE TABLE IF NOT EXISTS pesanan (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pelanggan_id INTEGER,
                    jenis_pakaian TEXT,
                    tgl_terima TEXT,
                    tgl_deadline TEXT,
                    status TEXT,
                    total_biaya REAL,
                    dp REAL,
                    foto_desain TEXT,
                    FOREIGN KEY(pelanggan_id) REFERENCES pelanggan(id)
                )''')
    
    # Migrasi otomatis: Tambah kolom deskripsi_pesanan jika belum ada
    c.execute("PRAGMA table_info(pesanan)")
    columns = [column[1] for column in c.fetchall()]
    if "deskripsi_pesanan" not in columns:
        c.execute("ALTER TABLE pesanan ADD COLUMN deskripsi_pesanan TEXT")
        
    conn.commit()
    conn.close()

init_db()

# --- 2. KONFIGURASI HALAMAN & SIDEBAR ---
st.set_page_config(page_title="Rumah Jahit Artha - Manajemen Desain & Pesanan", layout="wide")
st.title("🪡 Rumah Jahit Artha: Sistem Manajemen & Galeri Desain Penjahit")

# Deskripsi usaha di sidebar
st.sidebar.title("📍 Rumah Jahit Artha")
st.sidebar.caption("Custom Made By Order | Graduation | Engagement | Bridesmaid | Kemeja Cowo | Vermak Pakaian")
st.sidebar.markdown("**Lokasi:** Perum. Grand Kampoeng Kito (Paal Merah), Jambi")
st.sidebar.divider()

# Sidebar Navigasi Utama
menu = st.sidebar.radio(
    "Navigasi Utama", 
    [
        "Dashboard & Status Pesanan", 
        "🎨 Galeri Desain Baju", 
        "Tambah Pelanggan & Ukuran", 
        "Input Pesanan & Upload Desain", 
        "Data Pelanggan"
    ]
)

# --- 3. MODUL: DASHBOARD PESANAN ---
if menu == "Dashboard & Status Pesanan":
    st.subheader("📌 Status & Alur Produksi Pesanan")
    
    conn = sqlite3.connect("tailormate.db")
    query = '''SELECT p.id, pl.nama, p.jenis_pakaian, p.deskripsi_pesanan, p.tgl_deadline, p.status, p.total_biaya, p.dp, p.foto_desain 
               FROM pesanan p JOIN pelanggan pl ON p.pelanggan_id = pl.id'''
    df_pesanan = pd.read_sql_query(query, conn)
    conn.close()

    if not df_pesanan.empty:
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        col_stat1.metric("Total Pesanan", len(df_pesanan))
        col_stat2.metric("Dalam Proses", len(df_pesanan[df_pesanan['status'] != 'Selesai']))
        col_stat3.metric("Pesanan Selesai", len(df_pesanan[df_pesanan['status'] == 'Selesai']))

        st.divider()

        # Tampilkan Data Ringkas
        st.dataframe(df_pesanan.drop(columns=['foto_desain']), use_container_width=True)

        st.divider()
        st.subheader("🔄 Update Status Pekerjaan")
        col_up1, col_up2 = st.columns(2)
        with col_up1:
            order_id = st.number_input("Masukkan ID Pesanan:", min_value=1, step=1)
        with col_up2:
            new_status = st.selectbox("Pilih Status Baru:", ["Diterima", "Pemotongan Pola", "Penjahitan", "Fitting", "Finishing", "Selesai"])
        
        if st.button("Update Status"):
            conn = sqlite3.connect("tailormate.db")
            c = conn.cursor()
            c.execute("UPDATE pesanan SET status = ? WHERE id = ?", (new_status, order_id))
            conn.commit()
            conn.close()
            st.success(f"Status Pesanan #{order_id} berhasil diubah ke {new_status}!")
            st.rerun()
    else:
        st.info("Belum ada data pesanan.")

# --- 4. MODUL: GALERI DESAIN BAJU ---
elif menu == "🎨 Galeri Desain Baju":
    st.subheader("🖼️ Galeri Visual Desain & Referensi Pola Baju")
    
    conn = sqlite3.connect("tailormate.db")
    query = '''SELECT p.id, pl.nama, p.jenis_pakaian, p.deskripsi_pesanan, p.tgl_deadline, p.status, p.foto_desain,
                      pl.lingkar_dada, pl.lingkar_pinggang, pl.panjang_lengan, pl.lebar_bahu
               FROM pesanan p JOIN pelanggan pl ON p.pelanggan_id = pl.id 
               WHERE p.foto_desain IS NOT NULL AND p.foto_desain != '' '''
    df_galeri = pd.read_sql_query(query, conn)
    conn.close()

    if not df_galeri.empty:
        # Tampilkan gambar dalam grid kartu 3 kolom
        cols = st.columns(3)
        for idx, row in df_galeri.iterrows():
            col = cols[idx % 3]
            with col:
                with st.container(border=True):
                    file_path = os.path.join(UPLOAD_DIR, row['foto_desain'])
                    if os.path.exists(file_path):
                        img = Image.open(file_path)
                        st.image(img, use_container_width=True, caption=f"Desain ID #{row['id']}")
                    else:
                        st.warning("File gambar tidak ditemukan.")
                    
                    st.markdown(f"**Pelanggan:** {row['nama']}")
                    st.markdown(f"**Jenis:** {row['jenis_pakaian']}")
                    if row['deskripsi_pesanan']:
                        st.markdown(f"**Deskripsi:** {row['deskripsi_pesanan']}")
                    st.markdown(f"**Status:** `{row['status']}` | **Deadline:** {row['tgl_deadline']}")
                    
                    # Expander Detail Ukuran Pelanggan
                    with st.expander("📏 Detail Ukuran Body"):
                        st.write(f"- Lingkar Dada: **{row['lingkar_dada']} cm**")
                        st.write(f"- Lingkar Pinggang: **{row['lingkar_pinggang']} cm**")
                        st.write(f"- Panjang Lengan: **{row['panjang_lengan']} cm**")
                        st.write(f"- Lebar Bahu: **{row['lebar_bahu']} cm**")
    else:
        st.info("Belum ada foto desain baju yang diunggah pada pesanan.")

# --- 5. MODUL: TAMBAH PELANGGAN ---
elif menu == "Tambah Pelanggan & Ukuran":
    st.subheader("👤 Input Master Pelanggan & Ukuran")
    
    with st.form("form_pelanggan"):
        col1, col2 = st.columns(2)
        with col1:
            nama = st.text_input("Nama Lengkap*")
            telepon = st.text_input("Nomor Telepon/WA*")
            lingkar_dada = st.number_input("Lingkar Dada (cm)", min_value=0.0, step=0.5)
            lingkar_pinggang = st.number_input("Lingkar Pinggang (cm)", min_value=0.0, step=0.5)
        
        with col2:
            panjang_lengan = st.number_input("Panjang Lengan (cm)", min_value=0.0, step=0.5)
            lebar_bahu = st.number_input("Lebar Bahu (cm)", min_value=0.0, step=0.5)
            catatan = st.text_area("Catatan Khusus Postur/Gaya")
        
        if st.form_submit_button("Simpan Data Pelanggan"):
            if nama and telepon:
                conn = sqlite3.connect("tailormate.db")
                c = conn.cursor()
                c.execute('''INSERT INTO pelanggan 
                             (nama, telepon, lingkar_dada, lingkar_pinggang, panjang_lengan, lebar_bahu, catatan)
                             VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                          (nama, telepon, lingkar_dada, lingkar_pinggang, panjang_lengan, lebar_bahu, catatan))
                conn.commit()
                conn.close()
                st.success(f"Data pelanggan {nama} berhasil disimpan!")
            else:
                st.error("Nama dan No Telepon wajib diisi.")

# --- 6. MODUL: INPUT PESANAN & UPLOAD DESAIN ---
elif menu == "Input Pesanan & Upload Desain":
    st.subheader("🛍️ Input Pesanan Baru + Lampiran Foto Desain")
    
    conn = sqlite3.connect("tailormate.db")
    pelanggan_df = pd.read_sql_query("SELECT id, nama, telepon FROM pelanggan", conn)
    conn.close()
    
    if not pelanggan_df.empty:
        pelanggan_dict = {f"{row['nama']} ({row['telepon']})": row['id'] for _, row in pelanggan_df.iterrows()}
        selected_pelanggan = st.selectbox("Pilih Pelanggan:", list(pelanggan_dict.keys()))
        pelanggan_id = pelanggan_dict[selected_pelanggan]
        
        with st.form("form_pesanan"):
            col1, col2 = st.columns(2)
            with col1:
                jenis_pakaian = st.selectbox("Jenis Pakaian", ["Kemeja Pria", "Gaun/Pesta", "Celana Formal", "Batik", "Jas", "Kebaya", "Lainnya"])
                deskripsi_pesanan = st.text_area("Deskripsi Tambahan Pesanan (Model, Payet, Pilihan Kain, dll.)")
                tgl_terima = st.date_input("Tanggal Terima", datetime.now())
                tgl_deadline = st.date_input("Tanggal Selesai (Deadline)")
                
                # Upload Foto Desain/Model Baju
                uploaded_file = st.file_uploader("Upload Foto Desain / Pola Baju (JPG, PNG)", type=["jpg", "jpeg", "png"])
            
            with col2:
                ongkos_jahit = st.number_input("Biaya Ongkos Jahit (Rp)", min_value=0.0, step=10000.0)
                biaya_bahan = st.number_input("Biaya Tambahan Bahan/Aksesoris (Rp)", min_value=0.0, step=5000.0)
                dp = st.number_input("Uang Muka / DP (Rp)", min_value=0.0, step=10000.0)
            
            total_biaya = ongkos_jahit + biaya_bahan
            st.write(f"**Estimasi Total Biaya:** Rp {total_biaya:,.2f}")
            
            submitted = st.form_submit_button("Simpan Pesanan")
            
            if submitted:
                filename = ""
                if uploaded_file is not None:
                    # Simpan file gambar dengan nama unik berdasarkan waktu
                    filename = f"desain_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_file.name}"
                    file_path = os.path.join(UPLOAD_DIR, filename)
                    with open(file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())

                conn = sqlite3.connect("tailormate.db")
                c = conn.cursor()
                c.execute('''INSERT INTO pesanan 
                             (pelanggan_id, jenis_pakaian, deskripsi_pesanan, tgl_terima, tgl_deadline, status, total_biaya, dp, foto_desain)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                          (pelanggan_id, jenis_pakaian, deskripsi_pesanan, str(tgl_terima), str(tgl_deadline), "Diterima", total_biaya, dp, filename))
                conn.commit()
                conn.close()
                st.success("Pesanan dan foto desain berhasil tersimpan!")
    else:
        st.warning("Tambahkan data pelanggan terlebih dahulu di menu 'Tambah Pelanggan & Ukuran'.")

# --- 7. MODUL: MASTER DATA PELANGGAN ---
elif menu == "Data Pelanggan":
    st.subheader("📋 Master Data Pelanggan & Ukuran Body")
    conn = sqlite3.connect("tailormate.db")
    df_pelanggan = pd.read_sql_query("SELECT * FROM pelanggan", conn)
    conn.close()
    
    if not df_pelanggan.empty:
        st.dataframe(df_pelanggan, use_container_width=True)
    else:
        st.info("Belum ada data pelanggan.")