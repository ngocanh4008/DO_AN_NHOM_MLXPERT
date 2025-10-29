import pandas as pd
import pymysql
import numpy as np
import joblib
import os
import warnings
warnings.filterwarnings("ignore")

from prophet import Prophet
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import plotly.graph_objects as go
import matplotlib.pyplot as plt

# ==============================
# 1️⃣ KẾT NỐI MYSQL
# ==============================
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='@Obama123',
    database='mlxpert_retail',
    charset='utf8mb4'
)

# ==============================
# 2️⃣ ĐỌC DỮ LIỆU
# ==============================
train_sales = pd.read_sql("SELECT * FROM timeseries_train_sales", conn)
test_sales  = pd.read_sql("SELECT * FROM timeseries_test_sales",  conn)
dist        = pd.read_sql("SELECT * FROM distribution_channel", conn)
product     = pd.read_sql("SELECT * FROM product",            conn)
sales_weekly= pd.read_sql("SELECT * FROM sales_weekly",       conn)

# ==============================
# 3️⃣ XỬ LÝ WEEKLY
# ==============================
weekly_agg = (
    sales_weekly
    .groupby("product_id", as_index=False)
    .agg({"sold_quantity": "mean", "rolling_mean_4w": "mean"})
    .rename(columns={"sold_quantity": "avg_weekly_sales"})
)
weekly_agg["inventory_quantity"] = np.nan

# ==============================
# 4️⃣ JOIN + FEATURE ENGINEERING
# ==============================
def prepare_data(sales_df):
    df = (
        sales_df
        .merge(dist, left_on='distribution_channel_code', right_on='site_store', how='left', suffixes=('', '_dist'))
        .merge(product, on='product_id', how='left', suffixes=('', '_prod'))
        .merge(weekly_agg, on='product_id', how='left', suffixes=('', '_weekly'))
    )

    if 'net_price' in df.columns and 'listing_price' in df.columns:
        df['discount_rate'] = (df['listing_price'] - df['net_price']) / df['listing_price']
    else:
        df['discount_rate'] = 0

    if 'net_price' in df.columns and 'cost_price' in df.columns:
        df['margin'] = df['net_price'] - df['cost_price']
    else:
        df['margin'] = 0

    if 'sold_quantity' in df.columns:
        df['stock_flag'] = np.where(df['sold_quantity'] > 0, 1, 0)
    else:
        df['stock_flag'] = 0

    return df.fillna(0)

train_df = prepare_data(train_sales)
test_df  = prepare_data(test_sales)
print(f"Train: {train_df.shape[0]} dòng | Test: {test_df.shape[0]} dòng")

# ==============================
# 5️⃣ CHỌN FEATURE
# ==============================
numeric_cols = [
    'net_price', 'cost_price', 'margin', 'discount_rate',
    'month', 'year_num', 'quarter', 'promo_flag', 'holiday_flag',
    'stock_flag', 'avg_weekly_sales'
]
target = 'sold_quantity'

# ==============================
# 6️⃣ XỬ LÝ NGÀY & DỮ LIỆU SỐ
# ==============================
def resolve_datetime(df):
    if {'year_num', 'month'}.issubset(df.columns):
        df['year_num'] = df['year_num'].astype(str).str[:4]
        df['month'] = pd.to_numeric(df['month'], errors='coerce').fillna(1).astype(int).clip(1, 12)
        return pd.to_datetime(df['year_num'] + '-' + df['month'].astype(str) + '-01', errors='coerce')
    return pd.date_range('2020-01-01', periods=len(df), freq='W')

for col in numeric_cols:
    if col in train_df.columns:
        train_df[col] = pd.to_numeric(train_df[col], errors='coerce')
    if col in test_df.columns:
        test_df[col] = pd.to_numeric(test_df[col], errors='coerce')

train_df = train_df.replace([np.inf, -np.inf], np.nan).fillna(0)
test_df  = test_df.replace([np.inf, -np.inf], np.nan).fillna(0)

# ==============================
# 7️⃣ TẠO TẬP DỮ LIỆU PROPHET
# ==============================
regressors = [
    'discount_rate', 'promo_flag', 'holiday_flag', 'margin',
    'avg_weekly_sales', 'net_price', 'cost_price', 'stock_flag', 'quarter'
]
regressors = [c for c in regressors if c in train_df.columns and c in test_df.columns]

train_ds = resolve_datetime(train_df)
test_ds  = resolve_datetime(test_df)
train_y = train_df[target].astype(float)
test_y  = test_df[target].astype(float)

prophet_train = pd.DataFrame({'ds': train_ds, 'y': train_y})
prophet_test  = pd.DataFrame({'ds': test_ds,  'y': test_y})
for col in regressors:
    prophet_train[col] = train_df[col].values
    prophet_test[col]  = test_df[col].values

# ==============================
# 8️⃣ TRAIN PROPHET
# ==============================
m = Prophet(
    yearly_seasonality=True,
    weekly_seasonality=False,
    daily_seasonality=False,
    seasonality_mode='additive',
    uncertainty_samples=0  # 🚀 Tắt sampling để tránh lỗi RAM
)
for col in regressors:
    m.add_regressor(col)
m.fit(prophet_train)

# ==============================
# 9️⃣ HÀM DỰ ĐOÁN CHIA LÔ
# ==============================
def predict_in_chunks(model, df, chunk_size=20000):
    out = []
    for i in range(0, len(df), chunk_size):
        out.append(model.predict(df.iloc[i:i+chunk_size]))
    return pd.concat(out, ignore_index=True)

# ==============================
# 🔟 DỰ ĐOÁN TRÊN TEST & FORECAST
# ==============================
future_test = prophet_test[['ds'] + regressors].copy()
y_test_pred_df = predict_in_chunks(m, future_test, chunk_size=20000)

future_forecast = future_test.copy()
if 'promo_flag' in future_forecast.columns:
    future_forecast['promo_flag'] = 0
if 'discount_rate' in future_forecast.columns:
    future_forecast['discount_rate'] = 0.0
y_forecast_df = predict_in_chunks(m, future_forecast, chunk_size=20000)

# ==============================
# 1️⃣1️⃣ LƯU MODEL
# ==============================
save_path = os.path.join(os.path.dirname(__file__), "prophet_best.pkl")
joblib.dump(m, save_path)
print(f"✅ Model Prophet đã lưu tại: {save_path}")

# ==============================
# 1️⃣2️⃣ ĐÁNH GIÁ
# ==============================
y_pred = y_test_pred_df['yhat'].values
mse  = mean_squared_error(test_y, y_pred)
rmse = np.sqrt(mse)
mae  = mean_absolute_error(test_y, y_pred)
r2   = r2_score(test_y, y_pred)
n, p = len(test_y), len(regressors) if len(regressors) > 0 else 1
r2_adj = 1 - (1 - r2) * (n - 1) / (n - p - 1) if n - p - 1 > 0 else r2
mape = np.mean(np.abs((test_y - y_pred) / np.maximum(test_y, 1e-8))) * 100
AIC  = n * np.log(mse) + 2 * p
BIC  = n * np.log(mse) + p * np.log(n)

print("\n🎯 Hiệu năng mô hình (Prophet + Regressors):")
print(f"MAE   : {mae:.4f}")
print(f"MSE   : {mse:.4f}")
print(f"RMSE  : {rmse:.4f}")
print(f"R²    : {r2:.4f}")
print(f"R²adj : {r2_adj:.4f}")
print(f"MAPE  : {mape:.2f}%")
print(f"AIC   : {AIC:.2f}")
print(f"BIC   : {BIC:.2f}")

# ==============================
# 1️⃣4️⃣ TRAIN–TEST–FORECAST (Plotly)
# ==============================
y_train_fit = predict_in_chunks(m, prophet_train[['ds'] + regressors], chunk_size=20000)['yhat'].values
timeline = list(range(len(y_train_fit) + len(y_pred) + len(y_forecast_df)))

fig = go.Figure()
fig.add_trace(go.Scatter(x=timeline[:len(y_train_fit)], y=y_train_fit, mode='lines', name='Train'))
fig.add_trace(go.Scatter(x=timeline[len(y_train_fit):len(y_train_fit)+len(y_pred)], y=y_pred, mode='lines', name='Test'))
fig.add_trace(go.Scatter(x=timeline[len(y_train_fit)+len(y_pred):], y=y_forecast_df['yhat'].values, mode='lines', name='Forecast (promo=0, discount=0)', line=dict(dash='dot')))
fig.update_layout(title="Train – Test – Forecast (Prophet + Regressors)", xaxis_title="Index / Time", yaxis_title="Predicted Sales Quantity", template="plotly_white")
fig.show()
