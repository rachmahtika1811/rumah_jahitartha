import os
import sqlite3
import pandas as pd
import streamlit as st
from PIL import Image
from datetime import datetime

# --- KONFIGURASI HALAMAN (Harus di paling atas sebelum apapun) ---
st.set_page_config(page_title="Rumah Jahit Artha - Manajemen Desain & Pesanan", layout="wide")

# --- KONFIGURASI DATABASE & CACHE ---
@st.cache_resource
def get_db_connection():
    """Membuat koneksi database yang di-cache untuk performa"""
    conn = sqlite3.connect("tailormate.db", check_same_thread=False)
    return conn

def init_db():
    """Inisialisasi database dan tabel"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Tabel pelanggan
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
    
    # Tabel pesanan
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
    
    # Tambah kolom deskripsi_pesanan jika belum ada
    c.execute("PRAGMA table_info(pesanan)")
    columns = [column[1] for column in c.fetchall()]
    if "deskripsi_pesanan" not in columns:
        c.execute("ALTER TABLE pesanan ADD COLUMN deskripsi_pesanan TEXT")
    
    conn.commit()
    conn.close()

# Inisialisasi database saat aplikasi dimulai
init_db()

# --- KONFIGURASI FOLDER UPLOAD ---
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- UI SIDEBAR ---
st.title("🪡 Rumah Jahit Artha: Sistem Manajemen & Galeri Desain Penjahit")

st.sidebar.title("📍 Rumah Jahit Artha")
st.sidebar.caption("Custom Made By Order | Graduation | Engagement | Bridesmaid | Kemeja Cowo | Vermak Pakaian")
st.sidebar.markdown("**Lokasi:** Perum. Grand Kampoeng Kito (Paal Merah), Jambi")
st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigasi Utama", 
    [
        "Dashboard & Status Pesanan", 
        "🎨 Galeri Desain Baju", 
        "✨ Konsultasi & Foto Katalog Asli",
        "Tambah Pelanggan & Ukuran", 
        "Input Pesanan & Upload Desain", 
        "Data Pelanggan"
    ]
)

# --- FUNGSI HELPER ---
def format_rupiah(nilai):
    """Format angka ke format Rupiah"""
    return f"Rp {nilai:,.0f}".replace(",", ".")

def get_pelanggan_options():
    """Ambil daftar pelanggan untuk dropdown"""
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT id, nama, telepon FROM pelanggan", conn)
    conn.close()
    
    if df.empty:
        return {}
    
    return {f"{row['nama']} ({row['telepon']})": row['id'] for _, row in df.iterrows()}

# --- MODUL DASHBOARD ---
if menu == "Dashboard & Status Pesanan":
    st.subheader("📌 Status & Alur Produksi Pesanan")
    
    conn = get_db_connection()
    query = '''SELECT p.id, pl.nama, p.jenis_pakaian, p.deskripsi_pesanan, 
                      p.tgl_deadline, p.status, p.total_biaya, p.dp, p.foto_desain 
               FROM pesanan p 
               JOIN pelanggan pl ON p.pelanggan_id = pl.id'''
    df_pesanan = pd.read_sql_query(query, conn)
    conn.close()

    if not df_pesanan.empty:
        # Metrics
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("Total Pesanan", len(df_pesanan))
        with col_stat2:
            st.metric("Dalam Proses", len(df_pesanan[df_pesanan['status'] != 'Selesai']))
        with col_stat3:
            st.metric("Pesanan Selesai", len(df_pesanan[df_pesanan['status'] == 'Selesai']))

        st.divider()
        
        # Tampilkan dataframe tanpa kolom foto_desain
        st.dataframe(
            df_pesanan.drop(columns=['foto_desain']), 
            use_container_width=True,
            column_config={
                "total_biaya": st.column_config.NumberColumn("Total (Rp)", format="Rp %d"),
                "dp": st.column_config.NumberColumn("DP (Rp)", format="Rp %d")
            }
        )

        st.divider()
        st.subheader("🔄 Update Status Pekerjaan")
        
        col_up1, col_up2, col_up3 = st.columns(3)
        with col_up1:
            order_id = st.number_input("ID Pesanan:", min_value=1, step=1, key="update_order_id")
        with col_up2:
            new_status = st.selectbox(
                "Status Baru:", 
                ["Diterima", "Pemotongan Pola", "Penjahitan", "Fitting", "Finishing", "Selesai"],
                key="update_status"
            )
        with col_up3:
            if st.button("Update Status", use_container_width=True):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("UPDATE pesanan SET status = ? WHERE id = ?", (new_status, order_id))
                rows_affected = c.rowcount
                conn.commit()
                conn.close()
                
                if rows_affected > 0:
                    st.success(f"✅ Status Pesanan #{order_id} berhasil diubah ke {new_status}!")
                else:
                    st.error(f"❌ ID Pesanan #{order_id} tidak ditemukan!")
                st.rerun()
    else:
        st.info("📭 Belum ada data pesanan.")

# --- MODUL GALERI DESAIN ---
elif menu == "🎨 Galeri Desain Baju":
    st.subheader("🖼️ Galeri Visual Desain & Referensi Pola Baju")
    
    conn = get_db_connection()
    query = '''SELECT p.id, pl.nama, p.jenis_pakaian, p.deskripsi_pesanan, 
                      p.tgl_deadline, p.status, p.foto_desain,
                      pl.lingkar_dada, pl.lingkar_pinggang, pl.panjang_lengan, pl.lebar_bahu
               FROM pesanan p 
               JOIN pelanggan pl ON p.pelanggan_id = pl.id 
               WHERE p.foto_desain IS NOT NULL AND p.foto_desain != '' '''
    df_galeri = pd.read_sql_query(query, conn)
    conn.close()

    if not df_galeri.empty:
        # Tampilkan dalam grid 3 kolom
        for idx, row in df_galeri.iterrows():
            with st.container(border=True):
                col_img, col_info = st.columns([1, 2])
                
                with col_img:
                    file_path = os.path.join(UPLOAD_DIR, row['foto_desain'])
                    if os.path.exists(file_path):
                        try:
                            img = Image.open(file_path)
                            st.image(img, use_container_width=True, caption=f"Desain ID #{row['id']}")
                        except Exception as e:
                            st.error(f"Error loading image: {e}")
                    else:
                        st.warning("📁 File gambar tidak ditemukan")
                
                with col_info:
                    st.markdown(f"**Pelanggan:** {row['nama']}")
                    st.markdown(f"**Jenis:** {row['jenis_pakaian']}")
                    if row['deskripsi_pesanan']:
                        st.markdown(f"**Deskripsi:** {row['deskripsi_pesanan']}")
                    st.markdown(f"**Status:** `{row['status']}`")
                    st.markdown(f"**Deadline:** {row['tgl_deadline']}")
                    
                    with st.expander("📏 Detail Ukuran Body"):
                        st.write(f"- Lingkar Dada: **{row['lingkar_dada']} cm**")
                        st.write(f"- Lingkar Pinggang: **{row['lingkar_pinggang']} cm**")
                        st.write(f"- Panjang Lengan: **{row['panjang_lengan']} cm**")
                        st.write(f"- Lebar Bahu: **{row['lebar_bahu']} cm**")
                
                st.divider()
    else:
        st.info("📭 Belum ada foto desain baju yang diunggah pada pesanan.")

# --- MODUL KONSULTASI & KATALOG ---
elif menu == "✨ Konsultasi & Foto Katalog Asli":
    st.subheader("🖼️ Referensi Foto Katalog Asli & Panduan Penjahitan")
    st.info("💡 Pilih kriteria busana untuk menampilkan foto referensi asli beserta rekomendasi teknis penjahitan.")

    col1, col2 = st.columns(2)
    with col1:
        kategori_pakaian = st.selectbox(
            "Jenis Busana", 
            ["Gaun Bridesmaid / Pesta", "Kebaya Modern / Wisuda", "Kemeja Motif / Batik Pria", "Jas Formal / Blazer"]
        )
        warna_bahan = st.selectbox(
            "Pilihan Warna Utama", 
            ["Sage Green / Hijau Soft", "Navy / Biru Dongker", "Maroon / Merah Tua", "Rosegold / Dusty Pink"]
        )
    with col2:
        gaya_potongan = st.selectbox(
            "Gaya / Model Potongan", 
            ["A-Line Dress", "Slim Fit", "Lengan Balon / Puff", "Mermaid Style"]
        )
        detail_desain = st.text_area(
            "Detail Dekorasi", 
            "Aksen payet mutiara di bagian kerah dan dada, pemotongan V-neck."
        )

    if st.button("🔍 Tampilkan Foto Referensi Katalog Asli"):
        st.divider()
        st.markdown(f"### 📋 Panduan Teknis & Spesifikasi Jahitan ({kategori_pakaian})")
        
        st.markdown(f"""
        - **Model Cut:** {gaya_potongan}
        - **Rekomendasi Kain Utama:** Satin Velvet Premium, Silk Organza, atau Brokat Tulle
        - **Jarum & Benang:** Gunakan Jarum Microtex ukuran 70/10 - 80/12 agar serat kain halus tidak berserat
        - **Finishing Kampuh:** Teknik Stik Balik (*French Seam*) atau obras halus 4 benang
        - **Aplikasi Aksesoris:** {detail_desain}
        """)

        st.divider()
        st.markdown("### 📸 Foto Katalog Referensi Nyata (Multi-Sudut)")

        catalog_database = {
            "Gaun Bridesmaid / Pesta": {
                "depan": "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=800&q=80",
                "samping": "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?auto=format&fit=crop&w=800&q=80",
                "belakang": "https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=800&q=80"
            },
            "Kebaya Modern / Wisuda": {
                "depan": "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
                "samping": "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=800&q=80",
                "belakang": "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=800&q=80"
            },
            "Kemeja Motif / Batik Pria": {
                "depan": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=800&q=80",
                "samping": "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=800&q=80",
                "belakang": "https://images.unsplash.com/photo-1603252109303-2751441dd157?auto=format&fit=crop&w=800&q=80"
            },
            "Jas Formal / Blazer": {
                "depan": "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=800&q=80",
                "samping": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
                "belakang": "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?auto=format&fit=crop&w=800&q=80"
            }
        }

        photos = catalog_database.get(kategori_pakaian, catalog_database["Gaun Bridesmaid / Pesta"])

        tab1, tab2, tab3 = st.tabs(["📸 Tampak Depan", "📸 Tampak Samping", "📸 Tampak Belakang"])

        with tab1:
            st.image(photos["depan"], caption=f"Tampak Depan - {kategori_pakaian} ({warna_bahan})", use_container_width=True)
        with tab2:
            st.image(photos["samping"], caption=f"Tampak Samping - {kategori_pakaian} ({warna_bahan})", use_container_width=True)
        with tab3:
            st.image(photos["belakang"], caption=f"Tampak Belakang - {kategori_pakaian} ({warna_bahan})", use_container_width=True)

        st.success("✅ Foto katalog berhasil dimuat!")

# --- MODUL INPUT PELANGGAN ---
elif menu == "Tambah Pelanggan & Ukuran":
    st.subheader("👤 Input Master Pelanggan & Ukuran")
    
    with st.form("form_pelanggan", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            nama = st.text_input("Nama Lengkap *", placeholder="Masukkan nama lengkap")
            telepon = st.text_input("Nomor Telepon/WA *", placeholder="08xx-xxxx-xxxx")
            lingkar_dada = st.number_input("Lingkar Dada (cm)", min_value=0.0, step=0.5, format="%.1f")
            lingkar_pinggang = st.number_input("Lingkar Pinggang (cm)", min_value=0.0, step=0.5, format="%.1f")
        
        with col2:
            panjang_lengan = st.number_input("Panjang Lengan (cm)", min_value=0.0, step=0.5, format="%.1f")
            lebar_bahu = st.number_input("Lebar Bahu (cm)", min_value=0.0, step=0.5, format="%.1f")
            catatan = st.text_area("Catatan Khusus Postur/Gaya", placeholder="Contoh: Bahu turun, perut buncit, dll")
        
        submitted = st.form_submit_button("💾 Simpan Data Pelanggan", use_container_width=True)
        
        if submitted:
            if nama and telepon:
                try:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute('''INSERT INTO pelanggan 
                                 (nama, telepon, lingkar_dada, lingkar_pinggang, panjang_lengan, lebar_bahu, catatan)
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                              (nama, telepon, lingkar_dada, lingkar_pinggang, panjang_lengan, lebar_bahu, catatan))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ Data pelanggan **{nama}** berhasil disimpan!")
                except Exception as e:
                    st.error(f"❌ Error menyimpan data: {e}")
            else:
                st.error("⚠️ Nama dan No Telepon wajib diisi.")

# --- MODUL INPUT PESANAN ---
elif menu == "Input Pesanan & Upload Desain":
    st.subheader("🛍️ Input Pesanan Baru + Lampiran Foto Desain")
    
    pelanggan_dict = get_pelanggan_options()
    
    if pelanggan_dict:
        selected_pelanggan = st.selectbox("Pilih Pelanggan:", list(pelanggan_dict.keys()))
        pelanggan_id = pelanggan_dict[selected_pelanggan]
        
        with st.form("form_pesanan", clear_on_submit=False):
            col1, col2 = st.columns(2)
            
            with col1:
                jenis_pakaian = st.selectbox(
                    "Jenis Pakaian", 
                    ["Kemeja Pria", "Gaun/Pesta", "Celana Formal", "Batik", "Jas", "Kebaya", "Lainnya"]
                )
                deskripsi_pesanan = st.text_area(
                    "Deskripsi Tambahan Pesanan", 
                    placeholder="Model, Payet, Pilihan Kain, dll.",
                    height=100
                )
                tgl_terima = st.date_input("Tanggal Terima", datetime.now())
                tgl_deadline = st.date_input("Tanggal Selesai (Deadline)", datetime.now())
                uploaded_file = st.file_uploader(
                    "Upload Foto Desain / Pola Baju", 
                    type=["jpg", "jpeg", "png"],
                    help="Format: JPG, JPEG, PNG"
                )
            
            with col2:
                ongkos_jahit = st.number_input("Biaya Ongkos Jahit (Rp)", min_value=0.0, step=10000.0, format="%.0f")
                biaya_bahan = st.number_input("Biaya Tambahan Bahan/Aksesoris (Rp)", min_value=0.0, step=5000.0, format="%.0f")
                dp = st.number_input("Uang Muka / DP (Rp)", min_value=0.0, step=10000.0, format="%.0f")
            
            total_biaya = ongkos_jahit + biaya_bahan
            st.metric("Estimasi Total Biaya", format_rupiah(total_biaya))
            
            submitted = st.form_submit_button("💾 Simpan Pesanan", use_container_width=True)
            
            if submitted:
                filename = ""
                if uploaded_file is not None:
                    try:
                        # Generate unique filename
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        original_name = uploaded_file.name.replace(" ", "_")
                        filename = f"desain_{timestamp}_{original_name}"
                        file_path = os.path.join(UPLOAD_DIR, filename)
                        
                        # Simpan file
                        with open(file_path, "wb") as f:
                            f.write(uploaded_file.getvalue())
                        
                        st.success(f"✅ File desain berhasil diupload: {filename}")
                    except Exception as e:
                        st.error(f"❌ Error upload file: {e}")
                        filename = ""

                try:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute('''INSERT INTO pesanan 
                                 (pelanggan_id, jenis_pakaian, deskripsi_pesanan, tgl_terima, tgl_deadline, 
                                  status, total_biaya, dp, foto_desain)
                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                              (pelanggan_id, jenis_pakaian, deskripsi_pesanan, 
                               str(tgl_terima), str(tgl_deadline), "Diterima", 
                               total_biaya, dp, filename))
                    conn.commit()
                    conn.close()
                    st.success("✅ Pesanan dan foto desain berhasil tersimpan!")
                    st.balloons()
                except Exception as e:
                    st.error(f"❌ Error menyimpan pesanan: {e}")
    else:
        st.warning("⚠️ Tambahkan data pelanggan terlebih dahulu di menu 'Tambah Pelanggan & Ukuran'.")

# --- MODUL DATA PELANGGAN ---
elif menu == "Data Pelanggan":
    st.subheader("📋 Master Data Pelanggan & Ukuran Body")
    
    conn = get_db_connection()
    df_pelanggan = pd.read_sql_query("SELECT * FROM pelanggan", conn)
    conn.close()
    
    if not df_pelanggan.empty:
        st.dataframe(
            df_pelanggan, 
            use_container_width=True,
            column_config={
                "lingkar_dada": st.column_config.NumberColumn("Dada (cm)", format="%.1f"),
                "lingkar_pinggang": st.column_config.NumberColumn("Pinggang (cm)", format="%.1f"),
                "panjang_lengan": st.column_config.NumberColumn("Lengan (cm)", format="%.1f"),
                "lebar_bahu": st.column_config.NumberColumn("Bahu (cm)", format="%.1f")
            }
        )
        
        # Download button
        csv = df_pelanggan.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(
            "📥 Download Data Pelanggan (CSV)",
            csv,
            file_name=f"pelanggan_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.info("📭 Belum ada data pelanggan.")