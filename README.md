# 🎮 NTE Sentiment Analyzer

Framework dashboard interaktif multi-halaman berbasis **Streamlit** untuk penelitian skripsi:
**"Analisis Sentimen Ulasan Game _Neverness to Everness_ dengan Algoritma Multinomial Naive Bayes + TF-IDF + SMOTE"**

Dashboard ini mengelola seluruh alur _pipeline_ Machine Learning secara end-to-end:
Scraping → Labeling → Preprocessing → TF-IDF → Split Data → SMOTE → Training → Evaluasi → Visualisasi → Pengujian Real-Time.

---

## 🛠️ Instalasi & Persiapan

Berikut beberapa cara untuk menyiapkan aplikasi ini secara lokal di komputer Anda.

### Prasyarat

- Python **3.10** atau yang lebih baru.
- `pip` (package manager Python).

---

### Opsi 1: Instalasi Menggunakan Virtual Environment (Recommended)

Cara ini menjaga dependensi agar terisolasi dan tidak bertabrakan dengan project Python lain.

1. **Clone repository:**

   ```bash
   git clone git@github.com:MomoPi-Dark/streamlit-learn.git
   cd streamlit-learn
   ```

2. **Buat virtual environment:**

   ```bash
   python3 -m venv .venv
   ```

3. **Aktifkan virtual environment:**
   - **Linux / macOS:**
     ```bash
     source .venv/bin/activate
     ```
   - **Windows (Command Prompt / PowerShell):**
     ```cmd
     .venv\Scripts\activate
     ```

4. **Install semua dependensi:**

   ```bash
   pip install -r requirements.txt
   ```

5. **Jalankan aplikasi:**

   ```bash
   streamlit run src/app.py
   ```

6. Akses dashboard di peramban web pada alamat `http://localhost:8501`.

---

### Opsi 2: Instalasi Langsung (Global)

Jika Anda ingin langsung menginstall ke sistem:

```bash
git clone git@github.com:MomoPi-Dark/streamlit-learn.git
cd streamlit-learn
pip install -r requirements.txt
streamlit run src/app.py
```

---

## ⚙️ Konfigurasi Environment

Aplikasi ini menggunakan **dotenv** untuk memuat konfigurasi lokal.

1. Buat file `.env.local` di direktori utama:

   ```bash
   touch .env.local
   ```

2. Isi variabel yang diperlukan (opsional):
   ```env
   APP_ID=com.hottagames.nte
   ```

---

## 🚀 Panduan Alur Pipeline

Setelah dashboard terbuka, jalankan setiap tahapan di menu sidebar secara berurutan:

1. **📥 Pengumpulan Dataset (`/app-dataset`)**:
   Ambil ulasan secara _live scraping_ dari Google Play Store atau unggah dataset CSV.
2. **🏷️ Labeling Data (`/app-labeling`)**:
   Pelabelan sentimen otomatis berdasarkan rating bintang (4-5 Positif, 1-2 Negatif, 3 dibuang).
3. **🧹 Preprocessing Data (`/app-preprocessing`)**:
   Pembersihan teks (Case Folding, Cleaning, Normalisasi Slang, Stopword Removal, Stemming Sastrawi, Tokenizing).
4. **🧮 Pembobotan TF-IDF (`/app-tfidf`)**:
   Ekstraksi fitur teks menjadi representasi numerik matriks TF-IDF.
5. **✂️ Data Splitting (`/app-splitdata`)**:
   Pembagian data latih (80%) dan data uji (20%).
6. **⚖️ Penyeimbangan Kelas SMOTE (`/app-smoote`)**:
   Menyeimbangkan proporsi kelas Positif dan Negatif pada data latih.
7. **🤖 Training Naive Bayes (`/app-naifbayes`)**:
   Pelatihan model klasifikasi Multinomial Naive Bayes.
8. **📈 Evaluasi Model (`/app-evaluation`)**:
   Pengujian data uji untuk mendapatkan metrik Accuracy, Precision, Recall, F1-Score, dan Confusion Matrix.
9. **🖼️ Visualisasi (`/app-visualisasi`)**:
   Grafik visualisasi Top 20 kata dan WordCloud per kelas.
10. **🧪 Pengujian Real-Time (`/app-testing`)**:
    Uji coba inferensi real-time ulasan baru dari scraping live atau ketikan komentar manual.

---

## 📂 Struktur Direktori Proyek

```text
streamlit-learn/
├── public/                     # Artefak dataset, model, dan grafik
│   ├── csv/                    # Dataset mentah & hasil olahan
│   ├── tfidf/                  # Matriks & vectorizer TF-IDF
│   ├── split/                  # Hasil train-test split
│   ├── smote/                  # Data latih hasil SMOTE
│   ├── model/                  # File model Naive Bayes (.pkl)
│   ├── evaluation/             # Hasil metrik evaluasi (.json)
│   └── images/                 # Gambar WordCloud dan chart
├── src/
│   ├── app.py                  # Entry point utama aplikasi & layout sidebar
│   ├── structures/
│   │   └── base.py             # BasePage class & dekorator @Options
│   ├── lib/
│   │   ├── loader.py           # Dynamic page discovery
│   │   ├── enum.py             # Session state & stage keys
│   │   ├── bgManager.py        # Background task manager
│   │   ├── nlp.py              # Fungsi pemrosesan teks Sastrawi
│   │   └── slang.py            # Kamus normalisasi kata slang
│   └── app_pages/
│       └── app/                # Modul halaman tahapan penelitian
└── requirements.txt            # Daftar pustaka Python
```

---

## 🐛 Troubleshooting

- **Port bentrok / sudah terpakai**:
  Jalankan aplikasi di port yang berbeda:
  ```bash
  streamlit run src/app.py --server.port 8502
  ```
- **Error scraping Google Play Store**:
  Google Play membatasi frekuensi request. Tunggu beberapa saat, lalu jalankan kembali scraping dengan jumlah ulasan bertahap.
