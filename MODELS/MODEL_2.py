# -------------------------- MODEL_1_Prophet_Final.py --------------------------
# Usage: python MODEL_1_Prophet_Final.py
import pandas as pd
import numpy as np
from prophet import Prophet
import mysql.connector
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import math
import joblib
import matplotlib.pyplot as plt

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "@Obama123",
    "database": "timeseries_db"
}
TRAIN_QUERY = "SELECT * FROM timeseries_train_sales"
TEST_QUERY  = "SELECT * FROM timeseries_test_sales"
REGRESSORS = ["net_price", "promo_flag"]  # chosen option B
MODEL_PATH = "prophet_monthly_model.joblib"
FORECAST_CSV = "prophet_monthly_forecast.csv"


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "year_num" in df.columns and "month_num" in df.columns:
        df = df[(df["month_num"] >= 1) & (df["month_num"] <= 12)]
        df["year_month"] = df["year_num"].astype(int).astype(str) + "-" + df["month_num"].astype(int).astype(str).str.zfill(2)
        df["ds"] = pd.to_datetime(df["year_month"] + "-01", format="%Y-%m-%d", errors="coerce")
    elif "ds" in df.columns:
        df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
    else:
        raise ValueError("No suitable date columns found (need 'year_num'+'month_num' or 'ds')")

    if "sold_quantity" in df.columns:
        df["y"] = pd.to_numeric(df["sold_quantity"], errors="coerce").fillna(0)
    elif "y" in df.columns:
        df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0)
    else:
        raise ValueError("No target column found. Expected 'sold_quantity' or 'y'.")

    for col in REGRESSORS:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["ds"])  # drop invalid dates
    return df


def monthly_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    agg = (df.groupby("ds", as_index=False)
             .agg({
                "y": "sum",
                "net_price": "mean",
                "promo_flag": "max"
             }))
    if agg["ds"].duplicated().any():
        agg = agg.groupby("ds", as_index=False).mean(numeric_only=True)
    agg = agg.drop_duplicates(subset=["ds"]).sort_values("ds").reset_index(drop=True)
    return agg


def run_prophet():
    conn = mysql.connector.connect(**DB_CONFIG)
    train_df = pd.read_sql(TRAIN_QUERY, conn)
    test_df  = pd.read_sql(TEST_QUERY,  conn)
    conn.close()

    train_df = prepare(train_df)
    test_df  = prepare(test_df)

    train_month = monthly_aggregate(train_df)
    test_month  = monthly_aggregate(test_df)

    # keep originals
    train_month['y_orig'] = train_month['y'].astype(float)
    test_month['y_orig']  = test_month['y'].astype(float)

    # log1p transform
    train_month['y'] = train_month['y'].clip(lower=0)
    train_month['y_log'] = np.log1p(train_month['y'])

    # build input
    train_input = train_month[['ds','y_log'] + REGRESSORS].rename(columns={'y_log':'y'}).copy()
    # replace inf and cast
    train_input = train_input.replace([np.inf,-np.inf], np.nan).dropna()
    for col in REGRESSORS:
        if col in train_input.columns:
            train_input[col] = pd.to_numeric(train_input[col], errors='coerce').fillna(0.0)

    train_input = train_input.drop_duplicates(subset=['ds']).sort_values('ds').reset_index(drop=True)

    # init prophet (no yearly seasonality given short series)
    m = Prophet(changepoint_prior_scale=0.05, seasonality_prior_scale=5, seasonality_mode='additive', yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
    for reg in REGRESSORS:
        m.add_regressor(reg)

    m.fit(train_input)

    # prepare future from test_month
    future = test_month[['ds'] + REGRESSORS].copy()
    for col in REGRESSORS:
        if col in future.columns:
            future[col] = pd.to_numeric(future[col], errors='coerce').fillna(0.0)

    forecast = m.predict(future)

    # inverse transform
    y_pred = np.expm1(forecast['yhat'].values)
    y_true = test_month.set_index('ds').reindex(forecast['ds']).reset_index(drop=True)['y_orig'].values

    mae = mean_absolute_error(y_true, y_pred)
    rmse = math.sqrt(mean_squared_error(y_true, y_pred))
    den = np.where(y_true == 0, 1, y_true)
    mape = np.mean(np.abs((y_true - y_pred) / den)) * 100
    r2 = r2_score(y_true, y_pred)

    print('\n===== Prophet Monthly Evaluation =====')
    print(f'MAE: {mae:,.2f}')
    print(f'RMSE: {rmse:,.2f}')
    print(f'MAPE: {mape:.2f}%')
    print(f'R²: {r2:.4f}')

    # save
    joblib.dump(m, MODEL_PATH)
    out = pd.DataFrame({'ds': forecast['ds'], 'yhat': y_pred, 'y_true': y_true})
    out.to_csv(FORECAST_CSV, index=False)
    print(f'Saved Prophet model to {MODEL_PATH} and forecast to {FORECAST_CSV}')

    # plot
    plt.figure(figsize=(10,5))
    plt.plot(train_month['ds'], train_month['y_orig'], label='Train (Actual)')
    plt.plot(test_month['ds'], y_true, label='Test (Actual)', marker='o')
    plt.plot(out['ds'], out['yhat'], label='Prophet Forecast', linestyle='--')
    plt.title('Prophet Monthly Forecast (net_price + promo_flag)')
    plt.xlabel('Month')
    plt.ylabel('Sold Quantity')
    plt.legend()
    plt.tight_layout()
    plt.show()


# -------------------------- MODEL_2_ARIMAX_Final.py --------------------------
# Usage: python MODEL_2_ARIMAX_Final.py
import pandas as pd
import numpy as np
import mysql.connector
import matplotlib.pyplot as plt
import math
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
import warnings
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.preprocessing import StandardScaler

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "@Obama123",
    "database": "timeseries_db"
}
TRAIN_QUERY = "SELECT * FROM timeseries_train_sales"
TEST_QUERY  = "SELECT * FROM timeseries_test_sales"
EXOG_COLS = ["net_price","promo_flag"]  # option B
MODEL_PATH_ARIMAX = "arimax_monthly_model_final.joblib"
SCALER_PATH = "arimax_monthly_scaler.joblib"
FORECAST_CSV_ARIMAX = "arimax_monthly_forecast_final.csv"


def prepare_base(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "year_num" in df.columns and "month_num" in df.columns:
        df = df[(df["month_num"] >= 1) & (df["month_num"] <= 12)]
        df["year_month"] = df["year_num"].astype(int).astype(str) + "-" + df["month_num"].astype(int).astype(str).str.zfill(2)
        df["ds"] = pd.to_datetime(df["year_month"] + "-01", format="%Y-%m-%d", errors="coerce")
    elif "ds" in df.columns:
        df["ds"] = pd.to_datetime(df["ds"], errors="coerce")
    else:
        raise ValueError("No suitable date columns found (need 'year_num'+'month_num' or 'ds')")

    if "sold_quantity" in df.columns:
        df["y"] = pd.to_numeric(df["sold_quantity"], errors="coerce").fillna(0)
    elif "y" in df.columns:
        df["y"] = pd.to_numeric(df["y"], errors="coerce").fillna(0)
    else:
        raise ValueError("No target column found. Expected 'sold_quantity' or 'y'.")

    for c in EXOG_COLS:
        if c not in df.columns:
            df[c] = np.nan
        df[c] = pd.to_numeric(df[c], errors='coerce')

    df = df.dropna(subset=['ds'])
    return df


def monthly_agg_base(df: pd.DataFrame) -> pd.DataFrame:
    agg = (df.groupby('ds', as_index=False)
           .agg({'y':'sum', 'net_price':'mean', 'promo_flag':'max'}))
    if agg['ds'].duplicated().any():
        agg = agg.groupby('ds', as_index=False).mean(numeric_only=True)
    agg = agg.drop_duplicates(subset=['ds']).sort_values('ds').reset_index(drop=True)
    return agg


def run_arimax():
    warnings.filterwarnings('ignore')
    conn = mysql.connector.connect(**DB_CONFIG)
    train_df = pd.read_sql(TRAIN_QUERY, conn)
    test_df  = pd.read_sql(TEST_QUERY,  conn)
    conn.close()

    train_df = prepare_base(train_df)
    test_df  = prepare_base(test_df)

    train_month = monthly_agg_base(train_df)
    test_month  = monthly_agg_base(test_df)

    # originals
    train_month['y_orig'] = train_month['y'].astype(float)
    test_month['y_orig'] = test_month['y'].astype(float)

    # log transform target
    train_month['y_log'] = np.log1p(train_month['y'].clip(lower=0))
    test_month['y_log']  = np.log1p(test_month['y'].clip(lower=0))

    # prepare series
    train_series = train_month.set_index('ds')['y_log'].asfreq('MS').fillna(method='ffill')
    test_series  = test_month.set_index('ds')['y_log'].asfreq('MS').fillna(method='ffill')

    # exogenous: select EXOG_COLS and scale
    exog_train = train_month.set_index('ds')[EXOG_COLS].reindex(train_series.index).fillna(0.0)
    exog_test  = test_month.set_index('ds')[EXOG_COLS].reindex(test_series.index).fillna(0.0)

    scaler = StandardScaler()
    exog_train_scaled = scaler.fit_transform(exog_train)
    exog_test_scaled = scaler.transform(exog_test)
    joblib.dump(scaler, SCALER_PATH)
    print(f'Saved scaler to {SCALER_PATH}')

    # small grid
    orders = [(0,1,0),(0,1,1),(1,1,0),(1,1,1)]
    best_aic = np.inf
    best_res = None
    best_order = None

    print('🔎 Grid search ARIMAX (small grid)')
    for order in orders:
        try:
            mod = SARIMAX(train_series, order=order, exog=exog_train_scaled, enforce_stationarity=False, enforce_invertibility=False)
            res = mod.fit(disp=False)
            print(f'order={order} AIC={res.aic:.2f}')
            if res.aic < best_aic:
                best_aic = res.aic
                best_res = res
                best_order = order
        except Exception as e:
            print(f'skip {order} -> {e}')

    if best_res is None:
        raise RuntimeError('No valid ARIMAX model found')

    print(f'✅ Best order: {best_order} AIC={best_aic:.2f}')

    # forecast on log scale
    pred = best_res.get_forecast(steps=len(test_series), exog=exog_test_scaled)
    y_pred_log = pred.predicted_mean
    conf = pred.conf_int()

    # inverse transform
    y_pred = np.expm1(y_pred_log.values)
    y_lower = np.expm1(conf.iloc[:,0].values)
    y_upper = np.expm1(conf.iloc[:,1].values)

    y_true = test_month.set_index('ds').reindex(pred.predicted_mean.index)['y_orig'].fillna(0).values

    mae = mean_absolute_error(y_true, y_pred)
    rmse = math.sqrt(mean_squared_error(y_true, y_pred))
    den = np.where(y_true == 0, 1, y_true)
    mape = np.mean(np.abs((y_true - y_pred) / den)) * 100
    try:
        r2 = r2_score(y_true, y_pred)
    except Exception:
        r2 = float('nan')

    print('\n===== ARIMAX Monthly Evaluation (final) =====')
    print(f'MAE: {mae:,.2f}')
    print(f'RMSE: {rmse:,.2f}')
    print(f'MAPE: {mape:.2f}%')
    print(f'R²: {r2:.4f}')

    # save model
    joblib.dump(best_res, MODEL_PATH_ARIMAX)
    print(f'Saved ARIMAX to {MODEL_PATH_ARIMAX}')

    out = pd.DataFrame({'ds': pred.predicted_mean.index, 'yhat': y_pred, 'yhat_lower': y_lower, 'yhat_upper': y_upper, 'y_true': y_true})
    out.to_csv(FORECAST_CSV_ARIMAX, index=False)
    print(f'Saved forecast to {FORECAST_CSV_ARIMAX}')

    # plot
    plt.figure(figsize=(10,5))
    plt.plot(train_month['ds'], train_month['y_orig'], label='Train (Actual)')
    plt.plot(test_month['ds'], test_month['y_orig'], label='Test (Actual)', marker='o')
    plt.plot(out['ds'], out['yhat'], label='ARIMAX Forecast', linestyle='--')
    plt.fill_between(out['ds'], out['yhat_lower'], out['yhat_upper'], alpha=0.2)
    plt.title('ARIMAX Monthly Forecast (net_price + promo_flag)')
    plt.xlabel('Month')
    plt.ylabel('Sold Quantity')
    plt.legend()
    plt.tight_layout()
    plt.show()


# -------------------------- ENTRYPOINT --------------------------
if __name__ == '__main__':
    # run Prophet first then ARIMAX
    print('Running Prophet final...')
    try:
        run_prophet()
    except Exception as e:
        print('Prophet failed:', e)

    print('\nRunning ARIMAX final...')
    try:
        run_arimax()
    except Exception as e:
        print('ARIMAX failed:', e)
