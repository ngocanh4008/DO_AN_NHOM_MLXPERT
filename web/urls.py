from django.urls import path
from . import views

urlpatterns = [
  
    # 1. MAIN PAGES
    path('', views.login_view, name='login'),
    path('home/', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('price/', views.price_view, name='price'),
    path('forecast/', views.forecast_view, name='forecast'),
    path('report/', views.report_view, name='report'),
    path('overview/', views.overview_view, name='overview'),

    # 2. PRICE SIMULATION APIs
    path('api/predict/', views.predict, name='api_predict'),            
    path('api/simulate_series/', views.simulate_series, name='simulate_series'),

    # 3. REPORT APIs
    path('api/reports/', views.api_reports, name='api_reports'),
    path('api/download_report/', views.download_report, name='download_report'),
    path('api/reports/<int:report_id>', views.api_delete_report, name='api_delete_report'),
    path('reports/redownload/<int:report_id>', views.api_redownload_report, name='api_redownload_report'),

    # 4. OVERVIEW APIs
    path('api/overview/', views.api_overview, name='api_overview'),
    path('api/download_overview/', views.download_overview, name='download_overview'),

    # 5. FORECAST APIs
    path('api/forecast/', views.api_forecast, name='api_forecast'),
    path('api/forecast/export/', views.export_forecast, name='export_forecast'),
]
