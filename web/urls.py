from django.contrib import admin
from django.urls import path
from . import views

# app_name được đặt nếu đây là file urls.py của một ứng dụng (app-level)
# Nếu là file urls.py chính (project-level), bạn không cần dòng này.
# app_name = 'core'

urlpatterns = [
    # ------------------------------------
    # 1. AUTHENTICATION & CORE PAGES (CÁC TRANG CHỦ YẾU)
    # ------------------------------------
    path('', views.login_view, name='login'),  # Trang Đăng nhập (Mặc định)
    path('home', views.home, name='home'),  # Trang chủ
    path('price', views.price_view, name='price'),  # Trang giá/định giá
    path('report/', views.report_view, name='report'),  # Trang báo cáo (Giao diện người dùng)
    path('overview/', views.overview_view, name='overview'),  # Trang tổng quan

    # ------------------------------------
    # 2. API ENDPOINTS (ĐIỂM CUỐI DỮ LIỆU)
    # ------------------------------------

    # API List/Create
    path('api/reports', views.api_reports, name='api_reports'),  # Lấy danh sách hoặc tạo báo cáo mới
    path('api/download_report/', views.download_report, name='download_report'),  # Tải báo cáo

    # API Detail/Actions (sử dụng ID động)
    path('api/reports/<int:report_id>', views.api_delete_report, name='api_delete_report'),  # Xóa báo cáo
    path('reports/redownload/<int:report_id>', views.api_redownload_report, name='api_redownload_report'),
    # Tải lại báo cáo

    # Thêm path cho Admin nếu đây là file urls.py chính của project
    # path('admin/', admin.site.urls),
]