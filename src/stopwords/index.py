from pathlib import Path


def load_stopwords(folder: str | Path = "src/stopwords") -> list[str]:
    folder = Path(folder)

    stopwords: set[str] = set()

    for file in folder.glob("*.txt"):
        with file.open("r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                if word:
                    stopwords.add(word)

    return sorted(stopwords)
