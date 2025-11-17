# ==========================================================
# File: model_compare_v8_gridsearch_with_charts_FINAL.py
# Purpose: 3 models + full GridSearchCV + visualization
# ==========================================================

import pandas as pd
import numpy as np
import pymysql
import joblib
from pathlib import Path
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestRegressor
from scipy.ndimage import gaussian_filter1d
from plotly.subplots import make_subplots
import plotly.graph_objects as go


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
    print(f"✅ {len(features)} features selected.")
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
    return {"MAE": mae, "RMSE": rmse, "R2": r2, "R2_adj": r2_adj, "MAPE": mape, "AIC": aic, "BIC": bic}


# ====================== GridSearch ======================
def grid_train(model, param_grid, X_train, y_train, X_test, y_test, name):
    print(f"\n🚀 GridSearchCV for {name} ...")
    grid = GridSearchCV(model, param_grid, scoring="neg_mean_squared_error", cv=2, n_jobs=-1, verbose=1)
    grid.fit(X_train, y_train)
    best = grid.best_estimator_
    preds = best.predict(X_test)
    metrics = evaluate(y_test, preds, X_test)
    metrics["Model"] = name
    metrics["BestParams"] = grid.best_params_
    print(f"✅ {name} best params: {grid.best_params_}")
    return best, metrics, preds


# ====================== Visualization ======================
def plot_models_grid(y_test, predictions_dict):
    fig = make_subplots(rows=3, cols=1, subplot_titles=list(predictions_dict.keys()), vertical_spacing=0.08)
    row = 1
    for name, preds in predictions_dict.items():
        dfp = pd.DataFrame({"Actual": y_test.values, "Predicted": preds}).reset_index(drop=True).head(300)
        fig.add_trace(go.Scatter(y=dfp["Actual"], mode='lines', name=f"{name} Actual", line=dict(color='blue')), row=row, col=1)
        fig.add_trace(go.Scatter(y=dfp["Predicted"], mode='lines', name=f"{name} Predicted", line=dict(color='orange')), row=row, col=1)
        row += 1
    fig.update_layout(height=1000, width=1000, title="📊 Actual vs Predicted Sold Quantity — All Models",
                      showlegend=False, template="plotly_white")
    fig.show()


# ====================== Main ======================
if __name__ == "__main__":
    print("🚀 Loading data...")
    sales, dist, product, sales_weekly, weekly_agg = load_data()

    print("🔧 Preparing data...")
    df = prepare_data(sales, dist, product, sales_weekly, weekly_agg)
    X, y, _ = select_features(df)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    print(f"Train: {X_train.shape}, Test: {X_test.shape}")

    grids = {
        "XGBoost": {
            "model": XGBRegressor(random_state=42, eval_metric="rmse", tree_method="hist"),
            "params": {
                "n_estimators": [200, 300],
                "max_depth": [5, 6],
                "learning_rate": [0.05, 0.1],
                "subsample": [0.8, 0.9],
                "colsample_bytree": [0.8, 0.9]
            }
        },
        "LightGBM": {
            "model": LGBMRegressor(random_state=42),
            "params": {
                "n_estimators": [200, 300],
                "num_leaves": [31, 63],
                "learning_rate": [0.05, 0.1],
                "max_depth": [-1, 10],
                "subsample": [0.8, 0.9]
            }
        },
        "RandomForest": {
            "model": RandomForestRegressor(random_state=42),
            "params": {
                "n_estimators": [200, 300],
                "max_depth": [8, 10, 12],
                "max_features": ["sqrt", "log2"]
            }
        }
    }

    results, predictions = [], {}
    for name, setup in grids.items():
        model, metrics, preds = grid_train(setup["model"], setup["params"], X_train, y_train, X_test, y_test, name)
        results.append(metrics)
        predictions[name] = preds
        joblib.dump(model, Path(f"{name.lower()}_v8_grid.pkl"))
        print(f"💾 Saved {name} model.")

    # Biểu đồ Actual vs Predicted
    plot_models_grid(y_test, predictions)

    # Xuất file Excel
    df_results = pd.DataFrame(results).set_index("Model")
    print("\n📊 So sánh hiệu năng:")
    print(df_results[["MAE", "RMSE", "R2", "MAPE", "BestParams"]].round(4))
    df_results.to_excel("model_compare_v8_gridsearch_with_charts_FINAL.xlsx")
    print("\n💾 Results saved to model_compare_v8_gridsearch_with_charts_FINAL.xlsx")
