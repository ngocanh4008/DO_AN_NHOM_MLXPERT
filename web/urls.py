from django.contrib import admin
from django.urls import path
from .import views

urlpatterns = [
    path('', views.login_view),
    path('home', views.home),
    path('price', views.price_view),
    path('report/', views.report_view, name='report'),
    path('api/reports', views.api_reports, name='api_reports'),
    path('api/download_report/', views.download_report, name='download_report'),
    path('api/reports/<int:report_id>', views.api_delete_report, name='api_delete_report'),
    path('reports/redownload/<int:report_id>', views.api_redownload_report, name='api_redownload_report'),
]