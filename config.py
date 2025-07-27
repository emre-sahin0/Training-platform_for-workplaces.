import os
from datetime import timedelta

class Config:
    ENV = os.environ.get('FLASK_ENV', 'production')
    if ENV == 'development':
        SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    else:
        SECRET_KEY = os.environ.get('SECRET_KEY')
        if not SECRET_KEY:
            raise RuntimeError('SECRET_KEY ortam değişkeni tanımlı değil!')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File upload settings
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    
    # Ensure upload folder exists
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Email settings
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@trt.com.tr'
    
    # SQLAlchemy engine options for performance
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {
            'timeout': 20,
            'check_same_thread': False
        }
    }
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)
    
    # Request timeout
    TIMEOUT = 600  # 10 minutes
    
    # Debug mode
    DEBUG = True 