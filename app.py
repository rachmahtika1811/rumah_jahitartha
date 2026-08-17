# --- 5. MODUL: GENERATOR DESAIN GEMINI AI (WITH RETRY & FALLBACK) ---
elif menu == "✨ Generator Desain Gemini AI":
    st.subheader("✨ Konsultasi & Generator Desain Busana (Google Gemini AI)")
    st.info("💡 Dapatkan rekomendasi gaya busana, rincian potongan bahan, dan saran teknis penjahitan beserta GAMBAR VISUAL otomatis dari AI.")

    default_key = st.secrets.get("GEMINI_API_KEY", "")
    gemini_key = st.text_input("Masukkan Gemini API Key:", value=default_key, type="password", help="Dapatkan API Key gratis di aistudio.google.com")

    col1, col2 = st.columns(2)
    with col1:
        kategori_pakaian = st.selectbox("Jenis Busana", ["Gaun Bridesmaid / Pesta", "Kebaya Modern / Wisuda", "Kemeja Motif / Batik Pria", "Jas Formal / Blazer", "Baju Kurung / Abaya"])
        warna_bahan = st.text_input("Warna & Bahan Kain", "Sage Green, Bahan Satin Velvet")
    with col2:
        gaya_potongan = st.selectbox("Gaya / Model Potongan", ["A-Line Dress", "Slim Fit", "Lengan Balon / Puff", "Mermaid Style", "Modern Minimalist"])
        detail_desain = st.text_area("Detail Dekorasi / Aksesoris", "Payet mutiara di bagian dada dan kerah, potongan V-neck")

    if st.button("✨ Analisis & Dapatkan Rekomendasi Desain Gemini"):
        if not gemini_key:
            st.error("Silakan masukkan Gemini API Key terlebih dahulu.")
        else:
            with st.spinner("Gemini AI sedang merancang konsep, panduan penjahitan, dan gambar visual..."):
                try:
                    import time
                    from google import genai

                    client = genai.Client(api_key=gemini_key)
                    prompt_teks = f"""
                    Anda adalah asisten desainer tata busana profesional untuk penjahit 'Rumah Jahit Artha'.
                    Buatkan konsep desain rinci dan panduan teknis penjahitan untuk pesanan berikut:
                    - Jenis Busana: {kategori_pakaian}
                    - Warna & Bahan Kain: {warna_bahan}
                    - Model/Potongan: {gaya_potongan}
                    - Detail Aksesoris/Payet: {detail_desain}

                    Tolong berikan output terstruktur dalam Bahasa Indonesia yang mencakup:
                    1. Deskripsi Visual Konsep Busana
                    2. Saran Pemilihan Jenis Kain & Aksesoris Tambahan
                    3. Catatan Teknis Penjahitan & Pemotongan Pola (Penting untuk Penjahit)
                    """

                    # Daftar model yang digunakan (Urutan prioritas)
                    models_to_try = ['gemini-2.5-flash', 'gemini-3.6-flash']
                    response = None
                    last_error = None

                    # Percobaan pemanggilan dengan retry & fallback model
                    for model_name in models_to_try:
                        for attempt in range(2): # Coba 2 kali per model
                            try:
                                response = client.models.generate_content(
                                    model=model_name,
                                    contents=prompt_teks,
                                )
                                if response:
                                    break
                            except Exception as e:
                                last_error = e
                                time.sleep(1) # Tunggu 1 detik sebelum mencoba lagi
                        if response:
                            break

                    if response:
                        st.markdown("### 📋 Hasil Rekomendasi Desain & Panduan Penjahitan")
                        st.markdown(response.text)

                        # Pembuatan Gambar Visual Fotorealistis (Manekin Studio)
                        st.divider()
                        st.markdown("### 🖼️ Visualisasi Gambar Desain Baju (Katalog Studio)")
                        
                        prompt_gambar = (
                            f"Isolated studio product photography of a {kategori_pakaian} on a tailor dress form mannequin. "
                            f"Style: {gaya_potongan}. Fabric and Color: {warna_bahan}. Details: {detail_desain}. "
                            f"Clean neutral gray background, high-end fashion boutique display, "
                            f"no human, no person, no woman, no girl, no face, 8k resolution, photorealistic fabric texture, sharp focus on sewing stitches."
                        )
                        prompt_encoded = urllib.parse.quote(prompt_gambar)
                        image_url = f"https://image.pollinations.ai/prompt/{prompt_encoded}?width=800&height=800&nologo=true&model=flux"

                        st.image(image_url, caption=f"Foto Katalog Baju: {kategori_pakaian} ({gaya_potongan})", use_container_width=True)
                        st.success("Konsep desain dan foto produk baju berhasil dirancang!")
                    else:
                        st.error(f"Server Google AI sedang sangat padat (503). Silakan coba klik tombol kembali dalam beberapa detik. Detail: {last_error}")

                except Exception as e:
                    st.error(f"Gagal menghubungkan ke Gemini AI: {e}")