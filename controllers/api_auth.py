from flask import Blueprint, request, jsonify
from models import User, db
import jwt
import datetime
from werkzeug.security import check_password_hash
from config import Config
SECRET_KEY = Config.SECRET_KEY
import re

api_auth_bp = Blueprint('api_auth', __name__)

# Şifre gücü kontrol fonksiyonu (mevcutla aynı)
def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>\/?]", password):
        return False
    return True

# JWT token oluşturucu
def generate_jwt(user):
    payload = {
        'user_id': user.id,
        'username': user.username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

# JWT doğrulama decorator'u
def jwt_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        if not token:
            return jsonify({'error': 'Yetkisiz erişim!'}), 401
        try:
            data = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            user = User.query.get(data['user_id'])
            if not user:
                return jsonify({'error': 'Yetkisiz erişim!'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Yetkisiz erişim!'}), 401
        except Exception as e:
            return jsonify({'error': 'Yetkisiz erişim!'}), 401
        return f(user, *args, **kwargs)
    return decorated

@api_auth_bp.route('/api/register', methods=['POST'])
def api_register():
    """
    Kullanıcı API register endpointi
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            email:
              type: string
            password:
              type: string
            first_name:
              type: string
            last_name:
              type: string
    responses:
      201:
        description: Kayıt başarılı
        schema:
          type: object
          properties:
            message:
              type: string
      400:
        description: Eksik veya hatalı alanlar
    """
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    first_name = data.get('first_name')
    last_name = data.get('last_name')

    if not username or not email or not password:
        return jsonify({'error': 'Eksik alanlar!'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Kullanıcı adı zaten var!'}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'E-posta zaten var!'}), 400
    if not is_strong_password(password):
        return jsonify({'error': 'Şifreniz en az 8 karakter, büyük harf, küçük harf, rakam ve özel karakter içermelidir!'}), 400
    user = User(
        username=username,
        email=email,
        first_name=first_name,
        last_name=last_name
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'Kayıt başarılı!'}), 201

@api_auth_bp.route('/api/login', methods=['POST'])
def api_login():
    """
    Kullanıcı API login endpointi
    ---
    tags:
      - Auth
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              type: string
            password:
              type: string
    responses:
      200:
        description: Başarılı giriş
        schema:
          type: object
          properties:
            token:
              type: string
      401:
        description: Hatalı giriş
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Kullanıcı adı veya şifre hatalı!'}), 401
    token = generate_jwt(user)
    return jsonify({'token': token})

@api_auth_bp.route('/api/protected', methods=['GET'])
@jwt_required
def protected_route(current_user):
    """
    JWT ile korunan örnek endpoint
    ---
    tags:
      - Auth
    security:
      - Bearer: []
    responses:
      200:
        description: Başarılı erişim
        schema:
          type: object
          properties:
            message:
              type: string
      401:
        description: Yetkisiz erişim
    """
    return jsonify({'message': f'Hoşgeldin {current_user.username}, bu korumalı bir endpointtir!'}) 