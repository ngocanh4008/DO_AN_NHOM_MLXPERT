import numpy as np
import pandas as pd
import pymysql
import seaborn as sns
import matplotlib.pyplot as plt
from sklearn.preprocessing import MinMaxScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor


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
    return sales, dist, product, weekly_agg


# ====================== Feature Engineering ======================
def prepare_data(sales_df, dist, product, weekly_agg):
    if "channel_id" in dist.columns:
        dist = dist.drop_duplicates(subset=["channel_id"])
    if "product_id" in product.columns:
        product = product.drop_duplicates(subset=["product_id"])
    if "product_id" in weekly_agg.columns:
        weekly_agg = weekly_agg.drop_duplicates(subset=["product_id"])

    df = (
        sales_df
        .merge(dist, on="channel_id", how="left")
        .merge(product, on="product_id", how="left")
        .merge(weekly_agg, on="product_id", how="left")
    )

    df = df.fillna(0)

    df["avg_price_per_product"] = df.groupby("product_id")["net_price"].transform("mean")
    df["price_relative"] = np.where(df["avg_price_per_product"] > 0,
                                    df["net_price"] / df["avg_price_per_product"], 1)

    return df


# ====================== Feature Select ======================
def select_features(df):
    features = [
        "region_KVCA","region_KVMB","region_KVMT",
        "region_KVMTR","region_KVTN","region_Khac",
        "urbanization_Noi_thanh","urbanization_Nong_thon",
        "urbanization_TT_hanh_chinh_kinh_te",
        "product_group_enc","brand_name_enc","price_group_enc",
        "net_price","discount_rate","margin",
        "avg_weekly_sales","promo_flag","price_relative",
        "week_num","holiday_flag"
    ]
    features = [f for f in features if f in df.columns]
    X = df[features]
    y = df["sold_quantity"]
    return X, y, features


# ====================== VIF & Collinearity Check ======================
def calculate_vif(X: pd.DataFrame):
    vif_data = pd.DataFrame()
    vif_data["Variable"] = X.columns
    vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    return vif_data


def detect_perfect_collinearity(X: pd.DataFrame, threshold=1e-10):
    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    perfect_pairs = [
        (col, row) for col in upper.columns for row in upper.index
        if not pd.isna(upper.loc[row, col]) and abs(upper.loc[row, col] - 1) < threshold
    ]
    return perfect_pairs


# ====================== Suggest Columns to Drop ======================
def suggest_drops(X, vif_df, perfect_pairs):
    suggestions = set()

    for a, b in perfect_pairs:
        a_vif = vif_df.loc[vif_df["Variable"] == a, "VIF"].values[0]
        b_vif = vif_df.loc[vif_df["Variable"] == b, "VIF"].values[0]
        drop_var = a if a_vif >= b_vif else b
        suggestions.add(drop_var)

    high_vif = vif_df[vif_df["VIF"] > 50]["Variable"].tolist()
    suggestions.update(high_vif)

    return list(suggestions)


# ====================== Main ======================
if __name__ == "__main__":
    sales, dist, product, weekly_agg = load_data()
    df = prepare_data(sales, dist, product, weekly_agg)

    # === Tương quan giữa hai biến chính ===
    print("\n===== TƯƠNG QUAN GIỮA 2 BIẾN QUAN TRỌNG NHẤT =====")
    if all(v in df.columns for v in ["price_relative", "discount_rate"]):
        corr_value = df["price_relative"].corr(df["discount_rate"])
        print(f"📊 Hệ số tương quan giữa price_relative và discount_rate: {corr_value:.4f}")
        if abs(corr_value) > 0.8:
            print("⚠️ Hai biến này tương quan rất mạnh → có thể gây bias hoặc multicollinearity.")
        elif abs(corr_value) > 0.5:
            print("⚠️ Hai biến này tương quan trung bình → nên xem xét khi train model.")
        else:
            print("✅ Hai biến này không tương quan đáng kể → an toàn.")
    else:
        print("Không tìm thấy đủ hai biến price_relative và discount_rate trong dữ liệu.")

    # === Heatmap toàn bộ biến ===
    print("\n===== MA TRẬN TƯƠNG QUAN TOÀN BỘ BIẾN =====")
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    corr_matrix = df[numeric_cols].corr()

    plt.figure(figsize=(14, 10))
    sns.heatmap(corr_matrix, annot=False, cmap="coolwarm", center=0, linewidths=0.3)
    plt.title("🔍 Heatmap Tương Quan Giữa Các Biến Số", fontsize=14, weight="bold")
    plt.tight_layout()
    plt.show()

    # === VIF ===
    X, y, cols = select_features(df)
    print("\n===== KẾT QUẢ VIF =====")
    vif_df = calculate_vif(X)
    print(vif_df.sort_values(by="VIF", ascending=False))

    print("\n===== CÁC CẶP BIẾN TUYẾN TÍNH HOÀN HẢO =====")
    perfect_pairs = detect_perfect_collinearity(X)
    if perfect_pairs:
        for a, b in perfect_pairs:
            print(f"{a} <--> {b}")
    else:
        print("Không phát hiện cặp biến nào có tương quan hoàn hảo.")

    print("\n===== GỢI Ý BIẾN NÊN LOẠI BỎ =====")
    drops = suggest_drops(X, vif_df, perfect_pairs)
    if drops:
        print("Các biến nên bỏ:", ", ".join(drops))
    else:
        print("Không cần loại bỏ biến nào.")
