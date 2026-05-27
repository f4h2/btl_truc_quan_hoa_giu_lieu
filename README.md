# Big Mac Index – Phân tích dữ liệu với Apache Spark

Dự án thực hiện **Preprocessing**, **EDA**, **Linear Regression** và **Trực quan hóa dữ liệu**
cho bộ dữ liệu *Big Mac Index* của The Economist, sử dụng **Apache Spark (PySpark)**.

---

## Mục lục

1. [Giới thiệu dataset](#1-giới-thiệu-dataset)
2. [Cấu trúc dự án](#2-cấu-trúc-dự-án)
3. [Cài đặt môi trường](#3-cài-đặt-môi-trường)
4. [Tải dataset](#4-tải-dataset)
5. [Cách chạy](#5-cách-chạy)
6. [Giải thích từng bước](#6-giải-thích-từng-bước)
7. [Kết quả đầu ra](#7-kết-quả-đầu-ra)
8. [Phân tích & nhận xét](#8-phân-tích--nhận-xét)

---

## 1. Giới thiệu dataset

| Thuộc tính | Thông tin |
|---|---|
| Nguồn | [Kaggle – Big Mac Index Data](https://www.kaggle.com/datasets/mrmorj/big-mac-index-data) |
| File | `big mac.csv` (~181 KB) |
| Số cột | 19 |
| Giấy phép | CC0 Public Domain |

### Các cột chính

| Cột | Ý nghĩa |
|---|---|
| `date` | Ngày khảo sát |
| `iso_a3` | Mã quốc gia (ISO 3 ký tự) |
| `currency_code` | Mã tiền tệ |
| `name` | Tên quốc gia |
| `local_price` | Giá Big Mac bằng tiền địa phương |
| `dollar_ex` | Tỉ giá hối đoái so với USD |
| `dollar_price` | Giá Big Mac quy đổi sang USD |
| `USD_raw` | Chỉ số Big Mac thô so với USD (%) |
| `GDP_dollar` | GDP bình quân đầu người (USD) |
| `adj_price` | Giá điều chỉnh theo GDP |
| `USD_adjusted` | Chỉ số điều chỉnh theo GDP so với USD |

---

## 2. Cấu trúc dự án

```
btl_truc_quan_hoa/
│
├── data/                        ← Đặt file CSV vào đây
│   └── big mac.csv
│
├── src/
│   ├── preprocessing.py         ← Tiền xử lý dữ liệu
│   ├── eda.py                   ← Phân tích khám phá (EDA)
│   ├── regression.py            ← Hồi quy tuyến tính (MLlib)
│   └── visualization.py        ← Vẽ biểu đồ (matplotlib/seaborn)
│
├── outputs/                     ← Kết quả tự động tạo ra sau khi chạy
│   ├── clean_data.parquet
│   ├── regression_metrics.json
│   ├── bar_top15_highest_price.png
│   ├── bar_top15_lowest_price.png
│   ├── line_avg_price_by_year.png
│   ├── hist_dollar_price.png
│   ├── scatter_gdp_vs_price.png
│   ├── heatmap_corr.png
│   ├── boxplot_price_by_year.png
│   ├── line_usa_price.png
│   ├── scatter_actual_vs_pred.png
│   └── residual_plot.png
│
├── main.py                      ← Entry point chạy toàn bộ pipeline
├── requirements.txt
└── README.md
```

---

## 3. Cài đặt môi trường

### Yêu cầu hệ thống
- Python ≥ 3.8
- Java ≥ 8 (bắt buộc để chạy Spark)

### Kiểm tra Java

```bash
java -version
```

Nếu chưa có Java:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y default-jdk

# macOS (homebrew)
brew install openjdk@11
```

### Tạo virtual environment & cài thư viện

```bash
# Tạo venv
python -m venv .venv

# Kích hoạt (Linux/macOS)
source .venv/bin/activate

# Kích hoạt (Windows)
.venv\Scripts\activate

# Cài dependencies
pip install -r requirements.txt
```

---

## 4. Tải dataset

### Cách A – Tự động (khuyến nghị)

`main.py` sẽ **tự động tải dataset qua `kagglehub`** nếu file chưa tồn tại.
Chỉ cần đảm bảo đã cấu hình Kaggle API credentials:

```bash
# Cài kagglehub (đã có trong requirements.txt)
pip install kagglehub

# Lần đầu chạy, kagglehub sẽ yêu cầu đăng nhập Kaggle
# Tạo API token tại: https://www.kaggle.com/settings → API → Create New Token
# Đặt file kaggle.json vào ~/.kaggle/kaggle.json
mkdir -p ~/.kaggle
mv ~/Downloads/kaggle.json ~/.kaggle/
chmod 600 ~/.kaggle/kaggle.json
```

Sau đó chạy thẳng `python main.py` – dataset sẽ tự tải và copy vào `data/`.

### Cách B – Tải thủ công

1. Truy cập: https://www.kaggle.com/datasets/mrmorj/big-mac-index-data
2. Đăng nhập Kaggle → nhấn **Download**
3. Giải nén, đổi tên file thành `big mac.csv`
4. Đặt vào thư mục `data/`:

```
btl_truc_quan_hoa/
└── data/
    └── big mac.csv
```

---

## 5. Cách chạy

### Chạy pipeline đầy đủ (khuyến nghị)

```bash
python main.py
```

### Chỉ định đường dẫn CSV tùy chỉnh

```bash
python main.py --data /đường/dẫn/tới/big_mac.csv
```

### Chạy từng module riêng lẻ (để kiểm tra)

```bash
# Preprocessing
python -c "
import sys; sys.path.insert(0,'src')
from preprocessing import create_spark_session, run_preprocessing
spark = create_spark_session()
run_preprocessing(spark, 'data/big mac.csv', 'outputs/clean_data.parquet')
spark.stop()
"
```

### Xem kết quả biểu đồ

Sau khi chạy xong, toàn bộ biểu đồ nằm trong thư mục `outputs/`:
```bash
ls outputs/*.png
```

Mở xem trực tiếp (Linux):
```bash
eog outputs/          # Eye of GNOME
# hoặc
xdg-open outputs/line_avg_price_by_year.png
```

---

## 6. Giải thích từng bước

### Bước 1 – Preprocessing (`src/preprocessing.py`)

| Thao tác | Chi tiết |
|---|---|
| Đọc dữ liệu | `spark.read.csv()` với `header=True`, `inferSchema=True` |
| Chuẩn hóa tên cột | Loại bỏ khoảng trắng, dấu gạch ngang |
| Ép kiểu | Các cột số → `DoubleType`; `date` → `DateType` |
| Trích xuất năm | `F.year(col("date"))` → cột `year` |
| Xử lý null | Dropout theo cột `local_price`, `dollar_price`, `dollar_ex`; fillna GDP bằng median |
| Lưu kết quả | Parquet tại `outputs/clean_data.parquet` |

### Bước 2 – EDA (`src/eda.py`)

| Phân tích | Mô tả |
|---|---|
| Thống kê mô tả | `df.describe()` cho các cột số |
| Tổng quan | Số quốc gia, khoảng năm, số bản ghi |
| Top quốc gia | `groupBy + avg` sắp xếp giảm/tăng dần |
| Giá theo năm | `groupBy year + avg/min/max` |
| Phân phối giá | Bucket theo $1 USD |
| Tương quan | `df.stat.corr("GDP_dollar", "dollar_price")` |
| Kiểm tra null | Đếm null từng cột |

### Bước 3 – Linear Regression (`src/regression.py`)

**Mục tiêu:** Dự đoán `dollar_price` (giá Big Mac bằng USD)

**Đặc trưng sử dụng:**
- `GDP_dollar` – GDP bình quân đầu người
- `dollar_ex` – Tỉ giá hối đoái
- `year` – Năm

**Pipeline MLlib:**
```
VectorAssembler → StandardScaler → LinearRegression
```

| Tham số | Giá trị |
|---|---|
| Train/Test split | 80% / 20% |
| Seed | 42 |
| maxIter | 100 |
| regParam | 0.1 (Ridge regularization) |
| elasticNetParam | 0.0 |

**Metrics đánh giá:** RMSE, R², MAE

### Bước 4 – Visualization (`src/visualization.py`)

| File | Biểu đồ |
|---|---|
| `bar_top15_highest_price.png` | Top 15 quốc gia giá cao nhất (bar chart ngang) |
| `bar_top15_lowest_price.png` | Top 15 quốc gia giá thấp nhất |
| `line_avg_price_by_year.png` | Giá TB toàn cầu theo năm với dải min-max |
| `hist_dollar_price.png` | Histogram + KDE phân phối giá |
| `scatter_gdp_vs_price.png` | Scatter GDP vs giá kèm đường hồi quy |
| `heatmap_corr.png` | Heatmap tương quan các biến số |
| `boxplot_price_by_year.png` | Boxplot phân phối giá theo từng năm |
| `line_usa_price.png` | Xu hướng lịch sử giá tại Mỹ |
| `scatter_actual_vs_pred.png` | Giá thực tế vs dự đoán (kết quả regression) |
| `residual_plot.png` | Phân tích phần dư (residual analysis) |

---

## 7. Kết quả đầu ra

Sau khi chạy `main.py`, thư mục `outputs/` chứa:

```
outputs/
├── clean_data.parquet/          ← Dữ liệu sạch (dạng Parquet)
├── regression_metrics.json      ← RMSE, R², MAE, coefficients
└── *.png                        ← 10 biểu đồ trực quan
```

**Nội dung `regression_metrics.json`:**
```json
{
  "rmse": 0.xxxx,
  "r2": 0.xxxx,
  "mae": 0.xxxx,
  "intercept": x.xxxx,
  "coefficients": {
    "GDP_dollar": x.xxxxxx,
    "dollar_ex": x.xxxxxx,
    "year": x.xxxxxx
  }
}
```

---

## 8. Phân tích & nhận xét

### Big Mac Index là gì?

Big Mac Index được The Economist giới thiệu năm 1986 như một thước đo **Purchasing Power Parity (PPP)** – sức mua tương đương giữa các quốc gia. Ý tưởng: cùng một sản phẩm tiêu chuẩn (Big Mac) được bán ở khắp thế giới, nếu tỉ giá hối đoái phản ánh đúng PPP thì giá tính bằng USD phải như nhau ở mọi nơi.

### Các nhận xét kỳ vọng

1. **Xu hướng tăng theo thời gian:** Giá Big Mac USD tăng đều qua các năm do lạm phát toàn cầu.

2. **Tương quan GDP – Giá:** Quốc gia có GDP cao hơn thường có giá Big Mac đắt hơn (Pearson r ≈ 0.6–0.8), vì chi phí lao động và vận hành cao hơn.

3. **Biến động tỉ giá:** `dollar_ex` ảnh hưởng lớn đến `dollar_price` – khi đồng nội tệ mất giá, Big Mac tính USD rẻ hơn.

4. **Kết quả hồi quy:** R² dự kiến khoảng 0.5–0.7 với 3 đặc trưng. Residuals có thể không hoàn toàn ngẫu nhiên do thiếu đặc trưng lạm phát địa phương.

5. **Outliers:** Thụy Sĩ, Na Uy, Đan Mạch thường xuất hiện ở top giá cao nhất; Ukraina, Pakistan, Ai Cập ở nhóm thấp nhất.

### Mở rộng

- Thêm đặc trưng: tỉ lệ lạm phát, dân số, vùng địa lý (one-hot encoding)
- Thử mô hình phi tuyến: Random Forest, Gradient Boosting (Spark MLlib)
- Phân tích time-series: dự đoán giá Big Mac tương lai bằng ARIMA hoặc Prophet
