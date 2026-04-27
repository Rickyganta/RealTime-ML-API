from pathlib import Path
from zipfile import ZipFile

import requests

URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
OUT_DIR = Path("data")
ZIP_PATH = OUT_DIR / "ml-latest-small.zip"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=60)
    r.raise_for_status()
    ZIP_PATH.write_bytes(r.content)
    with ZipFile(ZIP_PATH) as zf:
        zf.extractall(OUT_DIR)
    print("Downloaded and extracted MovieLens to data/ml-latest-small")


if __name__ == "__main__":
    main()
