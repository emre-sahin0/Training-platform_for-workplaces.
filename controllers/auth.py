from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from models import User, PasswordReset, db
from services.email_service import send_password_reset_email
from utils.decorators import anonymous_required
import secrets
from datetime import datetime, timedelta
import re

auth_bp = Blueprint('auth', __name__)

# Şifre gücü kontrol fonksiyonu
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

@auth_bp.route('/login', methods=['GET', 'POST'])
@anonymous_required
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            flash('Başarıyla giriş yaptınız!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'danger')
    
    return render_template('login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
@anonymous_required
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten kullanılıyor!', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta adresi zaten kullanılıyor!', 'danger')
            return render_template('register.html')
        
        # Create new user
        if not is_strong_password(password):
            flash('Şifreniz en az 8 karakter, büyük harf, küçük harf, rakam ve özel karakter içermelidir!', 'danger')
            return render_template('register.html')
        
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('login'))

@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
@anonymous_required
def forgot_password():
    if request.method == 'POST':
        # JSON request'i destekle
        if request.is_json:
            email = request.json.get('email')
        else:
            email = request.form.get('email')
        
        if not email:
            if request.is_json:
                return jsonify({'success': False, 'message': 'E-posta adresi gerekli.', 'category': 'danger'})
            flash('E-posta adresi gerekli.', 'danger')
            return redirect(url_for('forgot_password'))
        
        user = User.query.filter_by(email=email).first()
        
        if not user:
            message = 'Bu e-posta adresi kayıtlı değil.'
            if request.is_json:
                return jsonify({'success': False, 'message': message, 'category': 'danger'})
            flash(message, 'danger')
            return redirect(url_for('forgot_password'))
        
        # Onaylanmış ve henüz kullanılmamış talep var mı kontrol et
        approved_request = PasswordReset.query.filter_by(
            user_id=user.id, 
            status='approved'
        ).first()
        
        if approved_request:
            # Onaylanmış talep var, şifre değiştirme sayfasına yönlendir
            if request.is_json:
                return jsonify({
                    'success': True,
                    'redirect_url': url_for('reset_password_with_token', token=approved_request.token)
                })
            return redirect(url_for('reset_password_with_token', token=approved_request.token))
        
        # Bekleyen talep var mı kontrol et
        pending_request = PasswordReset.query.filter_by(
            user_id=user.id, 
            status='pending'
        ).first()
        
        if pending_request:
            message = 'Şifre sıfırlama talebiniz zaten mevcut. Admin onayını bekleyin.'
            message_long = 'Şifre sıfırlama talebiniz admin onayında bekliyor. Onaylandıktan sonra tekrar bu sayfaya gelerek şifrenizi sıfırlayabilirsiniz.'
            if request.is_json:
                return jsonify({
                    'success': True, 
                    'message': message,
                    'message_long': message_long,
                    'category': 'info'
                })
            flash(message, 'info')
            return redirect(url_for('forgot_password'))
        
        # Yeni talep oluştur
        reset_request = PasswordReset(
            user_id=user.id,
            status='pending'
        )
        db.session.add(reset_request)
        db.session.commit()
        
        message = 'Şifre sıfırlama talebiniz gönderildi.'
        message_long = 'Şifre sıfırlama talebiniz admin onayına gönderildi. Admin onayından sonra tekrar bu sayfaya gelerek şifrenizi sıfırlayabilirsiniz.'
        if request.is_json:
            return jsonify({
                'success': True, 
                'message': message,
                'message_long': message_long,
                'category': 'info'
            })
        flash(message, 'info')
        return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@auth_bp.route('/reset_password/<token>', methods=['GET', 'POST'])
@anonymous_required
def reset_password_with_token(token):
    reset_request = PasswordReset.query.filter_by(token=token, status='approved').first()
    
    if not reset_request:
        flash('Geçersiz token veya talep bulunamadı.', 'danger')
        return redirect(url_for('forgot_password'))
    
    # Token süresi dolmuş mu kontrol et
    if reset_request.expires_at and reset_request.expires_at < datetime.utcnow():
        flash('Token süresi dolmuş. Yeni bir şifre sıfırlama talebinde bulunun.', 'danger')
        # Süresi dolmuş token'ı temizle
        reset_request.status = 'expired'
        db.session.commit()
        return redirect(url_for('forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not password or not confirm_password:
            flash('Şifre alanları boş bırakılamaz!', 'danger')
            return render_template('reset_password_with_token.html', token=token)
        
        if password != confirm_password:
            flash('Şifreler eşleşmiyor!', 'danger')
            return render_template('reset_password_with_token.html', token=token)
        
        if not is_strong_password(password):
            flash('Şifreniz en az 8 karakter, büyük harf, küçük harf, rakam ve özel karakter içermelidir!', 'danger')
            return render_template('reset_password_with_token.html', token=token)
        
        # Update password
        user = User.query.get(reset_request.user_id)
        user.set_password(password)
        
        # Mark request as completed
        reset_request.status = 'completed'
        db.session.commit()
        
        flash('Şifreniz başarıyla güncellendi. Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    
    return render_template('reset_password_with_token.html', token=token) 