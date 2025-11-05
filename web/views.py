# web/views.py
from datetime import datetime, date
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
import pandas as pd
from django.http import HttpResponse
from io import BytesIO
import openpyxl
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
# 👉 dùng model v8 holiday soft (đặt file đúng thư mục dự án)
MODEL_PATH = BASE_DIR / "web" / "ml_model" / "xgboost_model_v8_holidaysoft_grid.pkl"
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

from datetime import datetime, timedelta

@login_required(login_url='login')
def price_view(request):
    rows = q("SELECT variable_name, original_value, encoded_value FROM mapping")
    mapping = {}
    for var, original, encoded in rows:
        mapping.setdefault(var, []).append({"id": int(encoded), "name": str(original)})

    # 🔥 Lấy thông tin thời gian hiện tại
    today = datetime.today()
    year, week_num, _ = today.isocalendar()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    ctx = {
        "product_groups": mapping.get("product_group", []),
        "brands": mapping.get("brand_name", []),
        "regions": mapping.get("region", []),
        "today": today.strftime("%d/%m/%Y"),
        "week_num": week_num,
        "week_range": f"{start_of_week.strftime('%d/%m')} – {end_of_week.strftime('%d/%m/%Y')}",
        "year": year,
    }
    return render(request, "web/price.html", ctx)

# ================== FEATURE ORDER (V8) ==================
FEATURES_V8 = [
    # Region (7)
    "region_KVCA","region_KVMB","region_KVMT","region_KVMTR","region_KVTN","region_KVMN","region_Khac",
    # Urbanization (4)
    "urbanization_Noi_thanh","urbanization_Nong_thon","urbanization_TT_hanh_chinh_kinh_te","urbanization_Khac",
    # Encoded (3)
    "product_group_enc","brand_name_enc","price_group_enc",
    # Numeric & Time (8)
    "net_price","discount_rate","margin","avg_weekly_sales","promo_flag","price_relative",
    "holiday_flag_soft","week_num"
]


# ================== INTERNAL PREDICT (v8, chuẩn 22 feature) ==================
def _predict_internal_v8(payload):
    # ===== Inputs từ UI hoặc giá trị mặc định =====
    region_enc = int(payload.get("region_enc", 0))               # 0..6
    product_group_enc = int(payload.get("product_group_enc", 0))
    brand_name_enc = int(payload.get("brand_name_enc", 0))
    net_price = float(payload.get("net_price", 4_000_000))
    discount_pct_ui = float(payload.get("discount_rate", 20.0))  # % từ UI
    promo_on = bool(payload.get("promo_on", True))

    # ===== Derived =====
    cost_price = 0.70 * net_price
    margin = max(net_price - cost_price, 0.0)
    promo_flag = 1 if promo_on else 0
    discount_pct_ui = discount_pct_ui if promo_on else 0.0

    # price_relative: baseline theo mốc 3e6 (xấp xỉ lúc train)
    baseline_price = 3_000_000
    price_relative = (net_price / baseline_price) if baseline_price > 0 else 1.0

    # Không có chuỗi lịch sử và lịch lễ theo SKU → baseline nhỏ
    avg_weekly_sales = 0.2
    holiday_flag_soft = 0.1

    # Tuần hiện tại
    week_num = date.today().isocalendar().week

    # ===== Chuẩn hoá gần giống lúc train =====
    # discount_rate lúc train là tỷ lệ 0..~0.5 → map % UI 0..50 về [0..1]
    discount_rate_n = max(0.0, min(discount_pct_ui, 50.0)) / 50.0
    net_price_n  = min(net_price / 10_000_000.0, 1.0)
    margin_n     = min(margin    / 10_000_000.0, 1.0)
    price_rel_n  = min(price_relative / 2.0, 1.0)

    # ===== One-hot region (7) & urbanization (4 – tạm set 0) =====
    region_ohe = [0]*7
    if 0 <= region_enc < 7:
        region_ohe[region_enc] = 1
    urban_ohe = [0,0,0,0]  # chưa nhập từ UI → 0

    # price_group_enc gộp theo net_price nếu UI không gửi
    price_group_enc = int(payload.get(
        "price_group_enc",
        1 if net_price < 2_000_000 else (2 if net_price < 5_000_000 else 3)
    ))

    # ===== Row chuẩn 22 cột, đúng thứ tự FEATURES_V8 =====
    row = {
        # region 7
        "region_KVCA":region_ohe[0],"region_KVMB":region_ohe[1],"region_KVMT":region_ohe[2],
        "region_KVMTR":region_ohe[3],"region_KVTN":region_ohe[4],"region_KVMN":region_ohe[5],"region_Khac":region_ohe[6],
        # urbanization 4
        "urbanization_Noi_thanh":urban_ohe[0], "urbanization_Nong_thon":urban_ohe[1],
        "urbanization_TT_hanh_chinh_kinh_te":urban_ohe[2], "urbanization_Khac":urban_ohe[3],
        # encodes 3
        "product_group_enc": product_group_enc,
        "brand_name_enc": brand_name_enc,
        "price_group_enc": price_group_enc,
        # numeric & time 8
        "net_price": net_price_n,
        "discount_rate": discount_rate_n,
        "margin": margin_n,
        "avg_weekly_sales": avg_weekly_sales,
        "promo_flag": promo_flag,
        "price_relative": price_rel_n,
        "holiday_flag_soft": holiday_flag_soft,
        "week_num": week_num,
    }

    X = pd.DataFrame([row], columns=FEATURES_V8)
    y_pred = float(model.predict(X)[0])
    sold = max(y_pred, 0.0)
    revenue = sold * net_price
    profit = sold * margin
    return {"sold": sold, "revenue": revenue, "profit": profit}


# ================== PREDICT (API) ==================
@csrf_exempt
@login_required(login_url='login')
def predict(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "POST required"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}

        # chạy bằng internal để luôn đúng bộ 22 feature
        y = _predict_internal_v8(payload)

        net_price = float(payload.get("net_price", 4_000_000))
        # discount % để gợi ý AI
        discount_pct_ui = float(payload.get("discount_rate", 20.0))
        promo_on = bool(payload.get("promo_on", True))
        if not promo_on:
            discount_pct_ui = 0.0

        # biên lợi nhuận %
        cost_price = 0.7 * net_price
        margin = max(net_price - cost_price, 0.0)
        margin_rate = (margin / net_price * 100) if net_price else 0.0

        return JsonResponse({
            "ok": True,
            "predicted_sales": round(y["sold"], 2),
            "predicted_revenue": round(y["revenue"], 2),
            "predicted_profit": round(y["profit"], 2),
            "margin_rate": round(margin_rate, 2),
        })
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)


# ================== SIMULATE SERIES (cho biểu đồ) ==================
@csrf_exempt
@login_required(login_url='login')
def simulate_series(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
        mode = payload.get("mode", "discount")

        # defaults an toàn
        payload.setdefault("region_enc", 0)
        payload.setdefault("product_group_enc", 0)
        payload.setdefault("brand_name_enc", 0)
        payload.setdefault("net_price", 4_000_000.0)
        payload.setdefault("discount_rate", 20.0)
        payload.setdefault("promo_on", True)

        series = []
        base_price = float(payload["net_price"])

        if mode == "price":
            # quét ±30% giá theo bước 5%
            for i in range(-6, 7):
                p = base_price * (1 + i * 0.05)
                temp = {**payload, "net_price": p}
                y = _predict_internal_v8(temp)
                series.append({"x": round(p), **y})

        elif mode == "discount":
            # quét 0..50% discount theo bước 5%
            for d in range(0, 55, 5):
                temp = {**payload, "discount_rate": d, "promo_on": True}
                y = _predict_internal_v8(temp)
                series.append({"x": d, **y})

        elif mode == "region":
            # quét 7 vùng, để m có thể gom sang pie chart phía front-end
            for r in range(7):
                temp = {**payload, "region_enc": r}
                y = _predict_internal_v8(temp)
                series.append({"x": r, **y})

        return JsonResponse({"ok": True, "series": series})
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)})
    
from django.http import HttpResponse
from io import BytesIO
import openpyxl
from openpyxl.chart import LineChart, BarChart, Reference
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
import json
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required


@csrf_exempt
@login_required(login_url='login')
def download_report(request):
    try:
        payload = json.loads(request.body.decode("utf-8")) if request.body else {}
        payload.setdefault("region_enc", 0)
        payload.setdefault("product_group_enc", 0)
        payload.setdefault("brand_name_enc", 0)
        payload.setdefault("net_price", 4_000_000.0)
        payload.setdefault("discount_rate", 20.0)
        payload.setdefault("promo_on", True)

        # ========== Vùng mô phỏng ==========
        series_price = []
        series_discount = []
        series_region = []

        # Giá bán ±30%
        base_price = float(payload["net_price"])
        for i in range(-6, 7):
            p = base_price * (1 + i * 0.05)
            y = _predict_internal_v8({**payload, "net_price": p})
            series_price.append({"x": p, **y})

        # Khuyến mãi 0..50%
        for d in range(0, 55, 5):
            y = _predict_internal_v8({**payload, "discount_rate": d, "promo_on": True})
            series_discount.append({"x": d, **y})

        # 7 vùng
        for r in range(7):
            y = _predict_internal_v8({**payload, "region_enc": r})
            series_region.append({"x": r, **y})

        region_names = ["KVCA", "KVMB", "KVMT", "KVMTR", "KVTN", "KVMN", "Khác"]

        # ======= Tìm điểm tối ưu =======
        best_price = max(series_price, key=lambda x: x["profit"])
        best_discount = max(series_discount, key=lambda x: x["profit"])
        best_region = max(series_region, key=lambda x: x["profit"])

        # ======= Tạo Excel =======
        wb = openpyxl.Workbook()
        ws_sum = wb.active
        ws_sum.title = "Summary"

        # --- style cơ bản ---
        bold = Font(bold=True, size=12)
        header_fill = PatternFill("solid", fgColor="C5D9F1")
        thin = Side(border_style="thin", color="000000")
        border = Border(top=thin, left=thin, right=thin, bottom=thin)
        money_fmt = "#,##0₫"

        # === 1️⃣ Sheet SUMMARY ===
        ws_sum.column_dimensions["A"].width = 40
        ws_sum.column_dimensions["B"].width = 28

        ws_sum.append(["HẠNG MỤC", "GIÁ TRỊ"])
        for cell in ws_sum[1]:
            cell.font = bold
            cell.fill = header_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center")

        summary_rows = [
            ["Giá bán tối ưu (VND)", round(best_price["x"], 0)],
            ["Khuyến mãi tối ưu (%)", best_discount["x"]],
            ["Vùng lợi nhuận cao nhất", region_names[best_region["x"]]],
            ["Lợi nhuận tối đa (VND)", best_discount["profit"]],
            ["Doanh thu tối đa (VND)", best_discount["revenue"]],
            ["Sản lượng tối đa (sp/tuần)", best_discount["sold"]],
        ]
        for row in summary_rows:
            ws_sum.append(row)
            for c in ws_sum[ws_sum.max_row]:
                c.border = border
            if isinstance(row[1], (int, float)):
                ws_sum.cell(ws_sum.max_row, 2).number_format = money_fmt

        ws_sum.append([])
        ws_sum.append([
            "📈 Gợi ý AI",
            f"Áp dụng giá {round(best_price['x'],0):,.0f}đ, khuyến mãi {best_discount['x']}% tại {region_names[best_region['x']]} "
            f"để đạt lợi nhuận tối đa {best_discount['profit']:,.0f}đ/tuần."
        ])
        ws_sum["A9"].font = Font(bold=True, color="0070C0")
        ws_sum["B9"].font = Font(bold=True, color="0070C0")
        ws_sum["B9"].alignment = Alignment(wrap_text=True)

        
        # === 2️⃣ PRICE SIMULATION ===
        ws1 = wb.create_sheet("Price Simulation")
        ws1.append(["Giá bán (VND)", "Sản lượng", "Doanh thu (VND)", "Lợi nhuận (VND)"])
        for c in ws1[1]:
            c.font = bold
            c.fill = header_fill
            c.border = border
        for r in series_price:
            ws1.append([round(r["x"], 0), r["sold"], r["revenue"], r["profit"]])
        for row in ws1.iter_rows(min_row=2, max_col=4):
            for c in row:
                c.border = border
                if c.col_idx >= 3:
                    c.number_format = money_fmt

        chart1 = LineChart()
        chart1.title = "Biến động Doanh thu & Lợi nhuận theo Giá bán"
        chart1.y_axis.title = "Giá trị (VND)"
        chart1.x_axis.title = "Giá bán (VND)"
        data = Reference(ws1, min_col=2, max_col=4, min_row=1, max_row=ws1.max_row)
        cats = Reference(ws1, min_col=1, min_row=2, max_row=ws1.max_row)
        chart1.add_data(data, titles_from_data=True)
        chart1.set_categories(cats)
        ws1.add_chart(chart1, "G3")

        # === 3️⃣ DISCOUNT SIMULATION ===
        ws2 = wb.create_sheet("Discount Simulation")
        ws2.append(["Mức giảm giá (%)", "Sản lượng", "Doanh thu (VND)", "Lợi nhuận (VND)"])
        for c in ws2[1]:
            c.font = bold
            c.fill = header_fill
            c.border = border
        for r in series_discount:
            ws2.append([r["x"], r["sold"], r["revenue"], r["profit"]])
        for row in ws2.iter_rows(min_row=2, max_col=4):
            for c in row:
                c.border = border
                if c.col_idx >= 3:
                    c.number_format = money_fmt

        chart2 = LineChart()
        chart2.title = "Ảnh hưởng của Mức Khuyến mãi"
        chart2.y_axis.title = "Giá trị (VND)"
        chart2.x_axis.title = "Mức giảm giá (%)"
        data = Reference(ws2, min_col=2, max_col=4, min_row=1, max_row=ws2.max_row)
        cats = Reference(ws2, min_col=1, min_row=2, max_row=ws2.max_row)
        chart2.add_data(data, titles_from_data=True)
        chart2.set_categories(cats)
        ws2.add_chart(chart2, "G3")

        # === 4️⃣ REGION SIMULATION ===
        ws3 = wb.create_sheet("Region Simulation")
        ws3.append(["Vùng", "Sản lượng", "Doanh thu (VND)", "Lợi nhuận (VND)"])
        for c in ws3[1]:
            c.font = bold
            c.fill = header_fill
            c.border = border
        for r in series_region:
            label = region_names[r["x"]] if 0 <= r["x"] < len(region_names) else "?"
            ws3.append([label, r["sold"], r["revenue"], r["profit"]])
        for row in ws3.iter_rows(min_row=2, max_col=4):
            for c in row:
                c.border = border
                if c.col_idx >= 3:
                    c.number_format = money_fmt

        chart3 = BarChart()
        chart3.title = "So sánh Sản lượng theo Vùng"
        chart3.y_axis.title = "Sản lượng (sp/tuần)"
        chart3.x_axis.title = "Vùng"
        data = Reference(ws3, min_col=2, max_col=2, min_row=1, max_row=ws3.max_row)
        cats = Reference(ws3, min_col=1, min_row=2, max_row=ws3.max_row)
        chart3.add_data(data, titles_from_data=True)
        chart3.set_categories(cats)
        chart3.height = 10
        chart3.width = 20
        ws3.add_chart(chart3, "G3")

        # ====== Xuất file ======
        today_str = datetime.today().strftime("%Y%m%d")

        # Lưu workbook vào stream
        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)

        # Tạo response xuất file Excel
        response = HttpResponse(
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Tên file có ngày động (chắc chắn thay đổi mỗi lần tải)
        filename = f"BaoCaoGiaKhuyenMai_{today_str}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Ghi log ra console để kiểm tra
        print(f"[Download] Generated filename: {filename}")

        return response
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=500)
