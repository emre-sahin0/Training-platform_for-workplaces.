from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, abort, current_app
from flask_login import login_required, current_user, logout_user
from models import User, Course, Progress, Certificate, db
from utils.decorators import admin_required
import os

user_bp = Blueprint('user', __name__)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    # Kullanıcıya atanmış kurslar
    courses = current_user.assigned_courses
    
    # Yönetici ise admin dashboard'a yönlendir
    if current_user.is_admin:
        return redirect(url_for('admin.courses'))
    
    # Kullanıcı için duyurular
    from models import Announcement
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).limit(3).all()
    
    return render_template('user_dashboard.html', 
                         courses=courses, 
                         announcements=announcements,
                         user=current_user)

@user_bp.route('/user-certificates')
@login_required
def certificates():
    """User certificates page"""
    user_certificates = Certificate.query.filter_by(user_id=current_user.id).all()
    
    # Sertifika alabilecek tamamlanmış kurslar
    completed_courses = []
    for course in current_user.assigned_courses:
        progress = course.get_user_progress(current_user)
        if progress.all_content_completed and (not course.test_required or progress.passed_test):
            # Bu kurs için zaten sertifika var mı kontrol et
            existing_cert = Certificate.query.filter(
                Certificate.user_id == current_user.id,
                Certificate.course_id == course.id
            ).first()
            
            if not existing_cert:
                completed_courses.append(course)
    
    return render_template('user_certificates.html', 
                         certificates=user_certificates,
                         completed_courses=completed_courses)

@user_bp.route('/download_certificate/<int:certificate_id>')
@login_required
def download_certificate(certificate_id):
    """
    Sertifika PDF dosyasını indir
    ---
    tags:
      - User
    parameters:
      - name: certificate_id
        in: path
        type: integer
        required: true
        description: Sertifika ID
    produces:
      - application/pdf
    responses:
      200:
        description: PDF dosyası
        schema:
          type: file
      403:
        description: Yetkisiz erişim
      404:
        description: Dosya bulunamadı
    """
    cert = Certificate.query.get_or_404(certificate_id)
    # Sadece kendi sertifikasını veya admin ise indirebilir
    if cert.user_id != current_user.id and not getattr(current_user, 'is_admin', False):
        abort(403)
    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], cert.certificate_path)
    if not os.path.exists(file_path):
        abort(404, description='Belge dosyası bulunamadı.')
    return send_file(file_path, as_attachment=True)

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile management"""
    if request.method == 'POST':
        # Profil güncelleme
        if 'update_profile' in request.form:
            email = request.form.get('email')
            if email != current_user.email and User.query.filter_by(email=email).first():
                flash('Bu e-posta adresi zaten kullanılıyor.')
                return redirect(url_for('profile'))
            
            current_user.email = email
            db.session.commit()
            flash('Profil bilgileriniz güncellendi.')
            return redirect(url_for('profile'))
        
        # Şifre değiştirme
        elif 'change_password' in request.form:
            current_password = request.form.get('current_password')
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            
            if not current_user.check_password(current_password):
                flash('Mevcut şifreniz yanlış.')
                return redirect(url_for('profile'))
            
            if new_password != confirm_password:
                flash('Yeni şifreler eşleşmiyor.')
                return redirect(url_for('profile'))
            
            current_user.set_password(new_password)
            db.session.commit()
            flash('Şifreniz başarıyla değiştirildi.')
            return redirect(url_for('profile'))
    
    return render_template('profile.html')

@user_bp.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user = current_user
    # İlişkili verileri sil (ör: progress, certificates, vs.)
    from models import Progress, Certificate
    Progress.query.filter_by(user_id=user.id).delete()
    Certificate.query.filter_by(user_id=user.id).delete()
    # Kullanıcıyı sil
    db.session.delete(user)
    db.session.commit()
    flash('Hesabınız ve tüm verileriniz silindi.', 'success')
    logout_user()
    return redirect(url_for('auth.login')) 