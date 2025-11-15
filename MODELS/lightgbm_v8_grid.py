# ==========================================================
# File: lightgbm_v8_grid_feature_importance.py
# Purpose: Train LightGBM + show feature importance clearly
# ==========================================================

import pandas as pd
import numpy as np
import pymysql
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from lightgbm import LGBMRegressor
from scipy.ndimage import gaussian_filter1d
import plotly.express as px


# ====================== DB Connection ======================
def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="@Obama123",
        database="mlxpert_retail",
        charset="utf8mb4"
    )


# ====================== Load Data ======================
def load_data():
    conn = get_connection()
    sales = pd.read_sql("SELECT * FROM sales", conn)
    dist = pd.read_sql("SELECT * FROM distribution_channel", conn)
    product = pd.read_sql("SELECT * FROM product", conn)
    sales_weekly = pd.read_sql("SELECT * FROM sales_weekly", conn)
    conn.close()

    weekly_agg = (
        sales_weekly.groupby("product_id", as_index=False)
        .agg({"sold_quantity": "mean", "rolling_mean_4w": "mean"})
        .rename(columns={"sold_quantity": "avg_weekly_sales"})
    )
    return sales, dist, product, sales_weekly, weekly_agg


# ====================== Feature Engineering ======================
def prepare_data(sales_df, dist, product, sales_weekly, weekly_agg):
    dist = dist.drop_duplicates(subset=["channel_id"])
    product = product.drop_duplicates(subset=["product_id"])
    weekly_agg = weekly_agg.drop_duplicates(subset=["product_id"])

    df = (
        sales_df
        .merge(dist, on="channel_id", how="left")
        .merge(product, on="product_id", how="left")
        .merge(weekly_agg, on="product_id", how="left")
    ).fillna(0)

    df["margin"] = df["net_price"] - df["cost_price"]
    df["avg_price_per_product"] = df.groupby("product_id")["net_price"].transform("mean")
    df["price_relative"] = np.where(df["avg_price_per_product"] > 0, df["net_price"] / df["avg_price_per_product"], 1)
    df["log_price"] = np.log1p(df["net_price"])

    df = df.sort_values(["product_id", "week_num"])
    df["holiday_flag_soft"] = df.groupby("product_id")["holiday_flag"].transform(lambda x: gaussian_filter1d(x, sigma=1))

    scale_cols = ["net_price", "cost_price", "margin", "discount_rate", "avg_weekly_sales", "price_relative", "log_price"]
    scaler = MinMaxScaler()
    df[scale_cols] = scaler.fit_transform(df[scale_cols])
    return df


# ====================== Feature Selection ======================
def select_features(df):
    features = [
        "region_KVCA", "region_KVMB", "region_KVMT",
        "region_KVMTR", "region_KVTN", "region_KVMN", "region_Khac",
        "urbanization_Noi_thanh", "urbanization_Nong_thon",
        "urbanization_TT_hanh_chinh_kinh_te", "urbanization_Khac",
        "product_group_enc", "brand_name_enc", "price_group_enc",
        "net_price", "discount_rate", "margin",
        "avg_weekly_sales", "promo_flag", "price_relative",
        "holiday_flag_soft", "week_num"
    ]
    features = [f for f in features if f in df.columns]
    X = df[features]
    y = df["sold_quantity"]
    print(f"{len(features)} features selected.")
    return X, y, features


# ====================== Evaluation ======================
def evaluate(y_true, y_pred, X):
    mse = mean_squared_error(y_true, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    n, p = len(y_true), X.shape[1]
    r2_adj = 1 - (1 - r2) * (n - 1) / max(n - p - 1, 1)
    mape = np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1e-8))) * 100
    sse = np.sum((y_true - y_pred) ** 2)
    aic = n * np.log(sse / n) + 2 * p
    bic = n * np.log(sse / n) + np.log(n) * p
    print("\nHiệu năng mô hình:")
    print(f"MAE   : {mae:.4f}")
    print(f"RMSE  : {rmse:.4f}")
    print(f"R²    : {r2:.4f}")
    print(f"R²_adj: {r2_adj:.4f}")
    print(f"MAPE  : {mape:.2f}%")
    print(f"AIC   : {aic:.2f}")
    print(f"BIC   : {bic:.2f}")
    return {"MAE": mae, "RMSE": rmse, "R2": r2, "R2_adj": r2_adj, "MAPE": mape, "AIC": aic, "BIC": bic}


# ====================== Main ======================
if __name__ == "__main__":
    print("Loading data...")
    sales, dist, product, sales_weekly, weekly_agg = load_data()

    print("Preparing data...")
    df = prepare_data(sales, dist, product, sales_weekly, weekly_agg)
    X, y, cols = select_features(df)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")

    print("\nTraining LightGBM with GridSearchCV...")
    model = LGBMRegressor(random_state=42)
    params = {
        "n_estimators": [200, 300],
        "num_leaves": [31, 63],
        "learning_rate": [0.05, 0.1],
        "max_depth": [-1, 10],
        "subsample": [0.8, 0.9]
    }

    grid = GridSearchCV(model, params, cv=2, scoring="neg_mean_squared_error", n_jobs=-1, verbose=1)
    grid.fit(X_train, y_train)

    best_model = grid.best_estimator_
    print(f"Best params: {grid.best_params_}")

    y_pred = best_model.predict(X_test)
    metrics = evaluate(y_test, y_pred, X_test)

    # ====================== Feature Importance ======================
    importance = pd.DataFrame({
        "Feature": cols,
        "Importance": best_model.feature_importances_
    }).sort_values("Importance", ascending=False)

    print("\nFeature Importance (Top 15):")
    print(importance.head(15))

    fig = px.bar(
        importance.head(20), x="Importance", y="Feature",
        orientation="h", title="Feature Importance — LightGBM",
        text="Importance", template="plotly_white", height=700
    )
    fig.update_traces(texttemplate='%{text:.3f}', textposition='outside')
    fig.update_layout(yaxis=dict(autorange="reversed"))
    fig.show()

model_path = Path("models/lightgbm_best.pkl")
model_path.parent.mkdir(parents=True, exist_ok=True)   # tạo folder nếu chưa có
joblib.dump(best_model, model_path)

print(f"\n>> Model đã được lưu tại: {model_path}")