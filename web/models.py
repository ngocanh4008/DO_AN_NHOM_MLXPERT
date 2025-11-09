# models.py
from django.db import models
from django.contrib.auth.models import User

class ReportDownloadHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payload = models.JSONField()  # lưu params gửi từ frontend
    filename = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    file_size_kb = models.FloatField(default=0.0)

    def __str__(self):
        return f"{self.user.username} - {self.filename} - {self.created_at}"

# Lưu ý: Cần chạy migration sau khi chỉnh sửa models.py
# python manage.py makemigrations
# python manage.py migrate