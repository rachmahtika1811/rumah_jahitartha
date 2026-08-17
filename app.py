import os
import sqlite3
import uuid
from pathlib import Path
from datetime import date, datetime

import pandas as pd
import streamlit as st
from PIL import Image


# ============================================================
# KONFIGURASI
# ============================================================

st.set_page_config(
    page_title="Rumah Jahit Artha",
    page_icon="🪡",
    layout="wide",
)

DB_PATH = "tailormate.db"
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE_MB = 5


# ============================================================
# DATABASE
# ============================================================

def get_connection():
    """Membuka koneksi database SQLite."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Membuat tabel database jika belum tersedia."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pelanggan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nama TEXT NOT NULL,
                telepon TEXT NOT NULL,
                lingkar_dada REAL DEFAULT 0,
                lingkar_pinggang REAL DEFAULT 0,
                panjang_lengan REAL DEFAULT 0,
                lebar_bahu REAL DEFAULT 0,
                catatan TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pesanan (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pelanggan_id INTEGER NOT NULL,
                jenis_pakaian TEXT NOT NULL,
                deskripsi_pesanan TEXT,
                tgl_terima TEXT NOT NULL,
                tgl_deadline TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Diterima',
                total_biaya INTEGER DEFAULT 0,
                dp INTEGER DEFAULT 0,
                foto_desain TEXT,
                FOREIGN KEY (pelanggan_id)
                    REFERENCES pelanggan(id)
                    ON DELETE CASCADE
            )
        """)

        # Migrasi database lama
        cursor.execute("PRAGMA table_info(pesanan)")
        columns = [column[1] for column in cursor.fetchall()]

        if "deskripsi_pesanan" not in columns:
            cursor.execute(
                "ALTER TABLE pesanan ADD COLUMN deskripsi_pesanan TEXT"
            )

        conn.commit()


init_db()


# ============================================================
# HELPER
# ============================================================

STATUS_PESANAN = [
    "Diterima",
    "Pemotongan Pola",
    "Penjahitan",
    "Fitting",
    "Finishing",
    "Selesai",
]


def format_rupiah(value):
    """Format angka menjadi Rupiah."""
    if value is None:
        value = 0

    try:
        value = int(value)
    except (ValueError, TypeError):
        value = 0

    return f"Rp {value:,.0f}".replace(",", ".")


def save_uploaded_image(uploaded_file):
    """
    Menyimpan file upload dengan nama random.
    Menghindari penggunaan langsung uploaded_file.name.
    """
    if uploaded_file is None:
        return ""

    # Cek ukuran file
    file_size_mb = uploaded_file.size / (1024 * 1024)

    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise ValueError(
            f"Ukuran file terlalu besar. Maksimal {MAX_UPLOAD_SIZE_MB} MB."
        )

    # Validasi ekstensi
    allowed_extensions = {".jpg", ".jpeg", ".png"}
    extension = Path(uploaded_file.name).suffix.lower()

    if extension not in allowed_extensions:
        raise ValueError(
            "Format gambar tidak didukung. Gunakan JPG, JPEG, atau PNG."
        )

    # Nama file random
    filename = f"desain_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{extension}"

    file_path = UPLOAD_DIR / filename

    with open(file_path, "wb") as file:
        file.write(uploaded_file.getbuffer())

    # Pastikan file benar-benar merupakan gambar
    try:
        with Image.open(file_path) as image:
            image.verify()
    except Exception:
        if file_path.exists():
            file_path.unlink()

        raise ValueError("File yang diupload bukan gambar yang valid.")

    return filename


def delete_design_file(filename):
    """Menghapus file desain jika ada."""
    if not filename:
        return

    file_path = UPLOAD_DIR / filename

    try:
        if file_path.exists():
            file_path.unlink()
    except OSError:
        pass


# ============================================================
# SIDEBAR
# ============================================================

st.title("🪡 Rumah Jahit Artha")
st.caption("Sistem Manajemen Pelanggan, Pesanan, Ukuran & Galeri Desain")

st.sidebar.title("📍 Rumah Jahit Artha")
st.sidebar.caption(
    "Custom Made By Order | Graduation | Engagement | "
    "Bridesmaid | Kemeja Cowo | Vermak Pakaian"
)
st.sidebar.markdown(
    "**Lokasi:** Perum. Grand Kampoeng Kito (Paal Merah), Jambi"
)
st.sidebar.divider()

menu = st.sidebar.radio(
    "Navigasi Utama",
    [
        "Dashboard & Status Pesanan",
        "🎨 Galeri Desain Baju",
        "✨ Konsultasi & Foto Katalog",
        "Tambah Pelanggan & Ukuran",
        "Input Pesanan & Upload Desain",
        "Data Pelanggan",
    ],
)


# ============================================================
# DASHBOARD
# ============================================================

if menu == "Dashboard & Status Pesanan":

    st.subheader("📌 Dashboard & Status Produksi")

    with get_connection() as conn:
        query = """
            SELECT
                p.id,
                pl.nama,
                pl.telepon,
                p.jenis_pakaian,
                p.deskripsi_pesanan,
                p.tgl_terima,
                p.tgl_deadline,
                p.status,
                p.total_biaya,
                p.dp,
                (p.total_biaya - p.dp) AS sisa_bayar,
                p.foto_desain
            FROM pesanan p
            JOIN pelanggan pl
                ON p.pelanggan_id = pl.id
            ORDER BY p.id DESC
        """

        df_pesanan = pd.read_sql_query(query, conn)

    if df_pesanan.empty:
        st.info("Belum ada data pesanan.")
    else:

        total_pesanan = len(df_pesanan)
        selesai = len(df_pesanan[df_pesanan["status"] == "Selesai"])
        proses = total_pesanan - selesai
        total_pendapatan = int(df_pesanan["total_biaya"].sum())
        total_dp = int(df_pesanan["dp"].sum())
        total_sisa = int(df_pesanan["sisa_bayar"].sum())

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Pesanan",
            total_pesanan
        )

        col2.metric(
            "Dalam Proses",
            proses
        )

        col3.metric(
            "Selesai",
            selesai
        )

        col4.metric(
            "Total Nilai Pesanan",
            format_rupiah(total_pendapatan)
        )

        st.divider()

        col5, col6 = st.columns(2)

        col5.metric(
            "Total DP",
            format_rupiah(total_dp)
        )

        col6.metric(
            "Total Sisa Pembayaran",
            format_rupiah(total_sisa)
        )

        st.divider()

        # Filter status
        filter_status = st.selectbox(
            "Filter Status",
            ["Semua"] + STATUS_PESANAN
        )

        df_display = df_pesanan.copy()

        if filter_status != "Semua":
            df_display = df_display[
                df_display["status"] == filter_status
            ]

        # Format uang untuk tampilan
        df_display["total_biaya"] = df_display["total_biaya"].apply(
            format_rupiah
        )
        df_display["dp"] = df_display["dp"].apply(
            format_rupiah
        )
        df_display["sisa_bayar"] = df_display["sisa_bayar"].apply(
            format_rupiah
        )

        df_display = df_display.drop(
            columns=["foto_desain"],
            errors="ignore"
        )

        st.dataframe(
            df_display,
            use_container_width=True,
            hide_index=True
        )

        # ----------------------------------------------------
        # UPDATE STATUS
        # ----------------------------------------------------

        st.divider()
        st.subheader("🔄 Update Status Pekerjaan")

        col1, col2 = st.columns(2)

        with col1:
            order_id = st.number_input(
                "ID Pesanan",
                min_value=1,
                step=1
            )

        with col2:
            new_status = st.selectbox(
                "Status Baru",
                STATUS_PESANAN
            )

        if st.button(
            "Update Status",
            type="primary",
            use_container_width=True
        ):
            with get_connection() as conn:

                cursor = conn.cursor()

                cursor.execute(
                    """
                    SELECT id
                    FROM pesanan
                    WHERE id = ?
                    """,
                    (order_id,)
                )

                order_exists = cursor.fetchone()

                if not order_exists:
                    st.error(
                        f"Pesanan #{order_id} tidak ditemukan."
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE pesanan
                        SET status = ?
                        WHERE id = ?
                        """,
                        (new_status, order_id)
                    )

                    conn.commit()

                    st.success(
                        f"Status Pesanan #{order_id} berhasil "
                        f"diubah menjadi **{new_status}**."
                    )

                    st.rerun()


# ============================================================
# GALERI DESAIN
# ============================================================

elif menu == "🎨 Galeri Desain Baju":

    st.subheader("🖼️ Galeri Desain Baju")

    with get_connection() as conn:

        query = """
            SELECT
                p.id,
                pl.nama,
                p.jenis_pakaian,
                p.deskripsi_pesanan,
                p.tgl_deadline,
                p.status,
                p.foto_desain,
                pl.lingkar_dada,
                pl.lingkar_pinggang,
                pl.panjang_lengan,
                pl.lebar_bahu
            FROM pesanan p
            JOIN pelanggan pl
                ON p.pelanggan_id = pl.id
            WHERE p.foto_desain IS NOT NULL
              AND p.foto_desain != ''
            ORDER BY p.id DESC
        """

        df_galeri = pd.read_sql_query(query, conn)

    if df_galeri.empty:
        st.info(
            "Belum ada foto desain baju yang diunggah."
        )
    else:

        cols = st.columns(3)

        for index, row in df_galeri.iterrows():

            with cols[index % 3]:

                with st.container(border=True):

                    file_path = UPLOAD_DIR / str(
                        row["foto_desain"]
                    )

                    if file_path.exists():

                        try:
                            image = Image.open(file_path)

                            st.image(
                                image,
                                use_container_width=True,
                                caption=f"Desain Pesanan #{row['id']}"
                            )

                        except Exception:
                            st.error(
                                "Gambar tidak dapat dibuka."
                            )

                    else:
                        st.warning(
                            "File gambar tidak ditemukan."
                        )

                    st.markdown(
                        f"**Pelanggan:** {row['nama']}"
                    )

                    st.markdown(
                        f"**Jenis:** {row['jenis_pakaian']}"
                    )

                    description = row["deskripsi_pesanan"]

                    if pd.notna(description) and str(description).strip():
                        st.markdown(
                            f"**Deskripsi:** {description}"
                        )

                    st.markdown(
                        f"**Status:** `{row['status']}`"
                    )

                    st.markdown(
                        f"**Deadline:** {row['tgl_deadline']}"
                    )

                    with st.expander("📏 Detail Ukuran"):

                        st.write(
                            f"**Lingkar Dada:** "
                            f"{row['lingkar_dada']} cm"
                        )

                        st.write(
                            f"**Lingkar Pinggang:** "
                            f"{row['lingkar_pinggang']} cm"
                        )

                        st.write(
                            f"**Panjang Lengan:** "
                            f"{row['panjang_lengan']} cm"
                        )

                        st.write(
                            f"**Lebar Bahu:** "
                            f"{row['lebar_bahu']} cm"
                        )


# ============================================================
# KONSULTASI & KATALOG
# ============================================================

elif menu == "✨ Konsultasi & Foto Katalog":

    st.subheader(
        "🖼️ Referensi Foto Katalog & Panduan Penjahitan"
    )

    st.info(
        "Pilih kriteria busana untuk menampilkan "
        "referensi dan rekomendasi teknis."
    )

    col1, col2 = st.columns(2)

    with col1:

        kategori_pakaian = st.selectbox(
            "Jenis Busana",
            [
                "Gaun Bridesmaid / Pesta",
                "Kebaya Modern / Wisuda",
                "Kemeja Motif / Batik Pria",
                "Jas Formal / Blazer",
            ]
        )

        warna_bahan = st.selectbox(
            "Pilihan Warna Utama",
            [
                "Sage Green / Hijau Soft",
                "Navy / Biru Dongker",
                "Maroon / Merah Tua",
                "Rosegold / Dusty Pink",
            ]
        )

    with col2:

        gaya_potongan = st.selectbox(
            "Gaya / Model Potongan",
            [
                "A-Line Dress",
                "Slim Fit",
                "Lengan Balon / Puff",
                "Mermaid Style",
            ]
        )

        detail_desain = st.text_area(
            "Detail Dekorasi",
            "Aksen payet mutiara di bagian kerah dan dada, "
            "pemotongan V-neck."
        )

    if st.button(
        "🔍 Tampilkan Foto Referensi",
        type="primary"
    ):

        st.divider()

        st.markdown(
            f"### 📋 Panduan Teknis "
            f"({kategori_pakaian})"
        )

        st.markdown(
            f"""
            - **Model Cut:** {gaya_potongan}
            - **Warna:** {warna_bahan}
            - **Rekomendasi Kain:** Satin Velvet Premium, Silk Organza, atau Brokat Tulle
            - **Jarum:** Microtex 70/10 - 80/12 untuk kain halus
            - **Finishing Kampuh:** French Seam atau obras 4 benang
            - **Aplikasi:** {detail_desain}
            """
        )

        st.divider()

        st.markdown(
            "### 📸 Foto Referensi Multi-Sudut"
        )

        catalog_database = {

            "Gaun Bridesmaid / Pesta": {
                "depan":
                    "https://images.unsplash.com/photo-1566174053879-31528523f8ae?auto=format&fit=crop&w=800&q=80",
                "samping":
                    "https://images.unsplash.com/photo-1515372039744-b8f02a3ae446?auto=format&fit=crop&w=800&q=80",
                "belakang":
                    "https://images.unsplash.com/photo-1496747611176-843222e1e57c?auto=format&fit=crop&w=800&q=80"
            },

            "Kebaya Modern / Wisuda": {
                "depan":
                    "https://images.unsplash.com/photo-1610030469983-98e550d6193c?auto=format&fit=crop&w=800&q=80",
                "samping":
                    "https://images.unsplash.com/photo-1583391733956-3750e0ff4e8b?auto=format&fit=crop&w=800&q=80",
                "belakang":
                    "https://images.unsplash.com/photo-1572804013309-59a88b7e92f1?auto=format&fit=crop&w=800&q=80"
            },

            "Kemeja Motif / Batik Pria": {
                "depan":
                    "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?auto=format&fit=crop&w=800&q=80",
                "samping":
                    "https://images.unsplash.com/photo-1598033129183-c4f50c736f10?auto=format&fit=crop&w=800&q=80",
                "belakang":
                    "https://images.unsplash.com/photo-1603252109303-2751441dd157?auto=format&fit=crop&w=800&q=80"
            },

            "Jas Formal / Blazer": {
                "depan":
                    "https://images.unsplash.com/photo-1594938298603-c8148c4dae35?auto=format&fit=crop&w=800&q=80",
                "samping":
                    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=800&q=80",
                "belakang":
                    "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?auto=format&fit=crop&w=800&q=80"
            }
        }

        photos = catalog_database[kategori_pakaian]

        tab1, tab2, tab3 = st.tabs(
            [
                "📸 Tampak Depan",
                "📸 Tampak Samping",
                "📸 Tampak Belakang"
            ]
        )

        with tab1:
            st.image(
                photos["depan"],
                caption=f"Tampak Depan - {kategori_pakaian}",
                use_container_width=True
            )

        with tab2:
            st.image(
                photos["samping"],
                caption=f"Tampak Samping - {kategori_pakaian}",
                use_container_width=True
            )

        with tab3:
            st.image(
                photos["belakang"],
                caption=f"Tampak Belakang - {kategori_pakaian}",
                use_container_width=True
            )


# ============================================================
# TAMBAH PELANGGAN
# ============================================================

elif menu == "Tambah Pelanggan & Ukuran":

    st.subheader("👤 Tambah Pelanggan & Ukuran")

    with st.form("form_pelanggan"):

        col1, col2 = st.columns(2)

        with col1:

            nama = st.text_input(
                "Nama Lengkap *"
            )

            telepon = st.text_input(
                "Nomor Telepon / WhatsApp *"
            )

            lingkar_dada = st.number_input(
                "Lingkar Dada (cm)",
                min_value=0.0,
                max_value=300.0,
                value=0.0,
                step=0.5
            )

            lingkar_pinggang = st.number_input(
                "Lingkar Pinggang (cm)",
                min_value=0.0,
                max_value=300.0,
                value=0.0,
                step=0.5
            )

        with col2:

            panjang_lengan = st.number_input(
                "Panjang Lengan (cm)",
                min_value=0.0,
                max_value=200.0,
                value=0.0,
                step=0.5
            )

            lebar_bahu = st.number_input(
                "Lebar Bahu (cm)",
                min_value=0.0,
                max_value=100.0,
                value=0.0,
                step=0.5
            )

            catatan = st.text_area(
                "Catatan Khusus Postur / Gaya"
            )

        submitted = st.form_submit_button(
            "💾 Simpan Data Pelanggan",
            use_container_width=True
        )

        if submitted:

            nama = nama.strip()
            telepon = telepon.strip()

            if not nama:
                st.error("Nama pelanggan wajib diisi.")

            elif not telepon:
                st.error(
                    "Nomor Telepon/WhatsApp wajib diisi."
                )

            else:

                with get_connection() as conn:

                    conn.execute(
                        """
                        INSERT INTO pelanggan (
                            nama,
                            telepon,
                            lingkar_dada,
                            lingkar_pinggang,
                            panjang_lengan,
                            lebar_bahu,
                            catatan
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            nama,
                            telepon,
                            lingkar_dada,
                            lingkar_pinggang,
                            panjang_lengan,
                            lebar_bahu,
                            catatan.strip()
                        )
                    )

                    conn.commit()

                st.success(
                    f"Data pelanggan **{nama}** berhasil disimpan."
                )


# ============================================================
# INPUT PESANAN
# ============================================================

elif menu == "Input Pesanan & Upload Desain":

    st.subheader(
        "🛍️ Input Pesanan Baru"
    )

    with get_connection() as conn:

        pelanggan_df = pd.read_sql_query(
            """
            SELECT id, nama, telepon
            FROM pelanggan
            ORDER BY nama ASC
            """,
            conn
        )

    if pelanggan_df.empty:

        st.warning(
            "Belum ada pelanggan. "
            "Tambahkan pelanggan terlebih dahulu."
        )

    else:

        pelanggan_dict = {
            f"{row['nama']} ({row['telepon']})":
                int(row["id"])
            for _, row in pelanggan_df.iterrows()
        }

        selected_pelanggan = st.selectbox(
            "Pilih Pelanggan",
            list(pelanggan_dict.keys())
        )

        pelanggan_id = pelanggan_dict[
            selected_pelanggan
        ]

        with st.form("form_pesanan"):

            col1, col2 = st.columns(2)

            with col1:

                jenis_pakaian = st.selectbox(
                    "Jenis Pakaian",
                    [
                        "Kemeja Pria",
                        "Gaun/Pesta",
                        "Celana Formal",
                        "Batik",
                        "Jas",
                        "Kebaya",
                        "Lainnya"
                    ]
                )

                deskripsi_pesanan = st.text_area(
                    "Deskripsi Pesanan",
                    placeholder=(
                        "Model, jenis kain, warna, "
                        "payet, bordir, ukuran khusus, dll."
                    )
                )

                tgl_terima = st.date_input(
                    "Tanggal Terima",
                    value=date.today()
                )

                tgl_deadline = st.date_input(
                    "Tanggal Deadline",
                    value=date.today()
                )

                uploaded_file = st.file_uploader(
                    "Upload Foto Desain / Pola",
                    type=["jpg", "jpeg", "png"],
                    help=f"Maksimal {MAX_UPLOAD_SIZE_MB} MB."
                )

            with col2:

                ongkos_jahit = st.number_input(
                    "Ongkos Jahit (Rp)",
                    min_value=0,
                    value=0,
                    step=10000
                )

                biaya_bahan = st.number_input(
                    "Biaya Bahan / Aksesoris (Rp)",
                    min_value=0,
                    value=0,
                    step=5000
                )

                dp = st.number_input(
                    "Uang Muka / DP (Rp)",
                    min_value=0,
                    value=0,
                    step=10000
                )

            total_biaya = (
                ongkos_jahit +
                biaya_bahan
            )

            sisa_bayar = total_biaya - dp

            st.divider()

            col_a, col_b = st.columns(2)

            with col_a:
                st.metric(
                    "Total Biaya",
                    format_rupiah(total_biaya)
                )

            with col_b:
                st.metric(
                    "Sisa Pembayaran",
                    format_rupiah(sisa_bayar)
                )

            submitted = st.form_submit_button(
                "💾 Simpan Pesanan",
                use_container_width=True
            )

            if submitted:

                # Validasi tanggal
                if tgl_deadline < tgl_terima:

                    st.error(
                        "Tanggal deadline tidak boleh "
                        "sebelum tanggal terima."
                    )

                # Validasi DP
                elif dp > total_biaya:

                    st.error(
                        "DP tidak boleh lebih besar "
                        "dari total biaya."
                    )

                else:

                    filename = ""

                    try:

                        # Simpan gambar
                        if uploaded_file is not None:
                            filename = save_uploaded_image(
                                uploaded_file
                            )

                        with get_connection() as conn:

                            conn.execute(
                                """
                                INSERT INTO pesanan (
                                    pelanggan_id,
                                    jenis_pakaian,
                                    deskripsi_pesanan,
                                    tgl_terima,
                                    tgl_deadline,
                                    status,
                                    total_biaya,
                                    dp,
                                    foto_desain
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    pelanggan_id,
                                    jenis_pakaian,
                                    deskripsi_pesanan.strip(),
                                    str(tgl_terima),
                                    str(tgl_deadline),
                                    "Diterima",
                                    total_biaya,
                                    dp,
                                    filename
                                )
                            )

                            conn.commit()

                        st.success(
                            "✅ Pesanan berhasil disimpan!"
                        )

                    except ValueError as error:

                        if filename:
                            delete_design_file(filename)

                        st.error(str(error))

                    except Exception as error:

                        if filename:
                            delete_design_file(filename)

                        st.error(
                            f"Gagal menyimpan pesanan: {error}"
                        )


# ============================================================
# DATA PELANGGAN
# ============================================================

elif menu == "Data Pelanggan":

    st.subheader(
        "📋 Data Pelanggan & Ukuran Body"
    )

    with get_connection() as conn:

        df_pelanggan = pd.read_sql_query(
            """
            SELECT *
            FROM pelanggan
            ORDER BY id DESC
            """,
            conn
        )

    if df_pelanggan.empty:

        st.info(
            "Belum ada data pelanggan."
        )

    else:

        st.dataframe(
            df_pelanggan,
            use_container_width=True,
            hide_index=True
        )

        st.divider()

        st.subheader("🗑️ Hapus Pelanggan")

        pelanggan_options = {
            f"{row['nama']} ({row['telepon']})":
                int(row["id"])
            for _, row in df_pelanggan.iterrows()
        }

        selected_delete = st.selectbox(
            "Pilih pelanggan yang akan dihapus",
            list(pelanggan_options.keys())
        )

        delete_id = pelanggan_options[
            selected_delete
        ]

        confirm_delete = st.checkbox(
            "Saya yakin ingin menghapus pelanggan ini "
            "beserta seluruh pesanan terkait."
        )

        if st.button(
            "🗑️ Hapus Pelanggan",
            type="secondary"
        ):

            if not confirm_delete:

                st.warning(
                    "Centang konfirmasi terlebih dahulu."
                )

            else:

                with get_connection() as conn:

                    cursor = conn.cursor()

                    # Ambil file desain sebelum pesanan dihapus
                    cursor.execute(
                        """
                        SELECT foto_desain
                        FROM pesanan
                        WHERE pelanggan_id = ?
                        """,
                        (delete_id,)
                    )

                    files = [
                        row[0]
                        for row in cursor.fetchall()
                        if row[0]
                    ]

                    cursor.execute(
                        """
                        DELETE FROM pelanggan
                        WHERE id = ?
                        """,
                        (delete_id,)
                    )

                    conn.commit()

                # Hapus file gambar
                for filename in files:
                    delete_design_file(filename)

                st.success(
                    "Data pelanggan dan pesanan terkait "
                    "berhasil dihapus."
                )

                st.rerun()