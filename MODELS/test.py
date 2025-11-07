import joblib
model = joblib.load("xgboost_best.pkl")
importances = model.feature_importances_
for i, name in enumerate([
    "region_enc","urbanization_enc","price_group_enc","brand_name_enc",
    "product_group_enc","distribution_channel_code_enc","net_price","discount_rate",
    "cost_price","avg_weekly_sales","year_num","month","quarter",
    "holiday_flag","stock_flag","margin","promo_flag"
]):
    print(f"{name:<35} {importances[i]:.5f}")
