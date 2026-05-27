"""
main.py
-------
Pipeline chính – thực thi tuần tự:
  1. Preprocessing
  2. EDA
  3. Linear Regression
  4. Visualization

Cách chạy:
  python main.py [--data <đường_dẫn_csv>]

Mặc định tìm file CSV trong thư mục  data/big mac.csv
"""

import argparse
import os
import sys
import glob

# Thêm thư mục src vào PYTHONPATH khi chạy từ gốc dự án
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from preprocessing import create_spark_session, run_preprocessing
from eda import run_eda
from regression import run_regression
from visualization import run_visualization

# ── Đường dẫn mặc định ────────────────────────────────────────────────────────
DEFAULT_RAW      = os.path.join("data", "big mac.csv")
DEFAULT_GDP_1999 = os.path.join("data", "GDP by Country 1999-2022.csv")   # alejopaullier
DEFAULT_POP      = os.path.join("data", "world_population.csv")           # hasibalmuzdadid
CLEAN_PARQUET    = os.path.join("outputs", "clean_data.parquet")
OUTPUT_DIR       = "outputs"


def _kaggle_download_csv(dataset_handle: str, dest_path: str, file_keyword: str = None) -> str:
    """
    Helper: tải 1 dataset Kaggle, tìm file CSV khớp file_keyword (nếu có),
    copy vào dest_path. Trả về dest_path nếu thành công, None nếu thất bại.
    """
    import shutil
    try:
        import kagglehub
    except ImportError:
        print("[Download] kagglehub chưa được cài. Chạy: pip install kagglehub")
        return None

    if os.path.exists(dest_path):
        print(f"[Download] File đã tồn tại, bỏ qua tải: {dest_path}")
        return dest_path

    print(f"[Download] Đang tải '{dataset_handle}' từ Kaggle ...")
    try:
        path = kagglehub.dataset_download(dataset_handle)
    except Exception as e:
        print(f"[Download] Lỗi khi tải '{dataset_handle}': {e}")
        return None

    csv_files = glob.glob(os.path.join(path, "**", "*.csv"), recursive=True)
    if not csv_files:
        print(f"[Download] Không tìm thấy file CSV trong '{dataset_handle}'.")
        return None

    # Nếu có keyword, ưu tiên file khớp; nếu không thì lấy file đầu tiên
    if file_keyword:
        matched = [f for f in csv_files if file_keyword.lower() in os.path.basename(f).lower()]
        chosen = matched[0] if matched else csv_files[0]
    else:
        chosen = csv_files[0]

    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
    shutil.copy2(chosen, dest_path)
    print(f"[Download] Đã lưu: {chosen} → {dest_path}")
    return dest_path


def download_gdp_1999_dataset() -> str:
    """Tải 'GDP by Country 1999-2022.csv' (alejopaullier/-gdp-by-country-1999-2022)."""
    return _kaggle_download_csv(
        dataset_handle="alejopaullier/-gdp-by-country-1999-2022",
        dest_path=DEFAULT_GDP_1999,
        file_keyword="GDP by Country",
    )


def download_population_dataset() -> str:
    """Tải 'world_population.csv' (hasibalmuzdadid/world-population-analysis)."""
    return _kaggle_download_csv(
        dataset_handle="hasibalmuzdadid/world-population-analysis",
        dest_path=DEFAULT_POP,
        file_keyword="world_population",
    )


def download_dataset() -> str:
    """
    Tự động tải dataset từ Kaggle bằng kagglehub.
    Trả về đường dẫn tới file CSV.
    """
    try:
        import kagglehub
    except ImportError:
        print("[Download] kagglehub chưa được cài. Chạy: pip install kagglehub")
        return None

    print("[Download] Đang tải dataset từ Kaggle: mrmorj/big-mac-index-data ...")
    path = kagglehub.dataset_download("mrmorj/big-mac-index-data")
    print(f"[Download] Dataset đã tải về: {path}")

    # Tìm file CSV trong thư mục vừa tải
    csv_files = glob.glob(os.path.join(path, "**", "*.csv"), recursive=True)
    if not csv_files:
        print("[Download] Không tìm thấy file CSV trong dataset đã tải.")
        return None

    # Copy/symlink vào data/ để pipeline dùng đường dẫn nhất quán
    os.makedirs("data", exist_ok=True)
    src_csv = csv_files[0]
    dest_csv = DEFAULT_RAW
    if not os.path.exists(dest_csv):
        import shutil
        shutil.copy2(src_csv, dest_csv)
        print(f"[Download] Đã copy CSV → {dest_csv}")
    else:
        print(f"[Download] File đã tồn tại, bỏ qua copy: {dest_csv}")

    return dest_csv


def parse_args():
    parser = argparse.ArgumentParser(description="Big Mac Index – PySpark Pipeline")
    parser.add_argument(
        "--data", default=DEFAULT_RAW,
        help=f"Đường dẫn tới file CSV (mặc định: {DEFAULT_RAW})"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Tự động tải dataset nếu file chưa tồn tại
    if not os.path.exists(args.data):
        print(f"[Main] File '{args.data}' chưa có → thử tải tự động bằng kagglehub...")
        downloaded = download_dataset()
        if downloaded is None or not os.path.exists(downloaded):
            print(f"[ERROR] Không tìm thấy file dữ liệu: {args.data}")
            print("  → Tải thủ công tại: https://www.kaggle.com/datasets/mrmorj/big-mac-index-data")
            print(f"  → Sau đó đặt file CSV vào: {DEFAULT_RAW}")
            sys.exit(1)
        args.data = downloaded

    # ── 1. Khởi tạo Spark ──────────────────────────────────────────────────────
    print("\n[Main] Khởi động SparkSession...")
    spark = create_spark_session("BigMacIndex")

    # ── 2. Preprocessing ───────────────────────────────────────────────────────
    print("\n[Main] ── Bước 1: Preprocessing ──")

    # Tự động tải GDP 1999-2022 nếu chưa có
    if not os.path.exists(DEFAULT_GDP_1999):
        print(f"[Main] Chưa có '{DEFAULT_GDP_1999}' → tải tự động...")
        download_gdp_1999_dataset()

    # Tự động tải World Population nếu chưa có
    if not os.path.exists(DEFAULT_POP):
        print(f"[Main] Chưa có '{DEFAULT_POP}' → tải tự động...")
        download_population_dataset()

    # Kiểm tra file GDP 1999-2022 + World Population (nguồn chính)
    gdp_1999_path = DEFAULT_GDP_1999 if os.path.exists(DEFAULT_GDP_1999) else None
    pop_path      = DEFAULT_POP      if os.path.exists(DEFAULT_POP)      else None

    if gdp_1999_path and pop_path:
        print(f"[Main] Dùng GDP per capita: '{gdp_1999_path}' + '{pop_path}'")
        df_clean = run_preprocessing(
            spark, args.data, CLEAN_PARQUET,
            gdp_1999_path=gdp_1999_path,
            pop_path=pop_path,
        )
    else:
        missing = []
        if not gdp_1999_path:
            missing.append(f"'{DEFAULT_GDP_1999}'")
        if not pop_path:
            missing.append(f"'{DEFAULT_POP}'")
        print(f"[Main] ⚠  Thiếu file: {', '.join(missing)} – chạy preprocessing không enrich GDP.")
        df_clean = run_preprocessing(spark, args.data, CLEAN_PARQUET)

    # ── 3. EDA ─────────────────────────────────────────────────────────────────
    print("\n[Main] ── Bước 2: EDA ──")
    run_eda(df_clean)

    # ── 4. Linear Regression ───────────────────────────────────────────────────
    print("\n[Main] ── Bước 3: Linear Regression ──")
    _, predictions, metrics = run_regression(df_clean, output_dir=OUTPUT_DIR)

    # ── 5. Visualization ───────────────────────────────────────────────────────
    print("\n[Main] ── Bước 4: Visualization ──")
    run_visualization(df_clean, predictions_df=predictions)

    # ── Tổng kết ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  HOÀN THÀNH!")
    print(f"  R²   = {metrics['r2']:.4f}")
    print(f"  RMSE = {metrics['rmse']:.4f}")
    print(f"  MAE  = {metrics['mae']:.4f}")
    print(f"  Kết quả & biểu đồ lưu trong: {OUTPUT_DIR}/")
    print("=" * 60)

    spark.stop()


if __name__ == "__main__":
    main()
