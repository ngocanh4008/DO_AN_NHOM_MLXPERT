# web/views.py
from datetime import datetime
import json
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import joblib
import numpy as np
from pathlib import Path
from math import log1p
def login_view(request):
    # Nếu user đã đăng nhập, chuyển đến home
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username')  # hoặc 'email' nếu dùng email
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            if user.is_superuser:  # chỉ cho phép superuser đăng nhập
                login(request, user)
                return redirect('home')
            else:
                messages.error(request, "Tài khoản này không có quyền truy cập.")
        else:
            messages.error(request, "Sai tài khoản hoặc mật khẩu.")

    return render(request, 'web/login.html')  # ✅ template đúng thư mục


@login_required(login_url='login')
def home(request):
    return render(request, 'web/home.html')


def logout_view(request):
    logout(request)
    return redirect('login')

# ================== MODEL LOAD ==================
BASE_DIR = Path(__file__).resolve().parent.parent
# 👉 đổi sang model v7 softmono
MODEL_PATH = BASE_DIR / "web" / "ml_model" / "xgboost_model_v7_softmono.pkl"
model = joblib.load(MODEL_PATH)

# ================== DB Helper ==================
def q(sql):
    with connection.cursor() as cur:
        cur.execute("SET NAMES utf8mb4;")
        cur.execute(sql)
        return cur.fetchall()

# ================== PAGE ==================
@login_required(login_url='login')
def price_view(request):
    """
    GIỮ layout gốc. Chỉ thay đổi inputs/slider theo yêu cầu.
    """
    rows = q("SELECT variable_name, original_value, encoded_value FROM mapping")
    mapping = {}
    for var, original, encoded in rows:
        mapping.setdefault(var, []).append({"id": int(encoded), "name": str(original)})

    ctx = {
        "product_groups": mapping.get("product_group", []),
        "brands": mapping.get("brand_name", []),
        "regions": mapping.get("region", []),
    }
    return render(request, "web/price.html", ctx)

# ================== API ==================
@csrf_exempt
@login_required(login_url='login')
def predict(request):
    """
    API cho model v7 softmono (24 features):
    7 region OHE + 4 urban OHE + 3 encodes +
    10 numeric: net_price, cost_price, discount_rate, margin,
                avg_weekly_sales, promo_flag, price_relative, log_price,
                year_num, month_num
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))

        # ===== Inputs từ UI =====
        region_enc = int(payload["region_enc"])
        product_group_enc = int(payload["product_group_enc"])
        brand_name_enc = int(payload["brand_name_enc"])
        net_price = float(payload["net_price"])
        discount_rate = float(payload["discount_rate"])   # 1..50 (UI)
        promo_on = bool(payload.get("promo_on", True))

        # ===== Derived =====
        # (giữ chung công thức với UI hiện tại)
        cost_price = max(round(net_price * 0.7, 2), 0.0)
        margin = max(round(net_price - cost_price, 2), 0.0)
        price_group_enc = 1 if net_price < 2_000_000 else (2 if net_price < 5_000_000 else 3)
        promo_flag = 1 if promo_on else 0
        avg_weekly_sales = 0.0  # không cho nhập → để 0

        # v7 có thêm:
        # - price_relative: giá hiện tại / giá TB theo product (không có TB ở runtime) → xấp xỉ: so với ngưỡng 3,000,000
        #   m có thể thay hằng số này tùy domain (để 3e6 là hợp lý với dataset của m)
        baseline_price = 3_000_000
        price_relative = (net_price / baseline_price) if baseline_price > 0 else 1.0

        # - log_price
        log_price_val = log1p(net_price)

        # ===== Chuẩn hoá nhẹ cho numeric (xấp xỉ MinMax used in train) =====
        # Clip để tránh out-of-range — không bắt buộc nhưng giúp ổn định hơn
        def clip(v, lo, hi): return max(lo, min(hi, v))

        NET_CAP = 10_000_000.0
        net_price_n  = clip(net_price / NET_CAP, 0.0, 1.0)
        cost_price_n = clip(cost_price / NET_CAP, 0.0, 1.0)
        margin_n     = clip(margin / NET_CAP, 0.0, 1.0)
        discount_n   = clip(discount_rate / 50.0, 0.0, 1.0)  # UI 1..50%
        price_rel_n  = clip(price_relative / 2.0, 0.0, 1.0)  # giả định 0..2x
        log_price_n  = clip(log_price_val / log1p(NET_CAP), 0.0, 1.0)

        # ===== Thời gian =====
        now = datetime.now()
        year_num, month_num = now.year, now.month

        # ===== One-hot region (7) =====
        region_ohe = [0]*7
        if 0 <= region_enc < 7:
            region_ohe[region_enc] = 1

        # ===== One-hot urbanization (4) — để 0 hết (UI không nhập) =====
        urban_ohe = [0, 0, 0, 0]

        # ===== Assemble (ĐÚNG THỨ TỰ V7 — 24 cột) =====
        X = np.array([[
            # 7 region
            *region_ohe,
            # 4 urban
            *urban_ohe,
            # 3 encodes
            product_group_enc, brand_name_enc, price_group_enc,
            # 10 numeric (đÃ chuẩn hoá nhẹ)
            net_price_n, cost_price_n, discount_n, margin_n,
            avg_weekly_sales, promo_flag, price_rel_n, log_price_n,
            year_num, month_num
        ]], dtype=float)

        # Predict
        y_pred = float(model.predict(X)[0])
        sold = max(y_pred, 0.0)
        revenue = sold * net_price
        profit = sold * margin
        margin_rate = (margin / net_price * 100) if net_price else 0.0

        return JsonResponse({
            "ok": True,
            "predicted_sales": round(sold, 2),
            "predicted_revenue": round(revenue, 2),
            "predicted_profit": round(profit, 2),
            "margin_rate": round(margin_rate, 2)
        })

    except KeyError as ke:
        return JsonResponse({"ok": False, "error": f"Missing field: {ke}"}, status=400)
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
# ================== API: SIMULATE SERIES ==================
@csrf_exempt
@login_required(login_url='login')
def simulate_series(request):
    """
    Sinh dữ liệu mô phỏng cho 3 loại biểu đồ:
    - mode="price": thay đổi giá ±30%
    - mode="discount": thay đổi khuyến mãi 0→50%
    - mode="region": thay đổi vùng (0–6)
    """
    try:
        # ✅ an toàn khi body rỗng
        raw = request.body.decode("utf-8").strip()
        payload = json.loads(raw) if raw else {}
        mode = payload.get("mode", "price")

        # ✅ thêm mặc định cho các key bắt buộc
        payload.setdefault("region_enc", 0)
        payload.setdefault("product_group_enc", 0)
        payload.setdefault("brand_name_enc", 0)
        payload.setdefault("net_price", 4000000.0)
        payload.setdefault("discount_rate", 10.0)
        payload.setdefault("promo_on", True)
        print(f"[simulate_series] mode={mode}, keys={list(payload.keys())}")

        series = []
        base_price = float(payload.get("net_price", 4000000))
        discount = float(payload.get("discount_rate", 10))
        region = int(payload.get("region_enc", 0))

        if mode == "price":
            for i in range(-6, 7):  # ±30%
                p = base_price * (1 + i * 0.05)
                temp = {**payload, "net_price": p}
                y = _predict_internal(temp)
                series.append({"x": round(p), **y})

        elif mode == "discount":
            for d in range(0, 55, 5):
                temp = {**payload, "discount_rate": d}
                y = _predict_internal(temp)
                series.append({"x": d, **y})

        elif mode == "region":
            for r in range(7):
                temp = {**payload, "region_enc": r}
                y = _predict_internal(temp)
                series.append({"x": r, **y})

        return JsonResponse({"ok": True, "series": series})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})

# ================== INTERNAL PREDICT ==================

def _predict_internal(payload):
    region_enc = int(payload.get("region_enc", 0))
    product_group_enc = int(payload.get("product_group_enc", 0))
    brand_name_enc = int(payload.get("brand_name_enc", 0))
    net_price = float(payload.get("net_price", 4000000))
    discount_rate = float(payload.get("discount_rate", 10))
    promo_on = bool(payload.get("promo_on", True))

    cost_price = max(round(net_price * 0.7, 2), 0.0)
    margin = max(round(net_price - cost_price, 2), 0.0)
    price_group_enc = 1 if net_price < 2_000_000 else (2 if net_price < 5_000_000 else 3)
    promo_flag = 1 if promo_on else 0
    avg_weekly_sales = 0.0

    # ===== Các feature bổ sung (giống predict()) =====
    baseline_price = 3_000_000
    price_relative = (net_price / baseline_price) if baseline_price > 0 else 1.0
    log_price_val = log1p(net_price)

    # ===== Chuẩn hoá =====
    def clip(v, lo, hi): return max(lo, min(hi, v))
    NET_CAP = 10_000_000.0
    net_price_n  = clip(net_price / NET_CAP, 0.0, 1.0)
    cost_price_n = clip(cost_price / NET_CAP, 0.0, 1.0)
    margin_n     = clip(margin / NET_CAP, 0.0, 1.0)
    discount_n   = clip((discount_rate / 50.0) * 1.5, 0.0, 1.0)
    price_rel_n  = clip(price_relative / 2.0, 0.0, 1.0)
    log_price_n  = clip(log_price_val / log1p(NET_CAP), 0.0, 1.0)

    # ===== Time & one-hot =====
    now = datetime.now()
    year_num, month_num = now.year, now.month
    region_ohe = [0]*7
    if 0 <= region_enc < 7:
        region_ohe[region_enc] = 1
    urban_ohe = [0,0,0,0]

    # ===== Assemble (24 features total) =====
    X = np.array([[*region_ohe, *urban_ohe,
                   product_group_enc, brand_name_enc, price_group_enc,
                   net_price_n, cost_price_n, discount_n, margin_n,
                   avg_weekly_sales, promo_flag, price_rel_n, log_price_n,
                   year_num, month_num]], dtype=float)

    y_pred = float(model.predict(X)[0])
    sold = max(y_pred, 0.0)
    revenue = sold * net_price
    profit = sold * margin
    return {"sold": sold, "revenue": revenue, "profit": profit}
