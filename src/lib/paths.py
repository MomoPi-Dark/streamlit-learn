import shutil
from pathlib import Path

# File ini di-import normal (bukan exec), jadi __file__ aman dipakai di sini
ROOT_DIR = Path(__file__).resolve().parents[2] / "public"

# Data folder yang sebenarnya berada di public/csv
CSV_DIR = ROOT_DIR / "csv"
ULASAN_RAW_CSV_PATH = CSV_DIR / "ulasan_raw_nte.csv"
SLANG_CSV_PATH = CSV_DIR / "slang.csv"
ULASAN_LABELED_CSV_PATH = CSV_DIR / "ulasan_berlabel_nte.csv"
PREPROCESSED_CSV_PATH = CSV_DIR / "ulasan_preprocessed_nte.csv"

TFIDF_DIR = ROOT_DIR / "tfidf"
TFIDF_VECTORIZER_PATH = TFIDF_DIR / "tfidf_vectorizer.pkl"
TFIDF_MATRIX_PATH = TFIDF_DIR / "tfidf_matrix.npz"
TFIDF_FEATURE_NAMES_PATH = TFIDF_DIR / "tfidf_feature_names.pkl"

SPLIT_DIR = ROOT_DIR / "split"
X_TRAIN_PATH = SPLIT_DIR / "X_train.npz"
X_TEST_PATH = SPLIT_DIR / "X_test.npz"
Y_TRAIN_PATH = SPLIT_DIR / "y_train.pkl"
Y_TEST_PATH = SPLIT_DIR / "y_test.pkl"

SMOTE_DIR = ROOT_DIR / "smote"
X_TRAIN_RESAMPLED_PATH = SMOTE_DIR / "X_train_resampled.npz"
Y_TRAIN_RESAMPLED_PATH = SMOTE_DIR / "y_train_resampled.pkl"

MODEL_DIR = ROOT_DIR / "model"
MODEL_PATH = MODEL_DIR / "naive_bayes_model.pkl"

EVALUATION_DIR = ROOT_DIR / "evaluation"
METRICS_PATH = EVALUATION_DIR / "metrics.json"

IMAGES_DIR = ROOT_DIR / "images"
WORD_FREQ_IMAGE_PATH = IMAGES_DIR / "diagram_batang_20_kata.png"


def WORDCLOUD_IMAGE_PATH_TEMPLATE(label: str) -> Path:
    return IMAGES_DIR / f"wordcloud_smote_{label.lower()}.png"


def clear_downstream_artifacts() -> None:
    """
    Hapus seluruh artefak turunan (labeling, preprocessing, TF-IDF, split,
    SMOTE, model, evaluasi, visualisasi) setiap kali dataset mentah diambil
    ulang (scraping ulang atau upload baru).

    Ini WAJIB dipanggil setelah ULASAN_RAW_CSV_PATH ditulis ulang, supaya
    tahap-tahap berikutnya tidak memakai data lama yang sudah tidak sinkron
    dengan dataset mentah yang baru (mis. jumlah baris berbeda, index berbeda,
    label/preprocessing dari dataset lama, model, evaluasi, atau gambar lama, dst).
    """
    for file_path in (ULASAN_LABELED_CSV_PATH, PREPROCESSED_CSV_PATH):
        if file_path.exists():
            file_path.unlink()

    for directory in (
        TFIDF_DIR,
        SPLIT_DIR,
        SMOTE_DIR,
        MODEL_DIR,
        EVALUATION_DIR,
        IMAGES_DIR,
    ):
        if directory.exists():
            shutil.rmtree(directory)
