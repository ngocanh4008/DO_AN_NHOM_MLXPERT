from django.contrib import admin
from django.urls import path
from .import views

urlpatterns = [
    path('', views.home,), # phần '' để cấu hình đường dẫn cho trang. Ví dụ ở đâu '' trống --> runserver sẽ hiện ra trang này đầu tiên
    path('login', views.login,) # 'login' có nghĩa là đường dẫn của trang sẽ là "....:8000/login" 
    #views.[tên trang] --> để hiển thị trang tương ứng với đường dẫn trong ''
]

