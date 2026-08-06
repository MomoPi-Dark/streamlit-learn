import streamlit as st
import pandas as pd
import joblib
import json
import matplotlib.pyplot as plt
import seaborn as sns

from scipy import sparse
from datetime import datetime
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    confusion_matrix,
)

from structures.base import BasePage, Options
from lib.enum import StageKey, get_session_state, set_session_state
from lib.paths import (
    X_TEST_PATH,
    Y_TEST_PATH,
    MODEL_PATH,
    EVALUATION_DIR,
    METRICS_PATH,
)


@Options(
    page_name="evaluation",
    menu_name="Evaluasi Model",
    menu_icon="📈",
    category="training",
)
class AppPage(BasePage):

    def on_start(self) -> None:
        # STAGE_8 = True hanya jika hasil evaluasi benar-benar sudah
        # dihitung dan tersimpan di disk — bukan sekadar prasyarat terpenuhi.
        set_session_state(StageKey.STAGE_8, METRICS_PATH.exists())

    def run(self) -> None:
        warning = self._validate_requirements()

        st.title("📈 Evaluasi Model")
        st.write(
            "Model yang telah dilatih diuji pada **Data Uji (20%)** yang belum pernah "
            "dilihat oleh model selama training."
        )

        st.info(
            """
            **Tahap 8 - Evaluasi Model**

            - **Accuracy**: Persentase prediksi yang benar secara keseluruhan.
            - **Precision**: Akurasi prediksi positif/negatif.
            - **Recall**: Kemampuan mendeteksi sampel aktual per kelas.
            - **F1-Score**: Rata-rata harmonik Precision dan Recall.
            - **Confusion Matrix**: Visualisasi tabel prediksi vs aktual.
            """
        )

        if warning:
            st.warning(
                "### ⚠️ Persyaratan belum terpenuhi untuk Evaluasi Model\n\n"
                + "\n".join(f"- {msg}" for msg in warning)
            )

        st.markdown("---")

        if self._validate_requirements():
            st.error("🚫 Data belum siap. Selesaikan persyaratan di atas terlebih dahulu sebelum melanjutkan ke Evaluation.")
            st.stop()
            
        if METRICS_PATH.exists():
            self._render_existing_evaluation()
        else:
            self._render_evaluation()

    # ==========================================================
    # UI
    # ==========================================================

    def _render_existing_evaluation(self) -> None:
        with open(METRICS_PATH, encoding="utf-8") as f:
            metrics = json.load(f)

        st.success("✅ Model sudah dievaluasi.")

        self._render_metrics(metrics)

        st.markdown("---")

        with st.expander("🔄 Evaluasi Ulang"):
            st.warning(
                "Hasil evaluasi yang ada akan ditimpa apabila proses dijalankan kembali."
            )
            if st.button(
                "🔄 Evaluasi Ulang Model",
                type="primary",
                width="stretch",
                disabled=bool(self._validate_requirements()),
                key="reeval_button",
            ):
                self._run_evaluation()
                st.rerun()

    def _render_evaluation(self) -> None:
        if X_TEST_PATH.exists():
            X_test = sparse.load_npz(X_TEST_PATH)
            st.info(f"Data uji siap dievaluasi ({X_test.shape[0]:,} data, {X_test.shape[1]:,} fitur).")

        st.markdown("---")

        if st.button(
            "🚀 Mulai Evaluasi Model",
            type="primary",
            width="stretch",
            disabled=bool(self._validate_requirements()),
            key="eval_button",
        ):
            self._run_evaluation()
            st.rerun()

    def _run_evaluation(self) -> None:
        progress = st.progress(0.0)
        status = st.empty()

        metrics = self._process_evaluation(progress, status)

        EVALUATION_DIR.mkdir(parents=True, exist_ok=True)

        with open(METRICS_PATH, "w", encoding="utf-8") as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)

        progress.progress(1.0)
        status.success("✅ Evaluasi Model selesai.")

    def _render_metrics(self, metrics: dict) -> None:
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Accuracy", f"{metrics['accuracy'] * 100:.2f}%")

        with col2:
            st.metric("Precision", f"{metrics['precision'] * 100:.2f}%")

        with col3:
            st.metric("Recall", f"{metrics['recall'] * 100:.2f}%")

        with col4:
            st.metric("F1-Score", f"{metrics['f1_score'] * 100:.2f}%")

        st.caption(
            f"Precision, Recall, dan F1-Score di atas dihitung dengan rata-rata "
            f"**weighted** (mempertimbangkan proporsi tiap kelas). "
            f"Terakhir dievaluasi: {metrics['evaluated_at']}"
        )

        st.markdown("---")

        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.subheader("🧩 Confusion Matrix")

            fig, ax = plt.subplots(figsize=(5, 4))
            sns.heatmap(
                metrics["confusion_matrix"],
                annot=True,
                fmt="d",
                cmap="Blues",
                xticklabels=metrics["labels"],
                yticklabels=metrics["labels"],
                ax=ax,
            )
            ax.set_xlabel("Prediksi")
            ax.set_ylabel("Aktual")
            st.pyplot(fig)

        with col_right:
            st.subheader("📋 Laporan Klasifikasi per Kelas")

            report_df = pd.DataFrame(metrics["classification_report"]).transpose()
            st.dataframe(
                report_df.round(3),
                width="stretch",
            )

        st.download_button(
            label="⬇️ Download Hasil Evaluasi (.json)",
            data=json.dumps(metrics, indent=2, ensure_ascii=False),
            file_name=METRICS_PATH.name,
            mime="application/json",
            width="stretch",
        )

    # ==========================================================
    # PROCESS
    # ==========================================================

    def _process_evaluation(self, progress, status) -> dict:
        status.info("Memuat model dan data uji...")
        progress.progress(0.2)

        model = joblib.load(MODEL_PATH)
        X_test = sparse.load_npz(X_TEST_PATH)
        y_test = joblib.load(Y_TEST_PATH)

        status.info("Melakukan prediksi pada data uji...")
        progress.progress(0.5)

        y_pred = model.predict(X_test)
        labels = sorted(pd.Series(y_test).unique().tolist())

        status.info("Menghitung metrik performa...")
        progress.progress(0.8)

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, average="weighted", zero_division=0),
            "recall": recall_score(y_test, y_pred, average="weighted", zero_division=0),
            "f1_score": f1_score(y_test, y_pred, average="weighted", zero_division=0),
            "labels": labels,
            "confusion_matrix": confusion_matrix(y_test, y_pred, labels=labels).tolist(),
            "classification_report": classification_report(
                y_test, y_pred, labels=labels, output_dict=True, zero_division=0
            ),
            "evaluated_at": datetime.now().strftime("%d %b %Y %H:%M"),
        }

        return metrics

    # ==========================================================
    # VALIDATION
    # ==========================================================

    def _validate_requirements(self) -> list[str] | None:
        warnings: list[str] = []

        if not MODEL_PATH.exists():
            warnings.append("🤖 Model belum dilatih.")

        if not get_session_state(StageKey.STAGE_7):
            warnings.append("🤖 Tahap Training Model belum selesai.")

        if not X_TEST_PATH.exists() or not Y_TEST_PATH.exists():
            warnings.append("🔀 Data uji (Train-Test Split) belum tersedia.")

        if warnings:
            return warnings

        return None