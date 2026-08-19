# Streamlit Design System

Dokumen ini mendefinisikan aturan dan komponen untuk membangun antarmuka yang konsisten dan berkualitas tinggi dengan Streamlit.

## 1. Schema Aturan dari Streamlit

Schema aturan Streamlit adalah fondasi dari sistem desain ini. Ini mendefinisikan properti (props), perilaku interaktif, manajemen state, serta validasi yang dapat diterima untuk setiap komponen. Tujuannya adalah memastikan semua elemen UI dapat diprediksi, dapat diakses, dan mudah digunakan.

- **Definisi Komponen**: Setiap komponen didefinisikan dengan properti yang jelas, termasuk tipe data dan nilai default.
- **Perilaku**: Perilaku interaktif (mis. `onClick`, `onValueChange`) ditentukan untuk memastikan konsistensi.
- **State Management**: Aturan untuk mengelola status internal komponen (mis. `disabled`, `loading`, `error`).
- **Validasi**: Schema secara otomatis memvalidasi konfigurasi komponen untuk mencegah kesalahan saat runtime.

## 2. Sections

### 2.1. Overview

Sistem desain ini bertujuan memberikan panduan dan aset yang dapat dipakai kembali untuk mempercepat pengembangan aplikasi Streamlit. Dengan mengikuti panduan ini, kita dapat menciptakan pengalaman pengguna yang kohesif di seluruh produk.

### 2.2. Colors

Warna adalah elemen kunci dalam identitas visual. Gunakan palet berikut secara konsisten.

- **Primary**: `#FF4B4B` (Gunakan untuk tombol utama, tautan, dan elemen interaktif penting).
- **Secondary**: `#F0F2F6` (Warna latar belakang sidebar dan elemen sekunder).
- **Background**: `#FFFFFF` (Latar belakang utama aplikasi).
- **Text**: `#31333F` (Warna teks utama untuk keterbacaan).
- **Success**: `#28A745` (Notifikasi berhasil).
- **Warning**: `#FFC107` (Peringatan atau notifikasi penting).
- **Error**: `#DC3545` (Pesan kesalahan).

### 2.3. Typografi

Tipografi yang konsisten meningkatkan keterbacaan dan hierarki visual.

- **Font Family**: `Source Sans Pro`, `sans-serif`.
- **Heading 1 (`st.title`)**: 3rem, **Bold**.
- **Heading 2 (`st.header`)**: 2.25rem, **Semi-bold**.
- **Heading 3 (`st.subheader`)**: 1.75rem, **Semi-bold**.
- **Body (`st.write`, `st.markdown`)**: 1rem, **Regular**.
- **Caption (`st.caption`)**: 0.875rem, **Regular**, Opacity 70%.

### 2.4. Layout

Struktur tata letak menentukan bagaimana konten diatur di layar.

- **Max Width**: 1200 px untuk konten utama di layar lebar.
- **Columns (`st.columns`)**: Gunakan kolom untuk mengatur konten secara berdampingan. Jaga agar jumlah kolom tetap sederhana (2-3) untuk keterbacaan di perangkat seluler.
- **Container (`st.container`)**: Gunakan untuk mengelompokkan elemen terkait secara logis.
- **Sidebar**: Lebar default 304 px. Gunakan untuk navigasi utama dan filter global.

### 2.5. Elevation dan Depth

Gunakan bayangan (shadow) secara halus untuk menciptakan hierarki visual dan membedakan elemen interaktif.

- **Level 1 (Cards, Containers)**: `box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);`
- **Level 2 (Modals, Pop-ups)**: `box-shadow: 0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23);`

### 2.6. Shapes

Bentuk komponen harus konsisten untuk menciptakan tampilan yang bersih.

- **Border Radius**: 4 px untuk semua komponen interaktif seperti tombol, input, dan kartu.
- **Borders**: Gunakan border `1px solid #E6E6E6` untuk memisahkan elemen atau pada input field.

### 2.7. Components

Berikut adalah panduan untuk komponen Streamlit yang umum digunakan.

- **`st.button`**
  - Tombol utama harus menggunakan `type="primary"`.
  - Tombol sekunder menggunakan `type="secondary"` (default).
- **`st.text_input`**
  - Selalu sertakan `label` yang jelas.
  - Gunakan `placeholder` untuk memberikan contoh input.
- **`st.selectbox`**
  - Ideal untuk daftar pilihan antara 3 hingga 15 item.
  - Jika lebih dari itu, pertimbangkan untuk menggunakan `st.multiselect` atau pencarian.
- **`st.data_editor`**
  - Gunakan untuk menampilkan dan mengedit data tabular.
  - Pastikan untuk menonaktifkan kolom yang tidak boleh diedit.

### 2.8. Do's and Don'ts

#### Do's (Lakukan)

- **Gunakan Cache**: Manfaatkan `st.cache_data` dan `st.cache_resource` untuk mempercepat aplikasi.
- **Jaga Kesederhanaan**: Fokus pada alur kerja pengguna yang jelas dan minimalis.
- **Gunakan Label yang Jelas**: Pastikan setiap input memiliki label yang deskriptif.
- **Responsif**: Uji aplikasi Anda di berbagai ukuran layar.

#### Don'ts (Jangan Lakukan)

- **Terlalu Banyak Widget**: Hindari membanjiri layar dengan terlalu banyak input atau kontrol.
- **Mengabaikan State**: Jangan lupa mengelola state aplikasi, terutama pada aplikasi multi-halaman.
- **Warna Berlebihan**: Jangan gunakan terlalu banyak warna yang tidak perlu. Tetap berpegang pada palet yang ditentukan.
- **Teks Panjang Tanpa Format**: Pecah teks panjang menjadi beberapa paragraf, gunakan `st.header` atau `st.subheader`.
