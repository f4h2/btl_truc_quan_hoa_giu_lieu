"""
regression.py
-------------
Hồi quy tuyến tính (Linear Regression) dự đoán dollar_price
bằng PySpark MLlib.

Đặc trưng (features):
  - GDP_dollar      : GDP bình quân đầu người (USD)
  - dollar_ex       : Tỉ giá hối đoái so với USD
  - year            : Năm

Mục tiêu (label):
  - dollar_price : Giá Big Mac quy đổi sang USD
"""

from pyspark.sql import functions as F
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.regression import LinearRegression
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml import Pipeline
import os, json


def run_regression(df, output_dir: str = "outputs"):
    """
    Huấn luyện Linear Regression và in kết quả.
    Trả về (model, predictions_df, metrics_dict).
    """
    print("\n" + "=" * 60)
    print("  LINEAR REGRESSION")
    print("=" * 60)

    feature_cols = [c for c in ["GDP_dollar", "dollar_ex", "year"] if c in df.columns]
    label_col = "dollar_price"

    # Bỏ các dòng thiếu feature hoặc label
    model_df = df.select(feature_cols + [label_col]).dropna()
    print(f"[Regression] Số dòng dùng để train/test: {model_df.count()}")
    print(f"[Regression] Features: {feature_cols}")

    # Train / Test split (80 / 20)
    train_df, test_df = model_df.randomSplit([0.8, 0.2], seed=42)
    print(f"[Regression] Train: {train_df.count()} | Test: {test_df.count()}")

    # Pipeline: VectorAssembler → StandardScaler → LinearRegression
    assembler = VectorAssembler(inputCols=feature_cols, outputCol="features_raw")
    scaler = StandardScaler(inputCol="features_raw", outputCol="features",
                            withMean=True, withStd=True)
    lr = LinearRegression(
        featuresCol="features",
        labelCol=label_col,
        maxIter=100,
        regParam=0.1,
        elasticNetParam=0.0,
    )
    pipeline = Pipeline(stages=[assembler, scaler, lr])

    # Huấn luyện
    model = pipeline.fit(train_df)

    # Dự đoán
    predictions = model.transform(test_df)

    # Đánh giá
    evaluator_rmse = RegressionEvaluator(labelCol=label_col, predictionCol="prediction",
                                         metricName="rmse")
    evaluator_r2 = RegressionEvaluator(labelCol=label_col, predictionCol="prediction",
                                        metricName="r2")
    evaluator_mae = RegressionEvaluator(labelCol=label_col, predictionCol="prediction",
                                         metricName="mae")

    rmse = evaluator_rmse.evaluate(predictions)
    r2   = evaluator_r2.evaluate(predictions)
    mae  = evaluator_mae.evaluate(predictions)

    # Hệ số hồi quy
    lr_model = model.stages[-1]
    coef_dict = dict(zip(feature_cols, [float(c) for c in lr_model.coefficients]))
    intercept = float(lr_model.intercept)

    print("\n[Regression] Kết quả mô hình:")
    print(f"  RMSE      : {rmse:.4f}")
    print(f"  R²        : {r2:.4f}")
    print(f"  MAE       : {mae:.4f}")
    print(f"  Intercept : {intercept:.4f}")
    print("  Coefficients:")
    for feat, coef in coef_dict.items():
        print(f"    {feat:<20}: {coef:.6f}")

    print("\n[Regression] Mẫu dự đoán (10 dòng đầu):")
    predictions.select(feature_cols + [label_col, "prediction"]).show(10, truncate=False)

    # Lưu metrics ra file JSON
    os.makedirs(output_dir, exist_ok=True)
    metrics = {
        "rmse": rmse, "r2": r2, "mae": mae,
        "intercept": intercept,
        "coefficients": coef_dict,
    }
    metrics_path = os.path.join(output_dir, "regression_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"[Regression] Metrics đã lưu tại: {metrics_path}")

    print("=" * 60)
    return model, predictions, metrics
