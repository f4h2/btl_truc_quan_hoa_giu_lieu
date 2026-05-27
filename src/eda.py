"""
eda.py
------
Phân tích khám phá dữ liệu (EDA) Big Mac Index sử dụng PySpark SQL.

Các phân tích:
  1. Thống kê mô tả các cột số
  2. Số lượng quốc gia & khoảng thời gian
  3. Top quốc gia giá Big Mac cao / thấp nhất (trung bình)
  4. Biến động giá USD theo năm
  5. Phân phối dollar_price
  6. Tương quan giữa GDP_dollar và dollar_price
"""

from pyspark.sql import functions as F


def run_eda(df):
    """Thực hiện toàn bộ EDA, in kết quả ra console."""

    print("\n" + "=" * 60)
    print("  EXPLORATORY DATA ANALYSIS (EDA)")
    print("=" * 60)

    # --- 1. Thống kê mô tả ---
    print("\n[EDA 1] Thống kê mô tả các cột số:")
    num_cols = [
        c for c in ["local_price", "dollar_price", "dollar_ex",
                    "USD_raw", "GDP_dollar", "adj_price"]
        if c in df.columns
    ]
    df.select(num_cols).describe().show(truncate=False)

    # --- 2. Tổng quan ---
    n_countries = df.select("name").distinct().count() if "name" in df.columns else "N/A"
    n_years = df.select("year").distinct().count() if "year" in df.columns else "N/A"
    year_min = df.agg(F.min("year")).collect()[0][0] if "year" in df.columns else "N/A"
    year_max = df.agg(F.max("year")).collect()[0][0] if "year" in df.columns else "N/A"

    print(f"\n[EDA 2] Tổng quan dữ liệu:")
    print(f"  - Số quốc gia / vùng lãnh thổ : {n_countries}")
    print(f"  - Khoảng thời gian             : {year_min} – {year_max}  ({n_years} năm)")
    print(f"  - Tổng số bản ghi              : {df.count()}")

    # --- 3. Top quốc gia giá cao / thấp ---
    if "name" in df.columns and "dollar_price" in df.columns:
        avg_by_country = (
            df.groupBy("name")
            .agg(F.avg("dollar_price").alias("avg_dollar_price"))
            .orderBy(F.desc("avg_dollar_price"))
        )
        print("\n[EDA 3a] Top 10 quốc gia có giá Big Mac trung bình CAO nhất (USD):")
        avg_by_country.show(10, truncate=False)

        print("[EDA 3b] Top 10 quốc gia có giá Big Mac trung bình THẤP nhất (USD):")
        avg_by_country.orderBy("avg_dollar_price").show(10, truncate=False)

    # --- 4. Giá trung bình toàn cầu theo năm ---
    if "year" in df.columns and "dollar_price" in df.columns:
        print("[EDA 4] Giá Big Mac USD trung bình toàn cầu theo năm:")
        (
            df.groupBy("year")
            .agg(
                F.avg("dollar_price").alias("avg_price"),
                F.min("dollar_price").alias("min_price"),
                F.max("dollar_price").alias("max_price"),
                F.count("*").alias("n_obs"),
            )
            .orderBy("year")
            .show(50, truncate=False)
        )

    # --- 5. Phân phối dollar_price (histogram bucket) ---
    if "dollar_price" in df.columns:
        print("[EDA 5] Phân phối dollar_price (bins = $1):")
        (
            df.withColumn("price_bucket", F.floor(F.col("dollar_price")).cast("int"))
            .groupBy("price_bucket")
            .count()
            .orderBy("price_bucket")
            .show(30, truncate=False)
        )

    # --- 6. Tương quan GDP vs dollar_price ---
    if "GDP_dollar" in df.columns and "dollar_price" in df.columns:
        corr = df.stat.corr("GDP_dollar", "dollar_price")
        print(f"\n[EDA 6] Hệ số tương quan Pearson (GDP_dollar ↔ dollar_price): {corr:.4f}")

    # --- 7. Missing values ---
    print("\n[EDA 7] Kiểm tra giá trị null còn lại:")
    null_counts = [(c, df.filter(F.col(c).isNull()).count()) for c in df.columns]
    for col, cnt in null_counts:
        if cnt > 0:
            print(f"  {col:<30}: {cnt}")
    if all(cnt == 0 for _, cnt in null_counts):
        print("  Không còn giá trị null.")

    print("\n" + "=" * 60)
    return df
