from django.shortcuts import render
from django.http import HttpResponse
# Create your views here.
def home(request):
    return render(request, 'web/home.html') #hàm để tạo lệnh hiển thị trang khi truy cập vào url tương ứng đã cấu hình trong file urls.py
def login(request):
    return render(request, 'web/login.html')
