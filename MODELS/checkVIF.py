'''import numpy as np
import pandas as pd
import pymysql
from sklearn.preprocessing import MinMaxScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor


def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="Khanhdu@123",
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
         # tránh explosion khi merge
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

    # === Derived features ===
    df["cost_price"] = df["net_price"] * 0.7
    df["margin"] = df["net_price"] - df["cost_price"]
    df["avg_price_per_product"] = df.groupby("product_id")["net_price"].transform("mean")
    df["price_relative"] = np.where(df["avg_price_per_product"] > 0,
                                    df["net_price"] / df["avg_price_per_product"], 1)
    df["log_price"] = np.log1p(df["net_price"])

    # === Normalize continuous features ===
    #scale_cols = ["net_price", "cost_price", "margin", "discount_rate",
    #              "avg_weekly_sales", "price_relative", "log_price"]
    #scaler = MinMaxScaler()
    #df[scale_cols] = scaler.fit_transform(df[scale_cols])

    return df

# ====================== Feature Select ======================
def select_features(df):
    features = [
        # region/urbanization
        "region_KVCA","region_KVMB","region_KVMN","region_KVMT",
        "region_KVMTR","region_KVTN","region_Khac",
        "urbanization_Noi_thanh","urbanization_Nong_thon",
        "urbanization_TT_hanh_chinh_kinh_te","urbanization_Khac",
        # encoded categorical
        "product_group_enc","brand_name_enc","price_group_enc",
        # numeric features (normalized)
        "net_price","cost_price","discount_rate","margin",
        "avg_weekly_sales","promo_flag","price_relative","log_price",
        "year_num","month_num"
    ]
    features = [f for f in features if f in df.columns]
    X = df[features]
    y = df["sold_quantity"]
    return X, y, features

def calculate_vif(X: pd.DataFrame):
    vif_data = pd.DataFrame()
    vif_data["Variable"] = X.columns
    vif_data["VIF"] = [variance_inflation_factor(X.values, i) for i in range(X.shape[1])]
    return vif_data

def detect_perfect_collinearity(X: pd.DataFrame, threshold=1e-10):
    """Phát hiện các cặp biến có quan hệ tuyến tính hoàn hảo"""
    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    perfect_pairs = [
        (col, row) for col in upper.columns for row in upper.index
        if not pd.isna(upper.loc[row, col]) and abs(upper.loc[row, col] - 1) < threshold
    ]
    return perfect_pairs

sales, dist, product, weekly_agg = load_data()
df = prepare_data(sales, dist, product, weekly_agg)
X, y, cols = select_features(df)
print("\n===== KẾT QUẢ VIF =====")
vif_df = calculate_vif(X)
print(vif_df.sort_values(by="VIF", ascending=False))

# phát hiện các cặp biến tuyến tính hoàn hảo (gây VIF = ∞)
print("\n===== CÁC CẶP BIẾN TUYẾN TÍNH HOÀN HẢO =====")
perfect_pairs = detect_perfect_collinearity(X)
if perfect_pairs:
    for a, b in perfect_pairs:
        print(f"⚠️ {a} <--> {b}")
else:
    print("Không phát hiện cặp biến nào có tương quan hoàn hảo.")
'''
import numpy as np
import pandas as pd
import pymysql
from sklearn.preprocessing import MinMaxScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor


def get_connection():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="Khanhdu@123",
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
        "week_num"
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

    # Ưu tiên các cặp tuyến tính hoàn hảo
    for a, b in perfect_pairs:
        # chọn 1 trong 2 biến có VIF cao hơn để loại
        a_vif = vif_df.loc[vif_df["Variable"] == a, "VIF"].values[0]
        b_vif = vif_df.loc[vif_df["Variable"] == b, "VIF"].values[0]
        drop_var = a if a_vif >= b_vif else b
        suggestions.add(drop_var)

    # Nếu không có cặp hoàn hảo, xem biến nào VIF cực cao
    high_vif = vif_df[vif_df["VIF"] > 50]["Variable"].tolist()
    suggestions.update(high_vif)

    return list(suggestions)


# ====================== Main ======================
if __name__ == "__main__":
    sales, dist, product, weekly_agg = load_data()
    df = prepare_data(sales, dist, product, weekly_agg)
    # ====================== Check Correlation Between Price Variables ======================
    print("\n===== KIỂM TRA TƯƠNG QUAN VỚI SỐ LƯỢNG BÁN =====")
    price_vars = ["net_price", "cost_price", "margin"]
    existing_vars = [v for v in price_vars if v in df.columns]
    if existing_vars:
        corr_matrix = df[["sold_quantity"] + existing_vars].corr()
        print(corr_matrix)
    else:
        print("Không tìm thấy biến giá nào trong dataframe.")

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