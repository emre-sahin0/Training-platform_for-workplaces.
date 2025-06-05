import os
from datetime import timedelta

class Config:
    SECRET_KEY = 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///isg.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 16MB max file size
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    ADMIN_REGISTRATION_KEY = 'admin123'  # Admin kayıt şifresi 
    # --- Güvenlik Ayarları ---
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = True  # Sadece HTTPS üzerinden iletilsin
    SESSION_COOKIE_HTTPONLY = True  # JS erişemesin
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF'ye karşı ek koruma
    DEBUG = False  # Canlıda debug kapalı olmalı
    # Canlıda mutlaka uzun ve rastgele bir SECRET_KEY kullanın! 