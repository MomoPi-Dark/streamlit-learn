# AGENT.md — Guidelines for AI Coding Agents

Dokumen panduan arsitektur, standar pengembangan, dan instruksi kerja AI Agent / Developer dalam mengelola dan mengembangakan aplikasi web **Streamlit** untuk Skripsi Analisis Sentimen Game _Neverness to Everness_ (NTE).

---

## 📌 1. Ikhtisar Proyek & Context

- **Judul Penelitian**: Analisis Sentimen Review Game _Neverness to Everness_ (NTE) Menggunakan Algoritma Multinomial Naive Bayes + TF-IDF + SMOTE.
- **Tujuan Aplikasi**: Menyediakan _framework dashboard_ interaktif multi-halaman yang mengelola seluruh alur _pipeline_ Machine Learning (scraping, labeling, preprocessing, TF-IDF, train-test split, SMOTE, training model, evaluasi, hingga visualisasi dan pengujian _real-time_).
- **Tech Stack**:
  - **Framework**: Streamlit (>= 1.31) menggunakan `st.Page` & `st.navigation`.
  - **Language**: Python 3.10+
  - **ML/NLP Stack**: `scikit-learn` (`MultinomialNB`, `TfidfVectorizer`), `imbalanced-learn` (`SMOTE`), `Sastrawi`, `NLTK`, `pandas`, `numpy`, `google-play-scraper`.

---

## 📁 2. Struktur Direktori Proyek

Aplikasi menerapkan arsitektur **Zero-Hardcode Dynamic Router**. Seluruh halaman dimuat secara dinamis dari memori berdasarkan folder `src/app_pages`.

```text
streamlit-learn/
├── .streamlit/
│   └── config.toml          # Konfigurasi tema dan server Streamlit
├── docs/                     # Dokumen pendukung / riset
├── public/                   # Asset publik (gambar, icon, static file)
├── src/
│   ├── app.py                # Main Entrypoint (Router, Sidebar CSS, Navigation)
│   ├── app_pages/            # Halaman-halaman aplikasi (Dynamic Module Discovery)
│   │   └── app/
│   │       ├── dataset/
│   │       │   ├── slang/
│   │       │   │   └── page.py
│   │       │   └── page.py   # Page: Pengumpulan Dataset
│   │       ├── evaluation/
│   │       │   └── page.py   # Page: Evaluasi Model
│   │       ├── labeling/
│   │       │   └── page.py   # Page: Pelabelan Data
│   │       ├── naifbayes/
│   │       │   └── page.py   # Page: Training Model Naive Bayes
│   │       ├── preprocessing/
│   │       │   └── page.py   # Page: Preprocessing Teks
│   │       ├── smoote/
│   │       │   └── page.py   # Page: Penyeimbangan SMOTE
│   │       ├── splitdata/
│   │       │   └── page.py   # Page: Split Data Latih/Uji
│   │       ├── tfidf/
│   │       │   └── page.py   # Page: Pembobotan TF-IDF
│   │       ├── visualisasi/
│   │       │   └── page.py   # Page: Visualisasi & Insights
│   │       └── page.py       # Halaman Utama / Overview
│   ├── lib/                  # Helper utilities, Enums, & Configurations
│   │   ├── category_config.py# Konfigurasi grup/kategori halaman & validator state
│   │   ├── enum.py           # StateKey, StageKey, & State Loaders
│   │   ├── loader.py         # Module Loader Strategy
│   │   └── running_badge.py  # Status indicator helpers
│   ├── stopwords/            # File stopword khusus & dictionary
│   └── structures/
│       └── base.py           # BasePage ABC, PageMetadata, & Decorator @Options
├── .env.local                # Local environment variables
├── .gitignore
├── AGENT.md                  # Panduan AI Agent (Dokumen ini)
├── DESIGN.md                 # UI/UX & Design Guidelines
└── requirements.txt          # Python dependencies
```

---

## 🏛️ 3. Arsitektur Dynamic Router & Base System

Sistem routing menggunakan **Decorated OOP Pattern**. Setiap halaman didefinisikan sebagai _Class_ yang mewarisi `BasePage` dan dihiasi oleh dekorator `@Options`.

### 3.1 Cetak Biru Kelas Base (`src/structures/base.py`)

Lihat implementasi di [`base.py`](src/structures/base.py)

### 3.2 Siklus Hidup Halaman (Page Lifecycle)

| Method       | Trigger Exec                                                               | Peruntukan                                                                | Ketentuan                                                                       |
| :----------- | :------------------------------------------------------------------------- | :------------------------------------------------------------------------ | :------------------------------------------------------------------------------ |
| `on_start()` | **Semua** halaman aktif/non-aktif pada **setiap** rerun Streamlit.         | Inisialisasi default `st.session_state`, verifikasi kunci ringan.         | **DILARANG** meletakkan I/O berat, query database, atau training model di sini! |
| `on_load()`  | **Hanya** halaman yang sedang aktif, dieksekusi **SEKALI** (lazy loading). | Loading `.pkl` model, vectorizer, dataset besar ke cache RAM.             | Sangat disarankan dibungkus bersama `@st.cache_resource` atau `@st.cache_data`. |
| `run()`      | Dieksekusi setiap rerun untuk halaman yang sedang terbuka.                 | UI Streamlit (`st.title`, `st.dataframe`, `st.button`, interaksi widget). | Logika tampilan utama dan handler event tombol.                                 |
| `__call__()` | Dipanggil oleh `st.Page` runner.                                           | Adapter otomatis untuk menjamin `on_load()` dipanggil sebelum `run()`.    | Jangan di-override kecuali ada kebutuhan sistem khusus.                         |

---

## 🔄 4. Mekanisme Dynamic Loader (`src/lib/loader.py`)

`PageLoader` bertugas memindai berkas `.py` dalam `src/app_pages`, merender dan mengompilasi skrip ke memori scope virtual secara aman, serta mengekstrak kelas turunan `BasePage`.

- **Metode Sorting**: Memastikan file root di-load lebih dahulu sebelum sub-folder/kategori.
- **Auto Meta Binding**: Mengikat atribut absolut `__page_file__` ke kelas untuk kalkulasi slug URL otomatis.
- **No Static Imports**: `app.py` tidak meng-import file halaman satu per satu. Halaman baru yang dibuat di `src/app_pages/` dengan dekorator `@Options` akan otomatis muncul di navigasi.

## 🎨 4a. Dynamic Stylesheet Loader (`style.css`)

Aplikasi memuat CSS secara dinamis (bukan inline hardcoded di `app.py`) agar styling tetap terpisah dari logic dan mudah dikelola AI Agent tanpa merusak Python code.

### Mekanisme

- File [`style.css`](.streamlit/style.css) dibaca saat runtime dan di-inject ke halaman via `st.markdown(..., unsafe_allow_html=True)`.
- Loader melakukan caching (`@st.cache_data` atau read-once di module scope) agar tidak membaca file berulang kali setiap rerun.
- Selector utama yang WAJIB dijaga konsistensinya:
  - `[data-testid="stSidebar"]` — layout sidebar & navigasi
  - `[data-testid="stAppViewContainer"]` — container utama
  - `.stButton > button` — styling tombol custom

### Aturan untuk AI Agent

1. **JANGAN** menambahkan `<style>` inline baru di dalam `page.py` manapun. Semua styling global harus masuk ke `style.css` agar tidak terpecah dan sulit di-maintain.
2. **JANGAN** mengubah selector `data-testid` Streamlit tanpa memverifikasi versi Streamlit yang dipakai (`>= 1.31`) — selector ini bisa berubah antar versi.
3. Jika menambah komponen baru yang butuh style khusus, gunakan class custom (`.nte-*` prefix) di `style.css`, lalu terapkan via `st.markdown('<div class="nte-...">', unsafe_allow_html=True)` di halaman terkait — bukan inline style.
4. Perubahan pada `style.css` **tidak memerlukan restart** Streamlit jika loader menggunakan `@st.cache_data` dengan file-hash invalidation; namun jika loader cache di module-level tanpa hash check, restart manual diperlukan.

---

## 🚦 5. Pipeline Stages, Session State, & Routing Rules

Aplikasi ini mengontrol alur pemrosesan data skripsi menggunakan **Stage Guard**.

### 5.1 Daftar Stage Pipeline (`StageKey`)

1. **Stage 1**: Pengumpulan Data (`/app-dataset`)
2. **Stage 2**: Pelabelan Data (`/app-labeling`)
3. **Stage 3**: Preprocessing (`/app-preprocessing`)
4. **Stage 4**: Pembobotan TF-IDF (`/app-tfidf`)
5. **Stage 5**: Train-Test Split (`/app-splitdata`)
6. **Stage 6**: Penyeimbangan Kelas SMOTE (`/app-smoote`)
7. **Stage 7**: Training Model Naive Bayes (`/app-naifbayes`)
8. **Stage 8**: Evaluasi Model (`/app-evaluation`)
9. **Stage 9**: Visualisasi & Insights (`/app-visualisasi`)

### 5.2 Aturan Visibilitas Halaman (`is_page_visible`)

1. Jika `__page_meta__.enabled == False`, halaman tersembunyi.
2. Jika halaman memiliki `category`, sistem akan memeriksa `CATEGORY_CONFIG[category]`.
3. Fungsi `validator(session_state, page)` di `CATEGORY_CONFIG` akan memeriksa apakah _stage_ prasyarat di `st.session_state` sudah terpenuhi. Jika belum, halaman tidak akan ditampilkan di sidebar menu.

### 5.3 Konvensi URL Path Slug (`build_url_path`)

- `app_pages/page.py` $
ightarrow$ `/` (Root page)
- `app_pages/app/dataset/page.py` $
ightarrow$ `/app-dataset`
- `app_pages/app/preprocessing/page.py` $
ightarrow$ `/app-preprocessing`

---

## 📝 6. Panduan Membuat Halaman Baru (Step-by-Step)

Ketika AI Agent atau Developer diminta menambahkan modul/halaman baru, ikuti panduan berikut:

### Langkah 1: Buat berkas `.py` di direktori yang sesuai

Contoh: `src/app_pages/app/testing/page.py`

### Langkah 2: Tuliskan struktur kelas berbasis `@Options` dan `BasePage`

```python
import streamlit as st
from structures.base import BasePage, Options
from lib.enum import StateKey, StageKey, get_session_state


@Options(
    page_name="testing_page",
    menu_name="Testing Real-Time",
    menu_icon="🧪",
    requires_model=True,
    enabled=True,
    category="app",
)
class TestingPage(BasePage):
    def on_start(self) -> None:
        # Inisialisasi default session state jika diperlukan
        if "test_history" not in st.session_state:
            st.session_state["test_history"] = []

    def on_load(self) -> None:
        # Loading heavy resources (misal model pkl jika belum ada di state)
        pass

    def run(self) -> None:
        st.title("🧪 Uji Coba Real-Time Klasifikasi Sentimen")
        st.write("Masukkan ulasan teks game NTE untuk diuji secara langsung.")

        # Ambil model & vectorizer dari session_state / cache
        model = st.session_state.get(StateKey.MODEL)
        vectorizer = st.session_state.get(StateKey.VECTORIZER)

        if not model or not vectorizer:
            st.warning("⚠️ Model belum siap. Silakan selesaikan Stage 7 (Training Model) terlebih dahulu.")
            st.stop()

        user_input = st.text_area("Teks Ulasan:")
        if st.button("Uji Prediksi", type="primary"):
            if user_input.strip():
                # Process & predict
                vec = vectorizer.transform([user_input])
                pred = model.predict(vec)[0]
                prob = model.predict_proba(vec)

                if pred == "Positif":
                    st.success(f"Hasil Prediksi: **POSITIF** (Kepercayaan: {prob.max():.2%})")
                else:
                    st.error(f"Hasil Prediksi: **NEGATIF** (Kepercayaan: {prob.max():.2%})")
            else:
                st.warning("Mohon isi teks ulasan terlebih dahulu.")
```

---

## 🛠️ 7. Best Practices & Rules untuk AI Agent

1. **JANGAN LAKUKAN IMPORT HARCODE DI `app.py`**:
   - Dilarang menambahkan `import app_pages.xxx` secara manual di `app.py`. Biarkan `PageLoader` bekerja secara otomatis.
2. **GUNAKAN `StateKey` & `StageKey` ENUM**:
   - Hindari menggunakan string mentah seperti `st.session_state["model_ready"]`.
   - Selalu gunakan `StateKey.MODEL` atau `StageKey.STAGE_7` untuk konsistensi type-safety dan pemeliharaan.
3. **PISAHKAN PROSES HEAVY I/O KE `on_load()`**:
   - Pembacaan CSV besar, pemanggilan `joblib.load()`, atau ekstraksi TF-IDF berat wajib ditempatkan di `on_load()` atau dibungkus `@st.cache_resource` / `@st.cache_data`.
4. **JANGAN MERUSAK STYLING SIDEBAR CSS**:
   - Sidebar menggunakan custom CSS di `app.py` untuk konsistensi layout dashboard. Jika mengubah kelas CSS, pastikan selektor `[data-testid="stSidebar"]` tidak merusak `st.page_link`.
5. **KEAMANAN EXECUTABLE CODE (`PageLoader`)**:
   - `PageLoader` menggunakan `compile()` dan `exec()` untuk dinamisme RAM loading. Pastikan file dalam folder `app_pages/` terbebas dari _untrusted external input_.
