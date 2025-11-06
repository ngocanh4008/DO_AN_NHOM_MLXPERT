from django.contrib import admin
from django.urls import path
from web import views

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('home/', views.home, name='home'),
    path('price/', views.price_view, name='price'),
    path('forecast/', views.forecast_view, name='forecast'),

    # === API ROUTES ===
    path('api/forecast/', views.api_forecast, name='api_forecast'),
    path('api/predict/', views.predict, name='predict'),
    path('api/simulate/', views.simulate_series, name='simulate_series'),
    path('api/download/', views.download_report, name='download_report'),
]
