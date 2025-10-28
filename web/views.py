# web/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required

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
