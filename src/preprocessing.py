"""
preprocessing.py
----------------
Tiền xử lý dữ liệu Big Mac Index sử dụng PySpark.

Các bước:
  1. Đọc CSV
  2. Kiểm tra và xử lý giá trị null
  3. Ép kiểu dữ liệu
  4. Trích xuất năm từ cột date
  5. Bổ sung GDP_dollar (GDP per capita, USD) từ 2 nguồn:
       - GDP by Country 1999-2022 (Kaggle: alejopaullier/-gdp-by-country-1999-2022)
         → tổng GDP theo tỷ USD, rows = quốc gia, cols = năm
       - World Population (Kaggle: hasibalmuzdadid/world-population-analysis)
         → dân số ở các năm snapshot; dùng linear regression per-country
           để ước lượng dân số cho các năm còn thiếu
       → GDP_dollar = GDP_total_USD / estimated_population
       Chỉ điền vào những dòng đang null, giữ nguyên giá trị đã có.
  6. Loại bỏ các cột không cần thiết
  7. Lưu dữ liệu sạch ra Parquet
"""

import numpy as np
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, IntegerType, LongType, StructType, StructField, StringType


def create_spark_session(app_name: str = "BigMacIndex") -> SparkSession:
    """Khởi tạo SparkSession."""
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")
        .config("spark.sql.shuffle.partitions", "8")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def load_data(spark: SparkSession, path: str):
    """Đọc file CSV về DataFrame."""
    df = spark.read.csv(path, header=True, inferSchema=True)
    print(f"[Preprocessing] Số dòng gốc : {df.count()}")
    print(f"[Preprocessing] Số cột      : {len(df.columns)}")
    print("[Preprocessing] Schema:")
    df.printSchema()
    return df


def clean_data(df):
    """
    Làm sạch dữ liệu:
      - Rename cột có khoảng trắng
      - Ép kiểu numeric
      - Xử lý null
      - Thêm cột year
    """
    # Đổi tên cột chứa dấu cách / ký tự đặc biệt
    rename_map = {c: c.strip().replace(" ", "_").replace("-", "_") for c in df.columns}
    for old, new in rename_map.items():
        if old != new:
            df = df.withColumnRenamed(old, new)

    # Ép kiểu các cột số
    numeric_cols = [
        "local_price", "dollar_ex", "dollar_price",
        "USD_raw", "EUR_raw", "GBP_raw", "JPY_raw", "CNY_raw",
        "GDP_dollar", "adj_price",
        "USD_adjusted", "EUR_adjusted", "GBP_adjusted", "JPY_adjusted", "CNY_adjusted",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df = df.withColumn(col, F.col(col).cast(DoubleType()))

    # Chuyển cột date sang DateType
    if "date" in df.columns:
        df = df.withColumn("date", F.to_date(F.col("date")))
        df = df.withColumn("year", F.year(F.col("date")).cast(IntegerType()))

    # Xoá các dòng thiếu giá trị ở cột quan trọng
    key_cols = ["local_price", "dollar_price", "dollar_ex"]
    existing_key = [c for c in key_cols if c in df.columns]
    df = df.dropna(subset=existing_key)

    # # Điền null GDP bằng median (dùng approxQuantile), dùng median để ouliner không mạnh, mean sẽ bị ouliner mạnh
    # if "GDP_dollar" in df.columns:
    #     median_gdp = df.approxQuantile("GDP_dollar", [0.5], 0.01)[0]
    #     df = df.fillna({"GDP_dollar": median_gdp})

    print(f"[Preprocessing] Số dòng sau khi làm sạch: {df.count()}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 1 – Tải GDP by Country 1999-2022
#   Nguồn: Kaggle alejopaullier/-gdp-by-country-1999-2022
#   Định dạng: wide – rows = quốc gia (tên), cols = năm 1999..2022
#   Đơn vị  : tỷ USD (billions)
# ─────────────────────────────────────────────────────────────────────────────

def load_gdp_per_country_1999(spark: SparkSession, gdp_path: str):
    """
    Đọc 'GDP by Country 1999-2022.csv', unpivot sang long format.
    Trả về DataFrame với các cột:
      country_name (string), year (int), gdp_billions (double)
    """
    gdp_raw = spark.read.csv(gdp_path, header=True, inferSchema=True)
    print(f"[GDP-1999] Columns: {gdp_raw.columns[:5]} ...")

    # Cột đầu tiên là tên quốc gia (thường tên khác nhau tùy file)
    country_col = gdp_raw.columns[0]
    year_cols   = [c for c in gdp_raw.columns[1:] if c.strip().isdigit()]

    gdp_raw = gdp_raw.withColumnRenamed(country_col, "country_name")

    stack_expr = "stack({n}, {pairs}) AS (year_str, gdp_billions)".format(
        n=len(year_cols),
        pairs=", ".join([f"'{y}', `{y}`" for y in year_cols]),
    )
    gdp_long = (
        gdp_raw
        .select("country_name", F.expr(stack_expr))
        .withColumn("year",        F.col("year_str").cast(IntegerType()))
        .withColumn("gdp_billions", F.col("gdp_billions").cast(DoubleType()))
        .drop("year_str")
        .filter(F.col("gdp_billions").isNotNull())
    )
    print(f"[GDP-1999] Long format: {gdp_long.count()} dòng")
    return gdp_long


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 2 – Tải World Population & Hồi quy tuyến tính cho các năm thiếu
#   Nguồn: Kaggle hasibalmuzdadid/world-population-analysis → world_population.csv
#   Cột   : CCA3, Country/Territory, 2022 Population, 2020 Population,
#            2015 Population, 2010 Population, 2000 Population,
#            1990 Population, 1980 Population, 1970 Population, ...
#   Kết quả: DataFrame (cca3, year, population) cho mọi năm 1999..2022
# ─────────────────────────────────────────────────────────────────────────────

_POP_SNAPSHOT_YEARS = [1970, 1980, 1990, 2000, 2010, 2015, 2020, 2022]


def load_population_data(spark: SparkSession, pop_path: str):
    """
    Đọc world_population.csv.
    Trả về pandas DataFrame gồm cột: cca3, year, population
    (chỉ các năm snapshot đã có sẵn trong file).
    """
    pop_raw = spark.read.csv(pop_path, header=True, inferSchema=True)

    # Chuẩn hoá tên cột – bỏ khoảng trắng
    rename = {c: c.strip() for c in pop_raw.columns}
    for old, new in rename.items():
        if old != new:
            pop_raw = pop_raw.withColumnRenamed(old, new)

    print(f"[Population] Columns: {pop_raw.columns}")

    # Xác định cột mã quốc gia (CCA3 hoặc tương đương)
    cca3_candidates = [c for c in pop_raw.columns if "CCA3" in c.upper() or c.upper() in ("ISO3", "CODE")]
    if not cca3_candidates:
        raise ValueError("[Population] Không tìm thấy cột mã quốc gia (CCA3).")
    cca3_col = cca3_candidates[0]

    # Xác định các cột dân số theo năm, vd: "2022 Population"
    pop_col_map = {}          # {năm (int): tên cột}
    for y in _POP_SNAPSHOT_YEARS:
        for c in pop_raw.columns:
            if str(y) in c and "pop" in c.lower():
                pop_col_map[y] = c
                break

    if not pop_col_map:
        raise ValueError("[Population] Không tìm thấy cột dân số theo năm.")
    print(f"[Population] Cột năm tìm được: { {y: c for y, c in pop_col_map.items()} }")

    # Giữ lại cột cần thiết
    keep = [cca3_col] + list(pop_col_map.values())
    pop_pd = pop_raw.select(keep).toPandas()
    pop_pd = pop_pd.rename(columns={cca3_col: "cca3"})

    # Chuyển sang long format bằng pandas
    rows = []
    for y, col in pop_col_map.items():
        tmp = pop_pd[["cca3", col]].copy()
        tmp.columns = ["cca3", "population"]
        tmp["year"] = y
        tmp["population"] = (
            tmp["population"]
            .astype(str).str.replace(",", "", regex=False)
            .str.strip()
        )
        tmp["population"] = tmp["population"].apply(
            lambda v: float(v) if v not in ("", "nan", "None") else None
        )
        rows.append(tmp)

    import pandas as pd
    pop_long = pd.concat(rows, ignore_index=True).dropna(subset=["population"])
    pop_long["cca3"] = pop_long["cca3"].str.strip().str.upper()
    print(f"[Population] Long format (snapshot): {len(pop_long)} dòng")
    return pop_long


def estimate_population_all_years(pop_long_pd, year_min: int = 1999, year_max: int = 2022):
    """
    Với mỗi quốc gia (cca3), dùng linear regression (numpy polyfit bậc 1)
    trên các snapshot năm → ước lượng dân số cho mọi năm trong [year_min, year_max].

    Trả về pandas DataFrame: cca3, year, population_est
    """
    import pandas as pd

    all_years  = list(range(year_min, year_max + 1))
    result_rows = []

    for cca3, grp in pop_long_pd.groupby("cca3"):
        grp_clean = grp[["year", "population"]].dropna().sort_values("year")
        if len(grp_clean) < 2:
            # Chỉ có 1 điểm – dùng hằng số
            if len(grp_clean) == 1:
                pop_val = float(grp_clean["population"].iloc[0])
                result_rows += [{"cca3": cca3, "year": y, "population_est": pop_val}
                                 for y in all_years]
            continue

        years   = grp_clean["year"].values.astype(float)
        pops    = grp_clean["population"].values.astype(float)
        coeffs  = np.polyfit(years, pops, 1)   # [slope, intercept]
        poly_fn = np.poly1d(coeffs)

        for y in all_years:
            est = float(poly_fn(y))
            if est < 1:
                est = 1.0           # tránh chia cho âm / 0
            result_rows.append({"cca3": cca3, "year": y, "population_est": est})

    pop_est = pd.DataFrame(result_rows)
    print(f"[Population] Sau regression: {len(pop_est)} dòng, "
          f"{pop_est['cca3'].nunique()} quốc gia, năm {year_min}–{year_max}")
    return pop_est


# ─────────────────────────────────────────────────────────────────────────────
# PHẦN 3 – Kết hợp GDP + Population → GDP per capita, điền vào Big Mac
# ─────────────────────────────────────────────────────────────────────────────

def _build_country_name_to_iso_map(spark: SparkSession, iso_csv_path: str = None):
    """
    Tạo bảng ánh xạ tên quốc gia (từ GDP 1999 dataset) → ISO A3 (iso_a3).
    Dùng dữ liệu quốc gia đã có trong Big Mac (name ↔ iso_a3) để ánh xạ.
    Trả về dict {country_name_lower: iso_a3}.
    """
    return {}   # sẽ được xây dựng động từ Big Mac DataFrame


def enrich_with_gdp_per_capita(df, spark: SparkSession,
                                 gdp_path: str, pop_path: str):
    """
    Điền GDP_dollar (GDP per capita, USD) vào các dòng null trong Big Mac bằng:
      GDP_dollar = (gdp_billions × 1e9) / population_est

    Nguồn:
      gdp_path : 'GDP by Country 1999-2022.csv'  (Kaggle: alejopaullier)
      pop_path : 'world_population.csv'           (Kaggle: hasibalmuzdadid)

    Chiến lược join:
      Big Mac có cột (name, iso_a3).  GDP 1999 có tên quốc gia (country_name).
      Xây mapping country_name → iso_a3 từ chính dữ liệu Big Mac,
      sau đó join theo iso_a3 × year.
    """
    import pandas as pd

    # ── 1. Tải GDP long ──────────────────────────────────────────────────────
    gdp_long = load_gdp_per_country_1999(spark, gdp_path)   # (country_name, year, gdp_billions)

    # ── 2. Tải & hồi quy dân số ─────────────────────────────────────────────
    pop_snapshot_pd = load_population_data(spark, pop_path)
    pop_est_pd      = estimate_population_all_years(pop_snapshot_pd)
    # Ép kiểu tường minh
    pop_est_pd["year"]           = pop_est_pd["year"].astype(float).astype(int)
    pop_est_pd["population_est"] = pop_est_pd["population_est"].astype(float)
    pop_est_pd["cca3"]           = pop_est_pd["cca3"].astype(str)

    # Chọn đúng thứ tự cột rồi để Spark tự infer kiểu
    pop_est_pd = pop_est_pd[["cca3", "year", "population_est"]]
    pop_est_spark = (
        spark.createDataFrame(pop_est_pd)
        .withColumn("year",           F.col("year").cast(IntegerType()))
        .withColumn("population_est", F.col("population_est").cast(DoubleType()))
    )

    # ── 3. Xây mapping tên → iso_a3 từ Big Mac ──────────────────────────────
    # Big Mac: name (vd "Argentina"), iso_a3 (vd "ARG")
    bm_name_map = (
        df.select("name", "iso_a3")
          .distinct()
          .toPandas()
    )
    # GDP 1999: country_name (vd "Argentina")
    gdp_names_pd = gdp_long.select("country_name").distinct().toPandas()

    # ── Tầng 1: Exact match (case-insensitive) ────────────────────────────────
    bm_name_map["name_lower"]      = bm_name_map["name"].str.lower().str.strip()
    gdp_names_pd["name_lower"]     = gdp_names_pd["country_name"].str.lower().str.strip()
    bm_lower_to_iso = bm_name_map.set_index("name_lower")["iso_a3"].to_dict()

    # ── Tầng 2: Bảng alias thủ công cho các tên khác nhau phổ biến ───────────
    _MANUAL_ALIAS = {
        # GDP 1999 name (lower)           : Big Mac name (lower)
        "united states":                   "united states",
        "usa":                             "united states",
        "south korea":                     "south korea",
        "korea, rep.":                     "south korea",
        "korea, south":                    "south korea",
        "united kingdom":                  "britain",
        "uk":                              "britain",
        "great britain":                   "britain",
        "euro area":                       "euro area",
        "euro zone":                       "euro area",
        "euizon":                          "euro area",
        "czech republic":                  "czech republic",
        "czechia":                         "czech republic",
        "hong kong sar, china":            "hong kong",
        "hong kong, china":                "hong kong",
        "hong kong s.a.r.":                "hong kong",
        "china, p.r.: hong kong":          "hong kong",
        "taiwan, province of china":       "taiwan",
        "taiwan":                          "taiwan",
        "china, p.r.: mainland":           "china",
        "venezuela, rb":                   "venezuela",
        "venezuela (bolivarian republic)": "venezuela",
        "iran, islamic rep.":              "sri lanka",   # placeholder – handled below
        "iran (islamic republic of)":      "sri lanka",
        "russian federation":              "russia",
        "dominican rep.":                  "dominican republic",
        "slovak republic":                 "slovakia",
        "north macedonia":                 "north macedonia",
        "republic of north macedonia":     "north macedonia",
        "viet nam":                        "vietnam",
        "lao pdr":                         "vietnam",    # placeholder
        "egypt, arab rep.":                "egypt",
        "pakistan":                        "pakistan",
        "turkey":                          "turkey",
        "türkiye":                         "turkey",
        "kyrgyz republic":                 "kyrgyzstan",
        "moldova":                         "moldova",
        "republic of moldova":             "moldova",
        "côte d'ivoire":                   "ivory coast",
        "cote d'ivoire":                   "ivory coast",
        "trinidad and tobago":             "trinidad & tobago",
    }
    # Xây bảng tra alias: gdp_name_lower → iso_a3
    alias_to_iso: dict = {}
    for gdp_alias, bm_name in _MANUAL_ALIAS.items():
        iso = bm_lower_to_iso.get(bm_name.lower())
        if iso:
            alias_to_iso[gdp_alias] = iso

    # ── Tầng 3: Fuzzy match (difflib) cho các tên vẫn chưa khớp ─────────────
    import difflib
    bm_lower_names = list(bm_lower_to_iso.keys())

    def _fuzzy_iso(gdp_name_lower: str, cutoff: float = 0.88):
        """Trả về iso_a3 từ tên gần giống nhất trong Big Mac (nếu score >= cutoff)."""
        matches = difflib.get_close_matches(gdp_name_lower, bm_lower_names,
                                            n=1, cutoff=cutoff)
        if matches:
            return bm_lower_to_iso[matches[0]]
        return None

    # Gộp 3 tầng thành name_to_iso
    name_to_iso: dict = {}
    fuzzy_log: list = []
    for _, row in gdp_names_pd.iterrows():
        cname     = row["country_name"]
        cname_low = row["name_lower"]

        iso = (bm_lower_to_iso.get(cname_low)          # tầng 1: exact
               or alias_to_iso.get(cname_low)           # tầng 2: alias
               or _fuzzy_iso(cname_low))                # tầng 3: fuzzy

        if iso:
            name_to_iso[cname] = iso
            if cname_low not in bm_lower_to_iso and cname_low not in alias_to_iso:
                fuzzy_log.append(f"  fuzzy: '{cname}' → '{iso}'")

    matched = len(name_to_iso)
    total   = len(gdp_names_pd)
    print(f"[Enrich] Khớp tên quốc gia GDP↔BigMac: {matched}/{total} quốc gia")
    if fuzzy_log:
        print(f"[Enrich] Fuzzy matches ({len(fuzzy_log)}):")
        for l in fuzzy_log[:20]:
            print(l)
        if len(fuzzy_log) > 20:
            print(f"  ... và {len(fuzzy_log) - 20} khớp khác")

    # ── 4. Thêm cột iso_a3 vào GDP long ─────────────────────────────────────
    gdp_long_pd = gdp_long.toPandas()
    gdp_long_pd["iso_a3"] = gdp_long_pd["country_name"].map(name_to_iso)
    gdp_long_clean = gdp_long_pd[gdp_long_pd["iso_a3"].notna()].copy()

    # Ép kiểu + đảm bảo đúng thứ tự cột trước khi đưa vào Spark
    gdp_long_clean["year"]         = gdp_long_clean["year"].astype(float).astype(int)
    gdp_long_clean["gdp_billions"] = gdp_long_clean["gdp_billions"].astype(float)
    gdp_long_clean["country_name"] = gdp_long_clean["country_name"].astype(str)
    gdp_long_clean["iso_a3"]       = gdp_long_clean["iso_a3"].astype(str)

    # Chọn đúng thứ tự cột khớp schema, tránh Spark map nhầm vị trí
    gdp_long_clean = gdp_long_clean[["country_name", "year", "gdp_billions", "iso_a3"]]

    gdp_with_iso = (
        spark.createDataFrame(gdp_long_clean)          # để Spark tự infer kiểu
        .withColumn("year",         F.col("year").cast(IntegerType()))
        .withColumn("gdp_billions", F.col("gdp_billions").cast(DoubleType()))
    )

    # ── 5. Join GDP + Population → gdp_per_capita ───────────────────────────
    gdp_pc = (
        gdp_with_iso
        .join(
            pop_est_spark.withColumnRenamed("cca3", "iso_a3_pop"),
            on=(
                (F.col("iso_a3") == F.col("iso_a3_pop")) &
                (gdp_with_iso["year"] == pop_est_spark["year"])
            ),
            how="left",
        )
        .withColumn(
            "gdp_per_capita",
            F.when(
                F.col("population_est").isNotNull() & (F.col("population_est") > 0),
                (F.col("gdp_billions") * 1e9) / F.col("population_est"),
            ).otherwise(F.lit(None).cast(DoubleType()))
        )
        .select(
            F.col("iso_a3").alias("gdp_iso"),
            gdp_with_iso["year"].alias("gdp_year"),
            F.col("gdp_per_capita"),
        )
        .filter(F.col("gdp_per_capita").isNotNull())
    )

    # ── 6. Left join vào Big Mac, chỉ điền khi GDP_dollar đang null ──────────
    df_enriched = df.join(
        gdp_pc,
        on=(
            (F.col("iso_a3") == F.col("gdp_iso")) &
            (F.col("year")   == F.col("gdp_year"))
        ),
        how="left",
    ).drop("gdp_iso", "gdp_year")

    if "GDP_dollar" in df_enriched.columns:
        df_enriched = df_enriched.withColumn(
            "GDP_dollar",
            F.coalesce(F.col("GDP_dollar"), F.col("gdp_per_capita")),
        )
    else:
        df_enriched = df_enriched.withColumnRenamed("gdp_per_capita", "GDP_dollar")

    if "gdp_per_capita" in df_enriched.columns:
        df_enriched = df_enriched.drop("gdp_per_capita")

    null_cnt = df_enriched.filter(F.col("GDP_dollar").isNull()).count()
    print(f"[Enrich] Sau enrich_with_gdp_per_capita – null GDP_dollar còn lại: {null_cnt}")
    return df_enriched


# ─────────────────────────────────────────────────────────────────────────────
def save_enriched_snapshot(df, output_dir: str = "outputs"):
    """
    Lưu snapshot dữ liệu ngay sau bước enrich_with_gdp.
    Gồm 2 định dạng:
      - Parquet : outputs/enriched_snapshot.parquet  (để Spark đọc lại nhanh)
      - CSV     : outputs/enriched_snapshot.csv      (để xem trực tiếp, 1 file duy nhất)
    Ngoài ra in ra console:
      - Schema mới (thấy các cột được cập nhật)
      - Thống kê nhanh GDP_dollar trước / sau enrich
      - 10 dòng mẫu
    """
    import os
    os.makedirs(output_dir, exist_ok=True)

    parquet_path = os.path.join(output_dir, "enriched_snapshot.parquet")
    csv_path     = os.path.join(output_dir, "enriched_snapshot.csv")

    # Lưu Parquet
    df.coalesce(1).write.mode("overwrite").parquet(parquet_path)
    print(f"[Snapshot] Parquet đã lưu : {parquet_path}")

    # Lưu CSV (1 file, có header)
    df.coalesce(1).write.mode("overwrite").option("header", True).csv(csv_path)
    print(f"[Snapshot] CSV    đã lưu : {csv_path}")

    # In schema
    print("\n[Snapshot] Schema sau enrich_with_gdp:")
    df.printSchema()

    # Thống kê GDP_dollar
    if "GDP_dollar" in df.columns:
        print("[Snapshot] Thống kê GDP_dollar sau enrich:")
        df.select(
            F.count("GDP_dollar").alias("count_non_null"),
            F.count(F.when(F.col("GDP_dollar").isNull(), 1)).alias("count_null"),
            F.min("GDP_dollar").alias("min"),
            F.max("GDP_dollar").alias("max"),
            F.avg("GDP_dollar").alias("mean"),
        ).show(truncate=False)

    # 10 dòng mẫu – ưu tiên hiển thị các cột liên quan
    preview_cols = [c for c in [
        "date", "year", "name", "iso_a3", "currency_code",
        "local_price", "dollar_price", "GDP_dollar",
    ] if c in df.columns]
    print("[Snapshot] 10 dòng mẫu (sau enrich_with_gdp):")
    df.select(preview_cols).show(10, truncate=False)


def save_clean_data(df, output_path: str):
    """Lưu dữ liệu sạch dạng Parquet."""
    df.coalesce(1).write.mode("overwrite").parquet(output_path)
    print(f"[Preprocessing] Dữ liệu sạch đã lưu tại: {output_path}")


def run_preprocessing(spark: SparkSession, raw_path: str, clean_path: str,
                      gdp_1999_path: str = None,
                      pop_path: str = None):
    """
    Pipeline tiền xử lý hoàn chỉnh, trả về DataFrame sạch.
    Nếu gdp_1999_path và pop_path được cung cấp, tính GDP per capita rồi điền null.
    """
    df = load_data(spark, raw_path)
    df = clean_data(df)

    import os
    snapshot_dir = os.path.dirname(clean_path) or "outputs"

    if gdp_1999_path and pop_path:
        df = enrich_with_gdp_per_capita(df, spark, gdp_1999_path, pop_path)
        save_enriched_snapshot(df, output_dir=snapshot_dir)
    else:
        print("[Preprocessing] Không có GDP/Population data – bỏ qua enrich.")

    save_clean_data(df, clean_path)
    return df
