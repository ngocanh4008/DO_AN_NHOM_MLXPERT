from django.contrib import admin
from django.urls import path
from .import views

urlpatterns = [
    path('', views.login,),
    path('home', views.home),
    path('price', views.price_page),
    path('report/', views.report_view, name='report'),
]
