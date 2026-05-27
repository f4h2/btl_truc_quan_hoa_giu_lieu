"""
visualization.py
----------------
Trực quan hóa dữ liệu Big Mac Index bằng matplotlib & seaborn.
Dữ liệu được lấy từ PySpark DataFrame rồi chuyển sang Pandas.

Biểu đồ tạo ra (lưu vào thư mục outputs/):
  1.  bar_top15_highest_price.png      – Top 15 quốc gia giá cao nhất
  2.  bar_top15_lowest_price.png       – Top 15 quốc gia giá thấp nhất
  3.  line_avg_price_by_year.png       – Giá trung bình toàn cầu theo năm
  4.  hist_dollar_price.png            – Phân phối giá (histogram + KDE)
  5.  scatter_gdp_vs_price.png         – GDP per capita vs dollar_price
  6.  heatmap_corr.png                 – Heatmap tương quan
  7.  boxplot_price_by_year.png        – Boxplot giá theo năm
  8.  line_usa_price.png               – Xu hướng giá Big Mac tại Mỹ
  9.  scatter_actual_vs_pred.png       – Giá thực tế vs dự đoán (regression)
  10. residual_plot.png                – Residual plot
  11. line_top_countries.png           – Xu hướng giá theo năm (top 10 quốc gia)
  12. bar_usd_raw_overvalued.png       – Mức định giá cao/thấp trung bình (USD_raw)
  13. heatmap_price_country_year.png   – Heatmap giá × quốc gia × năm
  14. scatter_gdp_vs_usdraw.png        – GDP per capita vs chỉ số định giá
  15. violin_price_by_decade.png       – Violin plot giá theo thập kỷ
"""

import os
import pandas as pd
import matplotlib
matplotlib.use("Agg")          # chạy không cần GUI
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import seaborn as sns
from pyspark.sql import functions as F

# Thiết lập style chung
sns.set_theme(style="whitegrid", palette="muted", font_scale=1.1)
plt.rcParams.update({"figure.dpi": 120})

OUTPUT_DIR = "outputs"


def _save(fig, filename):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    print(f"[Viz] Đã lưu: {path}")


# ── 1 & 2.  Top quốc gia giá cao / thấp ──────────────────────────────────────
def plot_top_countries(df):
    if not ("name" in df.columns and "dollar_price" in df.columns):
        return

    avg = (
        df.groupBy("name")
        .agg(F.avg("dollar_price").alias("avg_price"))
        .orderBy(F.desc("avg_price"))
        .toPandas()
    )

    # Top 15 cao nhất
    fig, ax = plt.subplots(figsize=(12, 6))
    top15 = avg.head(15)
    sns.barplot(data=top15, x="avg_price", y="name", palette="Reds_r", ax=ax)
    ax.set_title("Top 15 quốc gia có giá Big Mac trung bình CAO nhất (USD)")
    ax.set_xlabel("Giá trung bình (USD)")
    ax.set_ylabel("Quốc gia")
    _save(fig, "bar_top15_highest_price.png")

    # Top 15 thấp nhất
    fig, ax = plt.subplots(figsize=(12, 6))
    bot15 = avg.tail(15).iloc[::-1]
    sns.barplot(data=bot15, x="avg_price", y="name", palette="Blues_r", ax=ax)
    ax.set_title("Top 15 quốc gia có giá Big Mac trung bình THẤP nhất (USD)")
    ax.set_xlabel("Giá trung bình (USD)")
    ax.set_ylabel("Quốc gia")
    _save(fig, "bar_top15_lowest_price.png")


# ── 3.  Giá trung bình theo năm ───────────────────────────────────────────────
def plot_avg_price_by_year(df):
    if not ("year" in df.columns and "dollar_price" in df.columns):
        return

    yearly = (
        df.groupBy("year")
        .agg(
            F.avg("dollar_price").alias("avg_price"),
            F.min("dollar_price").alias("min_price"),
            F.max("dollar_price").alias("max_price"),
        )
        .orderBy("year")
        .toPandas()
    )

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.fill_between(yearly["year"], yearly["min_price"], yearly["max_price"],
                    alpha=0.2, color="steelblue", label="Min–Max")
    ax.plot(yearly["year"], yearly["avg_price"], marker="o", color="steelblue",
            linewidth=2, label="Trung bình")
    ax.set_title("Giá Big Mac USD trung bình toàn cầu theo năm")
    ax.set_xlabel("Năm")
    ax.set_ylabel("Giá (USD)")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.legend()
    _save(fig, "line_avg_price_by_year.png")


# ── 4.  Histogram dollar_price ────────────────────────────────────────────────
def plot_price_distribution(df):
    if "dollar_price" not in df.columns:
        return

    prices = df.select("dollar_price").toPandas()

    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(prices["dollar_price"].dropna(), bins=40, kde=True, color="steelblue", ax=ax)
    ax.set_title("Phân phối giá Big Mac (USD)")
    ax.set_xlabel("Giá (USD)")
    ax.set_ylabel("Số lượng")
    _save(fig, "hist_dollar_price.png")


# ── 5.  Scatter GDP vs dollar_price ──────────────────────────────────────────
def plot_gdp_vs_price(df):
    if not ("GDP_dollar" in df.columns and "dollar_price" in df.columns):
        return

    sample = df.select("GDP_dollar", "dollar_price").dropna().sample(
        fraction=min(1.0, 3000 / max(df.count(), 1)), seed=42
    ).toPandas()

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.regplot(data=sample, x="GDP_dollar", y="dollar_price",
                scatter_kws={"alpha": 0.4, "s": 20}, line_kws={"color": "red"}, ax=ax)
    ax.set_title("GDP bình quân đầu người vs Giá Big Mac (USD)")
    ax.set_xlabel("GDP per capita (USD)")
    ax.set_ylabel("Giá Big Mac (USD)")
    _save(fig, "scatter_gdp_vs_price.png")


# ── 6.  Heatmap tương quan ────────────────────────────────────────────────────
def plot_correlation_heatmap(df):
    corr_cols = [c for c in [
        "local_price", "dollar_price", "dollar_ex",
        "USD_raw", "GDP_dollar", "adj_price",
    ] if c in df.columns]

    if len(corr_cols) < 2:
        return

    pdf = df.select(corr_cols).dropna().toPandas()

    fig, ax = plt.subplots(figsize=(10, 8))
    corr_matrix = pdf.corr()
    mask = (corr_matrix.abs() < 0)   # không mask, hiển thị tất cả
    sns.heatmap(corr_matrix, annot=True, fmt=".2f", cmap="coolwarm",
                center=0, square=True, linewidths=0.5, ax=ax)
    ax.set_title("Heatmap hệ số tương quan")
    _save(fig, "heatmap_corr.png")


# ── 7.  Boxplot giá theo năm ──────────────────────────────────────────────────
def plot_boxplot_by_year(df):
    if not ("year" in df.columns and "dollar_price" in df.columns):
        return

    pdf = df.select("year", "dollar_price").dropna().toPandas()
    pdf["year"] = pdf["year"].astype(int)

    fig, ax = plt.subplots(figsize=(16, 6))
    pdf.boxplot(column="dollar_price", by="year", ax=ax, grid=False,
                boxprops=dict(color="steelblue"),
                whiskerprops=dict(color="steelblue"),
                medianprops=dict(color="red", linewidth=2))
    ax.set_title("Phân phối giá Big Mac USD theo năm")
    fig.suptitle("")
    ax.set_xlabel("Năm")
    ax.set_ylabel("Giá (USD)")
    plt.xticks(rotation=45)
    _save(fig, "boxplot_price_by_year.png")


# ── 8.  Xu hướng giá tại Mỹ ──────────────────────────────────────────────────
def plot_usa_trend(df):
    iso_col = next((c for c in ["iso_a3", "currency_code"] if c in df.columns), None)
    if iso_col is None or "year" not in df.columns:
        return

    iso_val = "USA" if iso_col == "iso_a3" else "USD"
    usa = (
        df.filter(F.col(iso_col) == iso_val)
        .select("year", "dollar_price", "date")
        .orderBy("date")
        .toPandas()
    )

    if usa.empty:
        return

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(usa["date"] if "date" in usa.columns else usa["year"],
            usa["dollar_price"], marker="o", color="orange", linewidth=2)
    ax.set_title("Xu hướng giá Big Mac tại Mỹ (USD)")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Giá (USD)")
    plt.xticks(rotation=30)
    _save(fig, "line_usa_price.png")


# ── 9 & 10.  Biểu đồ từ kết quả hồi quy ──────────────────────────────────────
def plot_regression_results(predictions_df):
    """
    predictions_df : PySpark DataFrame chứa cột 'dollar_price' và 'prediction'
    """
    if predictions_df is None:
        return

    pdf = predictions_df.select("dollar_price", "prediction").dropna().toPandas()
    pdf["residual"] = pdf["dollar_price"] - pdf["prediction"]

    # Actual vs Predicted
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.scatter(pdf["dollar_price"], pdf["prediction"], alpha=0.4, s=15, color="steelblue")
    lim = [min(pdf["dollar_price"].min(), pdf["prediction"].min()) - 0.5,
           max(pdf["dollar_price"].max(), pdf["prediction"].max()) + 0.5]
    ax.plot(lim, lim, "r--", linewidth=1.5, label="Lý tưởng (y = x)")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_title("Giá thực tế vs Giá dự đoán (Linear Regression)")
    ax.set_xlabel("Giá thực tế (USD)")
    ax.set_ylabel("Giá dự đoán (USD)")
    ax.legend()
    _save(fig, "scatter_actual_vs_pred.png")

    # Residual plot
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(pdf["prediction"], pdf["residual"], alpha=0.4, s=15, color="purple")
    ax.axhline(0, color="red", linestyle="--", linewidth=1.5)
    ax.set_title("Residual Plot (Phần dư)")
    ax.set_xlabel("Giá dự đoán (USD)")
    ax.set_ylabel("Phần dư")
    _save(fig, "residual_plot.png")


# ── 11.  Xu hướng giá top 10 quốc gia theo năm ───────────────────────────────
def plot_top_countries_trend(df):
    if not all(c in df.columns for c in ["name", "year", "dollar_price"]):
        return

    # Lấy top 10 quốc gia có nhiều dữ liệu nhất
    top_countries = (
        df.groupBy("name")
        .agg(F.count("dollar_price").alias("cnt"))
        .orderBy(F.desc("cnt"))
        .limit(10)
        .toPandas()["name"]
        .tolist()
    )

    pdf = (
        df.filter(F.col("name").isin(top_countries))
        .groupBy("name", "year")
        .agg(F.avg("dollar_price").alias("avg_price"))
        .orderBy("year")
        .toPandas()
    )

    fig, ax = plt.subplots(figsize=(14, 6))
    for country in top_countries:
        sub = pdf[pdf["name"] == country]
        ax.plot(sub["year"], sub["avg_price"], marker="o", markersize=3,
                linewidth=1.5, label=country)
    ax.set_title("Xu hướng giá Big Mac theo năm – Top 10 quốc gia")
    ax.set_xlabel("Năm")
    ax.set_ylabel("Giá trung bình (USD)")
    ax.xaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    ax.legend(fontsize=8, ncol=2, loc="upper left")
    _save(fig, "line_top_countries.png")


# ── 12.  Mức định giá cao/thấp trung bình (USD_raw) ──────────────────────────
def plot_usd_raw_by_country(df):
    if not all(c in df.columns for c in ["name", "USD_raw"]):
        return

    avg_raw = (
        df.groupBy("name")
        .agg(F.avg("USD_raw").alias("avg_usd_raw"))
        .orderBy("avg_usd_raw")
        .toPandas()
    )

    fig, ax = plt.subplots(figsize=(14, max(6, len(avg_raw) * 0.22)))
    colors = ["#e74c3c" if v > 0 else "#3498db" for v in avg_raw["avg_usd_raw"]]
    ax.barh(avg_raw["name"], avg_raw["avg_usd_raw"], color=colors)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_title("Mức định giá Big Mac so với USD (trung bình)\n"
                 "Đỏ = định giá cao hơn USD  |  Xanh = định giá thấp hơn USD")
    ax.set_xlabel("USD_raw (chỉ số định giá)")
    ax.set_ylabel("Quốc gia")
    plt.tight_layout()
    _save(fig, "bar_usd_raw_overvalued.png")


# ── 13.  Heatmap giá Big Mac theo quốc gia × năm ─────────────────────────────
def plot_heatmap_country_year(df):
    if not all(c in df.columns for c in ["name", "year", "dollar_price"]):
        return

    # Lấy top 30 quốc gia có nhiều dữ liệu
    top30 = (
        df.groupBy("name").count().orderBy(F.desc("count")).limit(30)
        .toPandas()["name"].tolist()
    )

    pdf = (
        df.filter(F.col("name").isin(top30))
        .groupBy("name", "year")
        .agg(F.avg("dollar_price").alias("avg_price"))
        .toPandas()
    )

    pivot = pdf.pivot(index="name", columns="year", values="avg_price")
    pivot = pivot.sort_values(by=pivot.columns[-1], ascending=False)

    fig, ax = plt.subplots(figsize=(18, 10))
    sns.heatmap(pivot, cmap="YlOrRd", linewidths=0.3, linecolor="gray",
                annot=False, fmt=".1f", ax=ax,
                cbar_kws={"label": "Giá Big Mac (USD)"})
    ax.set_title("Heatmap giá Big Mac (USD) theo Quốc gia × Năm")
    ax.set_xlabel("Năm")
    ax.set_ylabel("Quốc gia")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    _save(fig, "heatmap_price_country_year.png")


# ── 14.  Scatter GDP per capita vs chỉ số định giá (USD_raw) ─────────────────
def plot_gdp_vs_usdraw(df):
    if not all(c in df.columns for c in ["GDP_dollar", "USD_raw", "year"]):
        return

    # Lấy mẫu tối đa 3000 dòng, tô màu theo thập kỷ
    pdf = (
        df.select("GDP_dollar", "USD_raw", "year", "name")
        .dropna()
        .sample(fraction=min(1.0, 3000 / max(df.count(), 1)), seed=42)
        .toPandas()
    )
    pdf["decade"] = (pdf["year"] // 10 * 10).astype(str) + "s"

    fig, ax = plt.subplots(figsize=(11, 7))
    palette = sns.color_palette("tab10", n_colors=pdf["decade"].nunique())
    for i, (decade, grp) in enumerate(pdf.groupby("decade")):
        ax.scatter(grp["GDP_dollar"], grp["USD_raw"],
                   alpha=0.45, s=18, label=decade, color=palette[i])
    ax.axhline(0, color="black", linewidth=0.8, linestyle="--")
    ax.set_title("GDP per capita vs Chỉ số định giá Big Mac (USD_raw)")
    ax.set_xlabel("GDP per capita (USD)")
    ax.set_ylabel("USD_raw  (> 0: đắt hơn; < 0: rẻ hơn so với USD)")
    ax.legend(title="Thập kỷ", fontsize=9)
    _save(fig, "scatter_gdp_vs_usdraw.png")


# ── 15.  Violin plot giá theo thập kỷ ────────────────────────────────────────
def plot_violin_by_decade(df):
    if not all(c in df.columns for c in ["year", "dollar_price"]):
        return

    pdf = df.select("year", "dollar_price").dropna().toPandas()
    pdf["decade"] = (pdf["year"] // 10 * 10).astype(str) + "s"

    fig, ax = plt.subplots(figsize=(12, 6))
    order = sorted(pdf["decade"].unique())
    sns.violinplot(data=pdf, x="decade", y="dollar_price",
                   order=order, palette="Set2",
                   inner="quartile", cut=0, ax=ax)
    ax.set_title("Phân phối giá Big Mac theo thập kỷ (Violin Plot)")
    ax.set_xlabel("Thập kỷ")
    ax.set_ylabel("Giá Big Mac (USD)")
    _save(fig, "violin_price_by_decade.png")


# ── Entry point ────────────────────────────────────────────────────────────────
def run_visualization(df, predictions_df=None):
    """Chạy toàn bộ pipeline trực quan hóa."""
    print("\n" + "=" * 60)
    print("  VISUALIZATION")
    print("=" * 60)
    plot_top_countries(df)
    plot_avg_price_by_year(df)
    plot_price_distribution(df)
    plot_gdp_vs_price(df)
    plot_correlation_heatmap(df)
    plot_boxplot_by_year(df)
    plot_usa_trend(df)
    plot_regression_results(predictions_df)
    # Biểu đồ mới
    plot_top_countries_trend(df)
    plot_usd_raw_by_country(df)
    plot_heatmap_country_year(df)
    plot_gdp_vs_usdraw(df)
    plot_violin_by_decade(df)
    print(f"[Viz] Tất cả biểu đồ đã lưu trong thư mục: {OUTPUT_DIR}/")
    print("=" * 60)
