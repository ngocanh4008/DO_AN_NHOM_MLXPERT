# DO_AN_NHOM_MLXPERT
Đây là github quản lý source code trong quá trình thực hiện đồ án môn Học máy trong phân tích kinh doanh_Nhóm 9_MLXpert

**1. Cách tải đúng phiên bản đồ án**
Dự án có nhiều nhánh (branch). Phiên bản hoàn chỉnh để chạy và demo là FIN_NONFILT.

Clone repo + checkout đúng nhánh:
git clone https://github.com/ngocanh4008/DO_AN_NHOM_MLXPERT
cd DO_AN_NHOM_MLXPERT
git checkout FIN_NONFILT

**Nếu không dùng Git:**

Nhấn nút Branch ở góc trên trái -> Chọn FIN_NONFILT -> Nhấn Code → Download ZIP

⚠️ Lưu ý: Không dùng nhánh main để chạy hệ thống vì đây không phải phiên bản final.

**2. Cách chạy backend Django**
1️. Tạo môi trường ảo
python -m venv .venv
.venv\Scripts\activate

2. Cài thư viện
pip install -r requirements.txt

3. Chạy server
python manage.py runserver

4. Tạo server đăng nhập

$env:DJANGO_SUPERUSER_USERNAME="admin"
$env:DJANGO_SUPERUSER_EMAIL="admin@example.com"
$env:DJANGO_SUPERUSER_PASSWORD="YourPass123"
python manage.py createsuperuser --noinput

**Server chạy tại: http://127.0.0.1:8000/**

