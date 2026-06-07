# Big Mac Index – Phân tích & Trực quan hóa dữ liệu

Dự án sử dụng **PySpark** để xử lý và phân tích bộ dữ liệu Big Mac Index kết hợp với dữ liệu GDP và dân số thế giới, nhằm khám phá mối quan hệ giữa giá cả, tỉ giá hối đoái và mức sống theo từng quốc gia, từng năm.

---

## Cấu trúc dự án

```
btl_truc_quan_hoa/
├── main.py                              # Pipeline chính
├── requirements.txt
├── data/
│   ├── big mac.csv                      # Dữ liệu Big Mac Index
│   ├── GDP by Country 1999-2022.csv     # Tổng GDP quốc gia (tỷ USD)
│   └── world_population.csv             # Dân số thế giới theo năm
├── src/
│   ├── preprocessing.py      # Tiền xử lý & enrich dữ liệu
│   ├── eda.py                # Phân tích khám phá (EDA)
│   ├── regression.py         # Hồi quy tuyến tính
│   └── visualization.py      # Vẽ biểu đồ
└── outputs/                  # Kết quả: biểu đồ PNG, metrics JSON, snapshot CSV
```

---

## Datasets sử dụng

### 1. Big Mac Index (`big mac.csv`)
- **Nguồn**: [The Economist – Big Mac Index](https://www.kaggle.com/datasets/mrmorj/big-mac-index-data)
- **Mô tả**: Giá bánh Big Mac tại hơn 50 quốc gia, ghi nhận từ năm 2000 đến 2022, khoảng 2 lần/năm.
- **Các cột chính**:

| Cột | Ý nghĩa |
|---|---|
| `date` | Ngày khảo sát |
| `iso_a3` | Mã quốc gia ISO 3 ký tự |
| `name` | Tên quốc gia |
| `local_price` | Giá Big Mac theo tiền tệ địa phương |
| `dollar_ex` | Tỉ giá hối đoái so với USD |
| `dollar_price` | Giá Big Mac quy đổi sang USD |
| `USD_raw` | Chỉ số định giá thô so với USD (> 0: đắt hơn, < 0: rẻ hơn) |
| `GDP_dollar` | GDP bình quân đầu người (USD) – ban đầu có nhiều giá trị null |
| `adj_price` | Giá điều chỉnh theo GDP |

---

### 2. GDP by Country 1999–2022 (`GDP by Country 1999-2022.csv`)
- **Nguồn**: [Kaggle – alejopaullier/-gdp-by-country-1999-2022](https://www.kaggle.com/datasets/alejopaullier/-gdp-by-country-1999-2022)
- **Mô tả**: Tổng GDP hàng năm của từng quốc gia từ 1999 đến 2022, đơn vị **tỷ USD** (billions USD).
- **Định dạng**: Wide format – mỗi hàng là 1 quốc gia, mỗi cột là 1 năm.

---

### 3. World Population (`world_population.csv`)
- **Nguồn**: [Kaggle – iamsouravbanerjee/world-population-dataset](https://www.kaggle.com/datasets/iamsouravbanerjee/world-population-dataset)
- **Mô tả**: Dân số của từng quốc gia tại các năm snapshot: 1970, 1980, 1990, 2000, 2010, 2015, 2020, 2022.
- **Cột quan trọng**: `CCA3` (mã ISO 3 ký tự), `2022 Population`, `2020 Population`, v.v.

---

## Xử lý dữ liệu

### Bước 1 – Làm sạch Big Mac (`clean_data`)
1. **Chuẩn hoá tên cột**: xoá khoảng trắng, thay `-` và space thành `_`.
2. **Ép kiểu**: các cột số được cast sang `DoubleType`; cột `date` sang `DateType`.
3. **Trích xuất năm**: thêm cột `year` từ `date`.
4. **Xoá dòng thiếu**: bỏ các dòng null tại các cột quan trọng `local_price`, `dollar_price`, `dollar_ex`.

### Bước 2 – Tính GDP per capita và điền null (`enrich_with_gdp_per_capita`)

Cột `GDP_dollar` trong Big Mac có rất nhiều giá trị null (đặc biệt các năm đầu). Quy trình điền giá trị:

#### 2a – Chuyển GDP sang long format
File `GDP by Country 1999-2022.csv` ở dạng wide được **unpivot** thành:
```
(country_name, year, gdp_billions)
```

#### 2b – Hồi quy tuyến tính dân số (per country)
File dân số chỉ có dữ liệu tại 8 năm snapshot (1970, 1980, …, 2022). Với mỗi quốc gia, dùng **`numpy.polyfit` bậc 1** (linear regression) trên các snapshot để ước lượng dân số cho **mọi năm từ 1999 đến 2022**:

$$\text{population\_est}(y) = \alpha \cdot y + \beta$$

#### 2c – Tính GDP per capita
$$\text{GDP\_dollar} = \frac{\text{gdp\_billions} \times 10^9}{\text{population\_est}}$$

#### 2d – Join và điền null
- Join Big Mac `(iso_a3, year)` với bảng GDP per capita `(country_name → iso_a3, year)`.
- Tên quốc gia trong GDP 1999 được ánh xạ sang `iso_a3` qua bảng tham chiếu lấy từ chính Big Mac.
- Chỉ điền khi `GDP_dollar` đang **null** (`coalesce(GDP_dollar, gdp_per_capita)`), giữ nguyên giá trị cũ nếu đã có.

### Bước 3 – EDA (`eda.py`)
- Thống kê mô tả các cột số.
- Thống kê số quốc gia, khoảng thời gian.
- Top 10 quốc gia giá cao nhất / thấp nhất.
- Giá trung bình toàn cầu theo năm.
- Phân phối `dollar_price`.
- Tương quan `GDP_dollar` – `dollar_price`.

### Bước 4 – Hồi quy tuyến tính (`regression.py`)
Dự đoán `dollar_price` từ các đặc trưng:

| Feature | Ý nghĩa |
|---|---|
| `GDP_dollar` | GDP bình quân đầu người |
| `dollar_ex` | Tỉ giá hối đoái |
| `year` | Năm |

Pipeline: `VectorAssembler → StandardScaler → LinearRegression`  
Tỉ lệ train/test: **80/20**. Metrics đánh giá: R², RMSE, MAE.

---

## Biểu đồ được tạo ra (15 biểu đồ)

### 1. `bar_top15_highest_price.png`
- **Loại**: Horizontal bar chart
- **Nội dung**: Top 15 quốc gia có giá Big Mac trung bình **cao nhất** (USD) trong toàn bộ lịch sử.
- **Tính chất**: So sánh trực tiếp giữa các quốc gia, màu đỏ gradient nhấn mạnh thứ hạng.

### 2. `bar_top15_lowest_price.png`
- **Loại**: Horizontal bar chart
- **Nội dung**: Top 15 quốc gia có giá Big Mac trung bình **thấp nhất**.
- **Tính chất**: Đối chiếu với biểu đồ #1, phản ánh sức mua và chi phí sinh hoạt thấp.

### 3. `line_avg_price_by_year.png`
- **Loại**: Line chart + vùng shading (min–max)
- **Nội dung**: Giá Big Mac USD trung bình toàn cầu theo từng năm, kèm dải min–max.
- **Tính chất**: Thể hiện xu hướng lạm phát giá theo thời gian và mức độ phân tán giữa các nước.

### 4. `hist_dollar_price.png`
- **Loại**: Histogram + KDE curve
- **Nội dung**: Phân phối giá Big Mac (USD) trên toàn bộ dataset.
- **Tính chất**: Cho thấy phần lớn giá tập trung ở mức nào; thường lệch phải (right-skewed) do một số nước rất đắt.

### 5. `scatter_gdp_vs_price.png`
- **Loại**: Scatter plot + đường hồi quy tuyến tính
- **Nội dung**: Mối quan hệ giữa GDP per capita và giá Big Mac (USD).
- **Tính chất**: Tương quan dương – nước giàu hơn thường có giá Big Mac cao hơn; đường đỏ thể hiện xu hướng; kiểm chứng lý thuyết PPP.

### 6. `heatmap_corr.png`
- **Loại**: Heatmap tương quan Pearson
- **Nội dung**: Ma trận tương quan giữa: `local_price`, `dollar_price`, `dollar_ex`, `USD_raw`, `GDP_dollar`, `adj_price`.
- **Tính chất**: Màu đỏ = tương quan dương mạnh, màu xanh = tương quan âm; giúp phát hiện multicollinearity trước khi hồi quy.

### 7. `boxplot_price_by_year.png`
- **Loại**: Box plot
- **Nội dung**: Phân phối giá Big Mac (USD) theo từng năm.
- **Tính chất**: Thể hiện median, tứ phân vị (IQR) và outlier từng năm; thấy rõ xu hướng giá tăng dần và sự mở rộng khoảng cách giữa các nước.

### 8. `line_usa_price.png`
- **Loại**: Line chart
- **Nội dung**: Xu hướng giá Big Mac tại **Mỹ (USD)** qua các kỳ khảo sát.
- **Tính chất**: Dùng làm mốc tham chiếu vì `USD_raw = 0` tại Mỹ; phản ánh lạm phát nội địa Mỹ theo thời gian.

### 9. `scatter_actual_vs_pred.png`
- **Loại**: Scatter plot
- **Nội dung**: Giá thực tế vs giá dự đoán từ mô hình Linear Regression.
- **Tính chất**: Điểm càng gần đường `y = x` (đường đỏ đứt) → mô hình càng chính xác; phát hiện bias hệ thống (over/under-predict).

### 10. `residual_plot.png`
- **Loại**: Scatter plot (phần dư)
- **Nội dung**: Phần dư (residual = thực tế − dự đoán) theo giá dự đoán.
- **Tính chất**: Phần dư ngẫu nhiên quanh 0 → giả định tuyến tính được thoả; nếu có cấu trúc hình phễu → phương sai không đồng nhất (heteroscedasticity).

### 11. `line_top_countries.png`
- **Loại**: Multi-line chart
- **Nội dung**: Xu hướng giá Big Mac theo năm của **top 10 quốc gia** có nhiều dữ liệu nhất.
- **Tính chất**: So sánh đồng thời nhiều quốc gia trên cùng trục thời gian; thể hiện sự phân kỳ/hội tụ giá giữa các nền kinh tế.

### 12. `bar_usd_raw_overvalued.png`
- **Loại**: Horizontal bar chart (hai màu đỏ/xanh)
- **Nội dung**: Chỉ số `USD_raw` trung bình của từng quốc gia – mức độ đắt/rẻ so với USD.
- **Tính chất**: **Đỏ** = đồng tiền định giá cao hơn USD (over-valued), **xanh** = định giá thấp hơn (under-valued); trực quan hoá lý thuyết Purchasing Power Parity (PPP).

### 13. `heatmap_price_country_year.png`
- **Loại**: Heatmap 2D (quốc gia × năm)
- **Nội dung**: Giá Big Mac (USD) trung bình theo **quốc gia × năm** (top 30 quốc gia).
- **Tính chất**: Màu vàng–đỏ = giá cao; dễ thấy quốc gia nào luôn đắt/rẻ và xu hướng tăng giá lan rộng theo thời gian trên toàn ma trận.

### 14. `scatter_gdp_vs_usdraw.png`
- **Loại**: Scatter plot (tô màu theo thập kỷ)
- **Nội dung**: GDP per capita vs chỉ số định giá `USD_raw`, phân nhóm theo thập kỷ.
- **Tính chất**: Kiểm tra xem nước giàu hơn có xu hướng định giá cao hơn không; màu sắc theo thập kỷ cho thấy sự dịch chuyển mẫu hình theo thời gian – liên quan đến hội tụ kinh tế.

### 15. `violin_price_by_decade.png`
- **Loại**: Violin plot
- **Nội dung**: Phân phối giá Big Mac (USD) theo từng **thập kỷ** (2000s, 2010s, 2020s).
- **Tính chất**: Kết hợp ưu điểm của box plot (median, IQR) và histogram (hình dạng phân phối); thể hiện rõ sự thay đổi của mật độ giá và độ trải rộng qua các thập kỷ.

---

## Cách chạy

```bash
# Cài đặt thư viện
pip install -r requirements.txt

# Chạy pipeline (tự động tải dataset nếu chưa có, cần kaggle API key)
python main.py

# Hoặc chỉ định file Big Mac thủ công
python main.py --data "data/big mac.csv"
```

> **Lưu ý**: Cần cấu hình Kaggle API (`~/.kaggle/kaggle.json`) để tự động tải dataset.

---

## Kết quả đầu ra (`outputs/`)

| File | Mô tả |
|---|---|
| `enriched_snapshot.csv` | Snapshot dữ liệu sau khi enrich GDP per capita |
| `enriched_snapshot.parquet` | Snapshot dạng Parquet để tái sử dụng nhanh |
| `clean_data.parquet` | Dữ liệu sạch cuối cùng dạng Parquet |
| `regression_metrics.json` | Chỉ số R², RMSE, MAE của mô hình hồi quy |
| `*.png` (15 file) | Toàn bộ biểu đồ trực quan hoá |



xdg-open choropleth_bigmac_index.html