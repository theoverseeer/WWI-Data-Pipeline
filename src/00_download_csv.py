import shutil
import kagglehub
from pathlib import Path

def download_kaggle_data(kaggle_link: str, target_dir: str = "data"):

    # Download latest version
    path = kagglehub.dataset_download(kaggle_link)
    csv_files = Path(path).rglob("*csv")

    # Copy the files from the source directory (shutil works on every Python version;
    # Path.copy only exists in Python 3.14+)
    Path(target_dir).mkdir(parents=True, exist_ok=True)
    for f in csv_files:
        shutil.copy(f, Path(target_dir) / f.name)

    print(f"Successfully downloaded Kaggle data files to {target_dir}.")

if __name__=="__main__":
    download_kaggle_data(kaggle_link="pauloviniciusornelas/wwimporters")