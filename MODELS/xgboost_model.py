import pandas as pd
import pymysql
from xgboost import XGBRegressor
from sklearn.model_selection import GridSearchCV, KFold
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import joblib
import os

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
train_sales = pd.read_sql("SELECT * FROM random_train_sales", conn)
test_sales = pd.read_sql("SELECT * FROM random_test_sales", conn)
dist = pd.read_sql("SELECT * FROM distribution_channel", conn)
product = pd.read_sql("SELECT * FROM product", conn)
sales_weekly = pd.read_sql("SELECT * FROM sales_weekly", conn)

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
# 4️⃣ JOIN
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
test_df = prepare_data(test_sales)
print(f"Train: {train_df.shape[0]} dòng | Test: {test_df.shape[0]} dòng")

# ==============================
# 5️⃣ CHỌN FEATURE
# ==============================
categorical_cols = [
    'region_enc', 'urbanization_enc', 'price_group_enc',
    'brand_name_enc', 'product_group_enc', 'distribution_channel_code_enc'
]
numeric_cols = [
    'net_price', 'cost_price', 'margin', 'discount_rate',
    'month', 'year_num', 'quarter', 'promo_flag', 'holiday_flag',
    'stock_flag', 'avg_weekly_sales'
]
target = 'sold_quantity'
existing_features = [c for c in categorical_cols + numeric_cols if c in train_df.columns]

train_model = train_df[existing_features + [target]].dropna(subset=[target])
test_model = test_df[existing_features + [target]].dropna(subset=[target])

for col in numeric_cols:
    if col in train_model.columns:
        train_model[col] = pd.to_numeric(train_model[col], errors='coerce')
        test_model[col] = pd.to_numeric(test_model[col], errors='coerce')

train_model = train_model.replace([np.inf, -np.inf], np.nan).fillna(0)
test_model = test_model.replace([np.inf, -np.inf], np.nan).fillna(0)

X_train, y_train = train_model[existing_features], train_model[target]
X_test, y_test = test_model[existing_features], test_model[target]
print(f"Dữ liệu train: {X_train.shape[0]} | test: {X_test.shape[0]}")

# ==============================
# 6️⃣ GRID SEARCH + K-FOLD
# ==============================
cv = KFold(n_splits=5, shuffle=True, random_state=42)
param_grid = {
    'n_estimators': [100, 300],
    'max_depth': [5, 10],
    'learning_rate': [0.05, 0.1]
}

def tune_model(model, name):
    print(f"\nĐang train {name} với GridSearch + KFold ...")
    grid = GridSearchCV(
        estimator=model,
        param_grid={k: v for k, v in param_grid.items() if k in model.get_params()},
        scoring='neg_mean_squared_error',
        cv=cv,
        n_jobs=-1
    )
    grid.fit(X_train, y_train)
    print(f"Best params {name}: {grid.best_params_}")
    return grid.best_estimator_

xgb_best = tune_model(XGBRegressor(random_state=42, eval_metric='rmse'), "XGBoost")

# ==============================
# 7️⃣ LƯU MÔ HÌNH ỔN ĐỊNH
# ==============================
save_path = os.path.join(os.path.dirname(__file__), "xgboost_best.pkl")
joblib.dump(xgb_best, save_path)
print(f"✅ Model saved successfully at: {save_path}")

# ==============================
# 8️⃣ ĐÁNH GIÁ
# ==============================
def evaluate_model(model, name):
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)
    r2 = r2_score(y_test, y_pred)
    n, p = len(y_test), X_test.shape[1]
    r2_adj = 1 - (1 - r2) * (n - 1) / (n - p - 1)
    mape = np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1e-8))) * 100
    AIC = n * np.log(mse) + 2 * p
    BIC = n * np.log(mse) + p * np.log(n)

    print(f"\nHiệu năng mô hình ({name}):")
    print(f"MAE   : {mae:.4f}")
    print(f"MSE   : {mse:.4f}")
    print(f"RMSE  : {rmse:.4f}")
    print(f"R²    : {r2:.4f}")
    print(f"R²adj : {r2_adj:.4f}")
    print(f"MAPE  : {mape:.2f}%")
    print(f"AIC   : {AIC:.2f}")
    print(f"BIC   : {BIC:.2f}")
    return y_pred

y_train_pred = xgb_best.predict(X_train)
y_test_pred = evaluate_model(xgb_best, "XGBoost")

# ==============================
# 9️⃣ FORECAST
# ==============================
X_forecast = X_test.copy()
X_forecast["promo_flag"] = 0
X_forecast["discount_rate"] = 0
y_forecast_pred = xgb_best.predict(X_forecast)

# ==============================
# 🔟 BIỂU ĐỒ TRAIN–TEST–FORECAST
# ==============================
timeline = list(range(len(y_train_pred) + len(y_test_pred) + len(y_forecast_pred)))

fig = go.Figure()
fig.add_trace(go.Scatter(x=timeline[:len(y_train_pred)], y=y_train_pred, mode='lines', name='Train', line=dict(color='green')))
fig.add_trace(go.Scatter(x=timeline[len(y_train_pred):len(y_train_pred)+len(y_test_pred)], y=y_test_pred, mode='lines', name='Test', line=dict(color='orange')))
fig.add_trace(go.Scatter(x=timeline[len(y_train_pred)+len(y_test_pred):], y=y_forecast_pred, mode='lines', name='Forecast', line=dict(color='blue', dash='dot')))
fig.update_layout(title="Train – Test – Forecast (XGBoost)", xaxis_title="Index / Time", yaxis_title="Predicted Sales Quantity", template="plotly_white")
fig.show()

# ==============================
# 1️⃣1️⃣ FEATURE IMPORTANCE
# ==============================
importance = pd.DataFrame({
    'Feature': X_train.columns,
    'Importance': xgb_best.feature_importances_
}).sort_values('Importance', ascending=False)

print("\nTop 10 Feature quan trọng nhất (XGBoost):")
print(importance.head(10))

fig_imp = px.bar(
    importance.head(10),
    x='Importance',
    y='Feature',
    orientation='h',
    title='Top 10 Feature Quan Trọng Nhất (XGBoost)',
    text='Importance'
)
fig_imp.update_traces(texttemplate='%{text:.2f}', textposition='outside')
fig_imp.update_layout(yaxis=dict(autorange="reversed"), template='plotly_white')
fig_imp.show()