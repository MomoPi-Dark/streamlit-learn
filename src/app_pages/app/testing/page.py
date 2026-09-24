import streamlit as st
import pandas as pd
import joblib
import re
import html
from datetime import datetime
from google_play_scraper import reviews, Sort

from structures.base import BasePage, Options
from lib.paths import (
    MODEL_PATH,
    TFIDF_VECTORIZER_PATH,
    SLANG_CSV_PATH,
)
from lib.enum import StageKey, get_session_state
from lib.translate import translate_series
from lib.slang import load_unified_slang_dict
from lib.nlp import clean_text_base, get_stopword_remover, get_stemmer


# Inisialisasi Preprocessing Component Cache (reuse shared singletons)
@st.cache_resource
def load_sastrawi_components():
    return get_stopword_remover(), get_stemmer()


def clean_text(text: str) -> str:
    return clean_text_base(text)


def preprocess_live(text: str, slang_dict, stopword_remover, stemmer) -> str:
    text = clean_text(text)
    text = " ".join(slang_dict.get(w, w) for w in text.split())
    text = stopword_remover.remove(text)
    text = " ".join(stemmer.stem(w) for w in text.split())
    return " ".join(t for t in text.split() if len(t) > 2)


@Options(
    page_id="testing",
    menu_name="Pengujian Real-Time",
    menu_icon="🧪",
    category="modeling",
)
class AppPage(BasePage):
    def on_start(self) -> None:
        # initialize session state for both tabs
        if "test_app_id" not in st.session_state:
            st.session_state.test_app_id = "com.hottagames.nte"
        if "test_num_reviews" not in st.session_state:
            st.session_state.test_num_reviews = 20
        if "test_manual_text_val" not in st.session_state:
            st.session_state.test_manual_text_val = ""
        if "test_manual_result" not in st.session_state:
            st.session_state.test_manual_result = None

    def run(self) -> None:
        st.title("🧪 Pengujian Model (Real-time Scraping)")

        st.write(
            "Melakukan scraping ulasan terbaru secara live dari Google Play Store, "
            "lalu menguji prediksi sentimen positif/negatif menggunakan model Naive Bayes yang telah dilatih."
        )

        # Validasi ketersediaan model & vectorizer
        if not MODEL_PATH.exists() or not TFIDF_VECTORIZER_PATH.exists():
            st.warning(
                "### ⚠️ Model atau Vectorizer Belum Tersedia\n\n"
                "Model Multinomial Naive Bayes dan pembobotan TF-IDF harus dilatih dan diselesaikan terlebih dahulu "
                "pada tahap **7. Training Model**."
            )
            st.stop()

        # -------------------------------------------------
        # 1️⃣ Tab UI – dua pilihan
        tab_scrape, tab_manual = st.tabs(
            ["📥 Ambil dari Scraping", "✍️ Ketik Komentar Sendiri"]
        )
        # -------------------------------------------------
        # 📥 Tab Scraping – kode lama dipertahankan
        with tab_scrape:
            # Input Parameter Scraping
            app_id_input = st.text_input(
                "Google Play App ID",
                value="com.hottagames.nte",
                help="Masukkan ID Aplikasi di Google Play Store yang ingin di-scrape.",
            )

            col1, col2 = st.columns(2)
            with col1:
                num_reviews = st.number_input(
                    "Jumlah Ulasan",
                    min_value=5,
                    value=20,
                    step=5,
                    help="Jumlah ulasan terbaru yang akan ditarik secara live.",
                )
            with col2:
                sort_order = st.selectbox(
                    "Urutkan Berdasarkan",
                    options=["Terbaru", "Paling Membantu"],
                    index=0,
                )

            st.markdown("---")

            # Load Model & Vectorizer sekali saat run
            try:
                model = joblib.load(MODEL_PATH)
                vectorizer = joblib.load(TFIDF_VECTORIZER_PATH)
            except Exception as e:
                st.error(f"Gagal memuat file model/vectorizer: {e}")
                st.stop()

            trigger_scrape = st.button(
                "🚀 Ambil & Prediksi Review Baru", type="primary", width="stretch"
            )

            if trigger_scrape:
                sort_val = (
                    Sort.NEWEST if sort_order == "Terbaru" else Sort.MOST_RELEVANT
                )

                with st.spinner("Mengunduh ulasan dari Google Play Store..."):
                    try:
                        result, _ = reviews(
                            app_id_input,
                            lang="id",
                            country="id",
                            sort=sort_val,
                            count=num_reviews,
                        )
                    except Exception as e:
                        st.error(f"Gagal melakukan scraping: {e}")
                        st.stop()

                if not result:
                    st.warning(
                        "Tidak ada ulasan yang ditemukan atau ID Aplikasi salah."
                    )
                    st.stop()

                st.success(f"Berhasil menarik {len(result)} ulasan terbaru!")

                # Parsing to Dataframe
                scraped_data = []
                for r in result:
                    scraped_data.append(
                        {
                            "Nama": r.get("userName", "Tanpa Nama"),
                            "Ulasan Asli": r.get("content", ""),
                            "Waktu": r.get("at", datetime.now()).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )

                df_scraped = pd.DataFrame(scraped_data)

                # Translate semua review ke Bahasa Indonesia sebelum ditampilkan/prediksi.
                with st.spinner("Menerjemahkan semua ulasan ke Bahasa Indonesia..."):
                    translated_series, translate_stats = translate_series(
                        df_scraped["Ulasan Asli"],
                        source="auto",
                        target="id",
                        only_detected_source=False,
                        delay=0.05,
                    )
                    df_scraped["Ulasan Asli"] = translated_series

                st.info(
                    f"✅ Translate selesai: {translate_stats['translated']} diterjemahkan, "
                    f"{translate_stats['failed']} gagal."
                )

                # Inisialisasi library preprocessing Sastrawi (cached)
                stopword_remover, stemmer = load_sastrawi_components()
                slang_dictionary = load_unified_slang_dict()

                # Predictions
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                predictions = []
                confidences = []

                for i, row in enumerate(df_scraped.itertuples()):
                    status_text.text(
                        f"Memproses dan melakukan Preprocessing ulasan {i + 1} dari {len(df_scraped)}..."
                    )
                    progress_bar.progress((i + 1) / len(df_scraped))

                    text_to_preprocess = getattr(row, "_2", "")  # Ulasan Asli
                    if not isinstance(text_to_preprocess, str):
                        text_to_preprocess = str(text_to_preprocess)

                    cleaned_text = preprocess_live(
                        text_to_preprocess, slang_dictionary, stopword_remover, stemmer
                    )

                    tfidf_vec = vectorizer.transform([cleaned_text])
                    pred_label = model.predict(tfidf_vec)[0]

                    try:
                        proba = model.predict_proba(tfidf_vec)[0]
                        pos_idx = (
                            list(model.classes_).index("Positif")
                            if "Positif" in model.classes_
                            else 1
                        )
                        conf = (
                            proba[pos_idx]
                            if pred_label == "Positif"
                            else proba[1 - pos_idx]
                        )
                        conf_str = f"{conf * 100:.1f}%"
                    except Exception:
                        conf_str = "N/A"

                    predictions.append(pred_label)
                    confidences.append(conf_str)

                progress_bar.empty()
                status_text.empty()

                df_scraped["sentimen_label"] = predictions
                df_scraped["Confidence"] = confidences

                def style_sentiment(val):
                    color = "#dcfce7" if val == "Positif" else "#fee2e2"
                    text_color = "#166534" if val == "Positif" else "#991b1b"
                    return f"background-color: {color}; color: {text_color}; font-weight: bold;"

                df_styled = df_scraped.style.map(
                    style_sentiment, subset=["sentimen_label"]
                )

                st.markdown("### 📊 Tabel Hasil Klasifikasi")
                st.dataframe(df_styled, width="stretch")

                positive_count = sum(1 for p in predictions if p == "Positif")
                negative_count = len(predictions) - positive_count

                st.markdown("### 📈 Ringkasan Sentimen")
                c1, c2 = st.columns(2)
                c1.metric(
                    "Ulasan Positif",
                    f"{positive_count} ({positive_count / len(predictions) * 100:.1f}%)",
                )
                c2.metric(
                    "Ulasan Negatif",
                    f"{negative_count} ({negative_count / len(predictions) * 100:.1f}%)",
                )
        # -------------------------------------------------
        # ✍️ Tab Manual – input komentar sendiri (versi detail)
        with tab_manual:
            # Proses reset sebelum widget dibuat agar tidak melanggar aturan Streamlit
            if st.session_state.get("reset_manual"):
                st.session_state.test_manual_text_val = ""
                st.session_state.test_manual_result = None
                st.session_state["reset_manual"] = False

            st.subheader("Uji sentimen dari komentar manual")
            comment = st.text_area(
                "Tulis komentar di sini …",
                key="test_manual_text_val",
                height=150,
            )
            trigger_manual = st.button("Proses Komentar", key="btn_manual")

            if trigger_manual:
                if not comment.strip():
                    st.warning("Komentar tidak boleh kosong")
                else:
                    # Load model & vectorizer
                    try:
                        model = joblib.load(MODEL_PATH)
                        vectorizer = joblib.load(TFIDF_VECTORIZER_PATH)
                    except Exception as e:
                        st.error(f"Gagal memuat model/vectorizer: {e}")
                        st.stop()

                    # Component preprocessing
                    slang_dict = load_unified_slang_dict()
                    stopword_remover, stemmer = load_sastrawi_components()

                    # ------- Tahapan preprocessing (detail) -------
                    stage_clean = clean_text(comment)
                    stage_normalized = " ".join(
                        slang_dict.get(w, w) for w in stage_clean.split()
                    )
                    stage_stopword = stopword_remover.remove(stage_normalized)
                    tokens_after_stem = [
                        stemmer.stem(w) for w in stage_stopword.split()
                    ]
                    stage_stem = " ".join(tokens_after_stem)
                    final_tokens = [t for t in tokens_after_stem if len(t) > 2]
                    final_text = " ".join(final_tokens)

                    # ------- Prediksi -------
                    vec = vectorizer.transform([final_text])
                    pred = model.predict(vec)[0]

                    classes = list(model.classes_)
                    proba_all = (
                        model.predict_proba(vec)[0]
                        if hasattr(model, "predict_proba")
                        else None
                    )
                    if proba_all is not None:
                        # buat dict {class: prob}
                        class_proba = {
                            str(classes[i]): float(proba_all[i])
                            for i in range(len(classes))
                        }
                        confidence = float(proba_all.max())
                    else:
                        class_proba = None
                        confidence = None

                    # ------- Top fitur penyumbang (kata dengan bobot TF-IDF tertinggi) -------
                    try:
                        feature_names = vectorizer.get_feature_names_out()
                        vec_dense = vec.toarray().flatten()
                        top_idx = vec_dense.argsort()[::-1][:10]
                        top_features = [
                            (feature_names[i], float(vec_dense[i]))
                            for i in top_idx
                            if vec_dense[i] > 0
                        ]
                    except Exception:
                        top_features = []

                    # ------- Simpan hasil -------
                    st.session_state.test_manual_result = {
                        "original": comment,
                        "stage_clean": stage_clean,
                        "stage_normalized": stage_normalized,
                        "stage_stopword": stage_stopword,
                        "stage_stem": stage_stem,
                        "tokens": final_tokens,
                        "final_text": final_text,
                        "label": pred,
                        "classes": classes,
                        "class_proba": class_proba,
                        "confidence": confidence,
                        "top_features": top_features,
                        "vector_dim": int(vec.shape[1]),
                    }

            # ------- Tampilkan hasil (detail) -------
            if st.session_state.get("test_manual_result"):
                res = st.session_state.test_manual_result
                st.markdown("---")

                # Ringkasan label dengan alert berwarna
                if res["label"] == "Positif":
                    st.success(f"✅ Sentimen: POSITIF")
                elif res["label"] == "Negatif":
                    st.error(f"❌ Sentimen: NEGATIF")
                else:
                    st.info(f"🔎 Sentimen: {res['label']}")

                # Confidence & distribusi probabilitas
                st.markdown("##### 🎯 Tingkat Keyakinan (Confidence)")
                if res["confidence"] is not None:
                    st.progress(min(max(res["confidence"], 0.0), 1.0))
                    st.caption(
                        f"Confidence label **{res['label']}** ≈ {res['confidence']:.2%}"
                    )

                    # Tabel distribusi probabilitas per kelas
                    if res.get("class_proba"):
                        prob_df = pd.DataFrame(
                            {
                                "Label": list(res["class_proba"].keys()),
                                "Probabilitas": list(res["class_proba"].values()),
                            }
                        ).sort_values("Probabilitas", ascending=False)
                        st.dataframe(prob_df, hide_index=True, width="stretch")
                else:
                    st.caption("Model tidak menyediakan probabilitas.")

                # Tahapan preprocessing (rinci)
                with st.expander("🔬 Detail Tahapan Preprocessing", expanded=True):
                    st.markdown("**1️⃣ Teks asli**")
                    st.code(res["original"] or "(kosong)")

                    st.markdown(
                        "**2️⃣ Cleaning (hapus URL, emoji, angka, simbol, lower-case)**"
                    )
                    st.code(res["stage_clean"] or "(kosong)")

                    st.markdown("**3️⃣ Normalisasi Slang (slang → formal)**")
                    st.code(res["stage_normalized"] or "(kosong)")

                    st.markdown("**4️⃣ Stopword Removal**")
                    st.code(res["stage_stopword"] or "(kosong)")

                    st.markdown("**5️⃣ Stemming (menggunakan Sastrawi)**")
                    st.code(res["stage_stem"] or "(kosong)")

                    st.markdown(
                        f"**6️⃣ Tokenisasi (panjang token > 2)** → "
                        f"{len(res['tokens'])} token"
                    )
                    st.code(" | ".join(res["tokens"]) if res["tokens"] else "(kosong)")

                # Vektor TF-IDF & top fitur
                with st.expander("📊 Vektor TF-IDF & Kata Berpengaruh"):
                    st.write(f"Dimensi vektor: **{res['vector_dim']}** fitur")
                    if res.get("top_features"):
                        feat_df = pd.DataFrame(
                            res["top_features"], columns=["Kata", "Bobot TF-IDF"]
                        )
                        st.dataframe(feat_df, hide_index=True, width="stretch")
                    else:
                        st.caption(
                            "Tidak ada fitur dengan bobot > 0 "
                            "(teks mungkin terlalu pendek atau OOV)."
                        )

                # Tombol reset
                if st.button("🔄 Reset Hasil", key="btn_manual_reset"):
                    st.session_state["reset_manual"] = True
                    st.rerun()
