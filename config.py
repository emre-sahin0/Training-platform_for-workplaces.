import os
from datetime import timedelta

class Config:
    SECRET_KEY = 'your-secret-key-here'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///isg.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    ADMIN_REGISTRATION_KEY = 'admin123'  # Admin kayıt şifresi 
    
    # --- Performance Ayarları (Hız optimizasyonu) ---
    SEND_FILE_MAX_AGE_DEFAULT = 86400  # Static file cache (1 gün)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 7200,  # 2 saat sonra connection'ları yenile
        'pool_size': 10,  # Connection pool size (SQLite için uygun)
        'max_overflow': 0,  # SQLite threading limiti
        'connect_args': {
            'timeout': 60,  # SQLite timeout (artırıldı)
            'check_same_thread': False
        }
    }
    
    # --- Request Timeout Ayarları ---
    TIMEOUT = 600  # 10 dakika request timeout (büyük dosyalar için)
    
    # --- Güvenlik Ayarları ---
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = True  # Sadece HTTPS üzerinden iletilsin
    SESSION_COOKIE_HTTPONLY = True  # JS erişemesin
    SESSION_COOKIE_SAMESITE = 'Lax'  # CSRF'ye karşı ek koruma
    DEBUG = True  # Debug açık (test için)
    # Canlıda mutlaka uzun ve rastgele bir SECRET_KEY kullanın! 