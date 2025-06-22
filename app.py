from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import openpyxl
from config import Config
from models import db, login_manager, User, Course, Video, Test, Question, Option, Progress, Announcement, Category, CertificateType, Certificate
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import uuid
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Length, Regexp

# Limiter nesnesini yeni sürüme uygun şekilde başlat
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    # --- Güvenlik: Talisman ve Limiter ---
    Talisman(app, content_security_policy={
        'default-src': ["'self'", 'https://cdn.jsdelivr.net'],
        'img-src': ["'self'", 'data:', 'https://cdn.jsdelivr.net'],
        'script-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net'],
        'style-src': ["'self'", "'unsafe-inline'", 'https://cdn.jsdelivr.net'],
    })
    # Limiter'ı burada app ile başlat
    limiter.init_app(app)

    return app

app = create_app()

# --- Giriş Formu (güçlü parola kontrolü için) ---
class LoginForm(FlaskForm):
    username = StringField('Kullanıcı Adı', validators=[DataRequired()])
    password = PasswordField('Şifre', validators=[DataRequired()])

# --- Kayıt/Şifre değiştir formunda parola politikası ---
password_policy = [
    Length(min=8, message='Şifre en az 8 karakter olmalı.'),
    Regexp(r'.*[A-Z].*', message='Şifre en az bir büyük harf içermeli.'),
    Regexp(r'.*[a-z].*', message='Şifre en az bir küçük harf içermeli.'),
    Regexp(r'.*[0-9].*', message='Şifre en az bir rakam içermeli.'),
    Regexp(r'.*[^A-Za-z0-9].*', message='Şifre en az bir özel karakter içermeli.')
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Kullanıcı adı ve şifre zorunludur.', 'danger')
            return render_template('login.html')
            
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Kullanıcı adı veya şifre hatalı!', 'danger')
            return render_template('login.html')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    if current_user.is_admin:
        courses = Course.query.all()
        selected_course_id = request.args.get('course_id', type=int)
        selected_course = Course.query.get(selected_course_id) if selected_course_id else (courses[0] if courses else None)
        user_progress = []
        if selected_course:
            users = selected_course.assigned_users  # SADECE ATANANLAR
            for user in users:
                # Her video için sadece bir tamamlanma kaydı say
                video_ids = set(v.id for v in selected_course.videos)
                completed_videos = len({p.video_id for p in user.progress if p.completed and p.video_id in video_ids})
                total_videos = len(video_ids)
                percent = int((completed_videos / total_videos) * 100) if total_videos else 0
                if percent > 100:
                    percent = 100
                user_progress.append({
                    'user': user,
                    'completed_videos': completed_videos,
                    'total_videos': total_videos,
                    'percent': percent,
                    'test_score': max((p.test_score for p in user.progress if p.video.course_id == selected_course.id and p.test_score is not None), default=None),
                    'test_completed': any(p.test_completed for p in user.progress if p.video.course_id == selected_course.id),
                })
        return render_template('admin_dashboard.html', courses=courses, selected_course=selected_course, user_progress=user_progress)
    else:
        courses = current_user.assigned_courses
        announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
        return render_template('user_dashboard.html', courses=courses, announcements=announcements)

@app.route('/course/<int:course_id>')
@login_required
def course(course_id):
    course = Course.query.get_or_404(course_id)
    videos = Video.query.filter_by(course_id=course_id).order_by(Video.order).all()
    return render_template('course.html', course=course, videos=videos)

@app.route('/video/<int:video_id>')
@login_required
def video(video_id):
    video = Video.query.get_or_404(video_id)
    progress = Progress.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    is_last_video = False
    test_completed = None
    course = video.course
    videos = sorted(course.videos, key=lambda v: v.order)
    # Video aşamaları
    total_videos = len(videos)
    completed_videos = 0
    for v in videos:
        p = Progress.query.filter_by(user_id=current_user.id, video_id=v.id).first()
        if p and p.completed:
            completed_videos += 1
    # Test aşaması
    has_test = bool((course.test_pdf and course.test_question_count and course.test_answer_key) or (course.tests and course.tests[0].questions))
    test_is_completed = False
    if has_test:
        # Son video üzerinden test tamamlanma kontrolü
        last_video = videos[-1] if videos else None
        if last_video:
            last_progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
            if last_progress and last_progress.test_completed:
                test_is_completed = True
    # Toplam aşama ve tamamlanan aşama
    total_steps = total_videos + (1 if has_test else 0)
    completed_steps = completed_videos + (1 if test_is_completed else 0)
    progress_percent = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
    # Son video ve test durumu
    if videos and video.id == videos[-1].id:
        is_last_video = True
        test_completed = test_is_completed
    return render_template('video.html', video=video, progress=progress, is_last_video=is_last_video, test_completed=test_completed, total_videos=total_videos, completed_videos=completed_videos, progress_percent=progress_percent, total_steps=total_steps, completed_steps=completed_steps, has_test=has_test, test_pdf=course.test_pdf, test_image=course.test_images)

@app.route('/test/<int:test_id>', methods=['GET', 'POST'])
@login_required
def test(test_id):
    test = Test.query.get_or_404(test_id)
    if request.method == 'POST':
        score = 0
        for question in test.questions:
            answer = request.form.get(f'question_{question.id}')
            if answer and Option.query.get(int(answer)).is_correct:
                score += 1
        
        progress = Progress.query.filter_by(user_id=current_user.id, video_id=test.course.videos[-1].id).first()
        if progress:
            progress.test_score = score
            progress.test_completed = score >= test.passing_score
            progress.completed_at = datetime.utcnow()
            db.session.commit()
        
        return redirect(url_for('course', course_id=test.course_id))
    
    return render_template('test.html', test=test)

@app.route('/admin/course/new', methods=['GET', 'POST'])
@login_required
def new_course():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    users = User.query.filter_by(is_admin=False).all()
    categories = Category.query.all()
    if request.method == 'POST':
        course = Course(
            title=request.form.get('title'),
            description=request.form.get('description'),
            category_id=request.form.get('category_id'),
            passing_score=request.form.get('passing_score', type=int)
        )
        # Kullanıcı atama
        assigned_user_ids = request.form.getlist('assigned_users')
        course.assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()
        db.session.add(course)
        db.session.commit()

        # Video(lar) ekle
        video_titles = request.form.getlist('video_titles[]')
        video_files = request.files.getlist('video_files[]')
        for idx, (title, file) in enumerate(zip(video_titles, video_files)):
            if file and file.filename:
                filename = secure_filename(f"{datetime.utcnow().timestamp()}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                video = Video(
                    title=title,
                    video_path=filename,
                    course_id=course.id,
                    order=idx+1
                )
                db.session.add(video)
        db.session.commit()

        # Test dosyası (PDF veya resim)
        test_file = request.files.get('test_file')
        pdf_question_count = request.form.get('pdf_question_count')
        pdf_answer_key = request.form.get('pdf_answer_key')
        if test_file and test_file.filename:
            ext = os.path.splitext(test_file.filename)[1].lower()
            if ext == '.pdf':
                filename = secure_filename(f"test_{course.id}_{test_file.filename}")
                test_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                course.test_pdf = filename
                course.test_images = None
            elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                img_filename = secure_filename(f"testimg_{course.id}_{datetime.utcnow().timestamp()}_{test_file.filename}")
                test_file.save(os.path.join(app.config['UPLOAD_FOLDER'], img_filename))
                course.test_images = img_filename
                course.test_pdf = None
            course.test_question_count = int(pdf_question_count) if pdf_question_count else None
            course.test_answer_key = pdf_answer_key
            db.session.commit()

        return redirect(url_for('dashboard'))
    return render_template('new_course.html', users=users, categories=categories)

@app.route('/admin/course/<int:course_id>/upload', methods=['POST'])
@login_required
def upload_video(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    if 'video' not in request.files:
        flash('No video file')
        return redirect(url_for('course', course_id=course_id))
    
    file = request.files['video']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('course', course_id=course_id))
    
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        video = Video(
            title=request.form.get('title'),
            video_path=filename,
            course_id=course_id,
            order=Video.query.filter_by(course_id=course_id).count() + 1
        )
        db.session.add(video)
        db.session.commit()
    
    return redirect(url_for('course', course_id=course_id))

@app.route('/admin/report')
@login_required
def generate_report():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))

    selected_course_id = request.args.get('course_id', type=int)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None

    if not selected_course:
        flash('Rapor için bir kurs seçmelisiniz.')
        return redirect(url_for('dashboard'))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Eğitim Raporu"

    # Başlıkları ekle
    headers = ['Kullanıcı', 'E-posta', 'Kurs', 'Kategori', 'Tamamlanan Video', 'Toplam Video', 'İlerleme (%)', 'Test Sonucu', 'Durum', 'Tamamlanma Tarihi']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='6A82FB', end_color='6A82FB', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = Border(left=Side(style='thin', color='B4B4B4'), right=Side(style='thin', color='B4B4B4'), top=Side(style='thin', color='B4B4B4'), bottom=Side(style='thin', color='B4B4B4'))

    row = 2
    users = selected_course.assigned_users
    videos = selected_course.videos
    for user in users:
        completed_videos = 0
        last_completed_at = ''
        test_score = '-'
        test_status = 'Devam Ediyor'
        for video in videos:
            progress = Progress.query.filter_by(user_id=user.id, video_id=video.id).first()
            if progress and progress.completed:
                completed_videos += 1
                if progress.completed_at:
                    last_completed_at = progress.completed_at.strftime('%Y-%m-%d %H:%M:%S')
                if progress.test_score is not None:
                    test_score = progress.test_score
                if progress.test_completed:
                    test_status = 'Tamamlandı'
        total_videos = len(videos)
        percent = int((completed_videos / total_videos) * 100) if total_videos else 0
        ws.cell(row=row, column=1, value=f"{user.first_name} {user.last_name}")
        ws.cell(row=row, column=2, value=user.email)
        ws.cell(row=row, column=3, value=selected_course.title)
        ws.cell(row=row, column=4, value=selected_course.category.name if selected_course.category else '')
        ws.cell(row=row, column=5, value=completed_videos)
        ws.cell(row=row, column=6, value=total_videos)
        percent_cell = ws.cell(row=row, column=7, value=f"{percent}%")
        percent_cell.alignment = Alignment(horizontal='center')
        percent_cell.fill = PatternFill(start_color='A1C4FD', end_color='A1C4FD', fill_type='solid')
        ws.cell(row=row, column=8, value=test_score)
        status_cell = ws.cell(row=row, column=9, value=test_status)
        if test_status == 'Tamamlandı':
            status_cell.fill = PatternFill(start_color='43E97B', end_color='43E97B', fill_type='solid')
            status_cell.font = Font(bold=True, color='222222')
        else:
            status_cell.fill = PatternFill(start_color='FFB347', end_color='FFB347', fill_type='solid')
            status_cell.font = Font(bold=True, color='222222')
        ws.cell(row=row, column=10, value=last_completed_at)
        for col in range(1, 11):
            ws.cell(row=row, column=col).border = Border(left=Side(style='thin', color='B4B4B4'), right=Side(style='thin', color='B4B4B4'), top=Side(style='thin', color='B4B4B4'), bottom=Side(style='thin', color='B4B4B4'))
        row += 1

    # Sütun genişliklerini ayarla
    for col in ws.columns:
        max_length = 0
        column = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[column].width = max_length + 4

    report_path = os.path.join(app.config['UPLOAD_FOLDER'], f'report_{selected_course.id}.xlsx')
    wb.save(report_path)

    return send_file(report_path, as_attachment=True)

@app.route('/video/<int:video_id>/complete', methods=['POST'])
@login_required
def complete_video(video_id):
    print(f"DEBUG: Video complete called for video_id: {video_id}")
    
    video = Video.query.get_or_404(video_id)
    print(f"DEBUG: Video found: {video.title}")
    
    progress = Progress.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    if not progress:
        progress = Progress(user_id=current_user.id, video_id=video_id)
        db.session.add(progress)
        print(f"DEBUG: Created new progress for user {current_user.id}")
    
    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.session.commit()
    print(f"DEBUG: Progress marked as completed")
    
    # Bir sonraki videoyu veya testi kontrol et
    course = video.course
    print(f"DEBUG: Course: {course.title}")
    
    # Mevcut videonun order'ına göre bir sonraki videoyu bul
    videos = sorted(course.videos, key=lambda v: v.order)
    print(f"DEBUG: Total videos in course: {len(videos)}")
    
    current_index = next((i for i, v in enumerate(videos) if v.id == video_id), -1)
    print(f"DEBUG: Current video index: {current_index}")
    
    if current_index >= 0 and current_index < len(videos) - 1:
        # Bir sonraki video var
        next_video = videos[current_index + 1]
        print(f"DEBUG: Next video found: {next_video.title}")
        return jsonify({
            'success': True, 
            'next_url': url_for('video', video_id=next_video.id),
            'message': 'Bir sonraki videoya geçiliyor...'
        })
    else:
        print(f"DEBUG: This is the last video, checking for test...")
        # Son video, test var mı kontrol et
        completed_count = Progress.query.filter_by(
            user_id=current_user.id, 
            completed=True
        ).join(Video).filter(Video.course_id == course.id).count()
        
        total_count = len(course.videos)
        print(f"DEBUG: Completed videos: {completed_count}/{total_count}")
        
        has_test = bool((course.test_pdf or course.test_images) and course.test_question_count and course.test_answer_key)
        print(f"DEBUG: Course has test: {has_test}")
        
        if has_test and completed_count == total_count:
            # Test var ve tüm videolar tamamlandı
            last_video = videos[-1] if videos else None
            test_progress = Progress.query.filter_by(
                user_id=current_user.id, 
                video_id=last_video.id
            ).first() if last_video else None
            
            test_completed = test_progress and test_progress.test_completed
            print(f"DEBUG: Test already completed: {test_completed}")
            
            if not test_completed:
                print(f"DEBUG: Redirecting to test")
                return jsonify({
                    'success': True,
                    'next_url': url_for('pdf_test', course_id=course.id),
                    'message': 'Teste yönlendiriliyorsunuz...'
                })
            else:
                print(f"DEBUG: Test already completed, going to dashboard")
                return jsonify({
                    'success': True,
                    'next_url': url_for('dashboard'),
                    'message': 'Kurs tamamlandı! Ana panele dönülüyor...'
                })
        else:
            print(f"DEBUG: No test or not all videos completed, going to dashboard")
            return jsonify({
                'success': True,
                'next_url': url_for('dashboard'),
                'message': 'Kurs tamamlandı! Ana panele dönülüyor...'
            })
    
    print(f"DEBUG: Fallback return")
    return jsonify({'success': True})

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm = request.form.get('confirm')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        is_admin = request.form.get('is_admin') == 'on'
        admin_password = request.form.get('admin_password')

        if not username or not email or not password or not confirm or not first_name or not last_name:
            flash('Tüm alanları doldurun.', 'danger')
            return render_template('register.html')
        if password != confirm:
            flash('Şifreler eşleşmiyor.', 'danger')
            return render_template('register.html')
            
        # Güçlü şifre kontrolü
        if len(password) < 8:
            flash('Şifre en az 8 karakter olmalı.', 'danger')
            return render_template('register.html')
        if not any(c.isupper() for c in password):
            flash('Şifre en az bir büyük harf içermeli.', 'danger')
            return render_template('register.html')
        if not any(c.islower() for c in password):
            flash('Şifre en az bir küçük harf içermeli.', 'danger')
            return render_template('register.html')
        if not any(c.isdigit() for c in password):
            flash('Şifre en az bir rakam içermeli.', 'danger')
            return render_template('register.html')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            flash('Şifre en az bir özel karakter içermeli (!@#$%^&* vb.).', 'danger')
            return render_template('register.html')
            
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.', 'danger')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta zaten kayıtlı.', 'danger')
            return render_template('register.html')
        
        # Admin şifre kontrolü - SADECE admin olarak kayıt olunuyorsa
        if is_admin:
            if not admin_password or admin_password != app.config['ADMIN_REGISTRATION_KEY']:
                flash('Geçersiz admin kayıt şifresi.', 'danger')
                return render_template('register.html')

        user = User(username=username, email=email, first_name=first_name, last_name=last_name, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    # Kullanıcının tüm ilerleme kayıtlarını sil
    Progress.query.filter_by(user_id=current_user.id).delete()
    
    # Kullanıcıyı sil
    db.session.delete(current_user)
    db.session.commit()
    
    logout_user()
    flash('Hesabınız başarıyla silindi.')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
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

@app.route('/admin/users')
@login_required
def admin_users():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.first_name = request.form.get('first_name')
        user.last_name = request.form.get('last_name')
        user.email = request.form.get('email')
        user.is_admin = True if request.form.get('is_admin') == 'on' else False
        db.session.commit()
        flash('Kullanıcı bilgileri güncellendi.', 'success')
        return redirect(url_for('admin_users'))
    return render_template('edit_user.html', user=user)

@app.route('/admin/user/<int:user_id>/delete', methods=['POST'])
@login_required
def delete_user(user_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Admin kullanıcılar silinemez.', 'danger')
        return redirect(url_for('admin_users'))
    # Kullanıcıya ait tüm ilerlemeleri sil
    Progress.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('Kullanıcı başarıyla silindi.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/course/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        course.category_id = request.form.get('category_id')
        course.certificate_type_id = request.form.get('certificate_type_id')
        course.passing_score = request.form.get('passing_score', type=int)
        
        # Kullanıcı atama
        assigned_user_ids = request.form.getlist('assigned_users')
        course.assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()
        
        db.session.commit()
        flash('Kurs başarıyla güncellendi.')
        return redirect(url_for('admin_courses'))
    
    users = User.query.filter_by(is_admin=False).all()
    categories = Category.query.all()
    certificate_types = CertificateType.query.all()
    return render_template('edit_course.html', course=course, users=users, categories=categories, certificate_types=certificate_types)

@app.route('/admin/course/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    # Önce testleri, soruları ve şıkları sil
    for test in course.tests:
        for question in test.questions:
            for option in question.options:
                db.session.delete(option)
            db.session.delete(question)
        db.session.delete(test)
    # Kursun tüm videolarını ve ilerlemeleri sil
    upload_folder = app.config['UPLOAD_FOLDER']
    for video in course.videos:
        # Video dosyasını sil
        video_path = os.path.join(upload_folder, video.video_path)
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
            except Exception as e:
                print(f"Video dosyası silinemedi: {video_path} - {e}")
        Progress.query.filter_by(video_id=video.id).delete()
        db.session.delete(video)
    # Test PDF dosyasını sil
    if course.test_pdf:
        pdf_path = os.path.join(upload_folder, course.test_pdf)
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception as e:
                print(f"PDF dosyası silinemedi: {pdf_path} - {e}")
    # Test fotoğraflarını sil
    if course.test_images:
        for img_filename in course.test_images.split(','):
            img_path = os.path.join(upload_folder, img_filename)
            if os.path.exists(img_path):
                try:
                    os.remove(img_path)
                except Exception as e:
                    print(f"Test fotoğrafı silinemedi: {img_path} - {e}")
    # Rapor dosyalarını sil
    # Tekli rapor
    report_path = os.path.join(upload_folder, f'report_{course.id}.xlsx')
    if os.path.exists(report_path):
        try:
            os.remove(report_path)
        except Exception as e:
            print(f"Rapor dosyası silinemedi: {report_path} - {e}")
    # Çoklu raporlar (multi_report_...xlsx)
    for fname in os.listdir(upload_folder):
        if fname.startswith('multi_report_') and fname.endswith('.xlsx'):
            multi_report_path = os.path.join(upload_folder, fname)
            if os.path.exists(multi_report_path):
                try:
                    os.remove(multi_report_path)
                except Exception as e:
                    print(f"Multi rapor dosyası silinemedi: {multi_report_path} - {e}")
    db.session.delete(course)
    db.session.commit()
    flash('Kurs ve tüm videoları/testleri ve dosyaları silindi.')
    return redirect(url_for('dashboard'))

@app.route('/admin/courses')
@login_required
def admin_courses():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    courses = Course.query.all()
    return render_template('admin_courses.html', courses=courses)

@app.route('/admin/course/<int:course_id>/test/edit', methods=['POST'])
@login_required
def edit_test(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    title = request.form.get('title')
    passing_score = int(request.form.get('passing_score'))

    # Test var mı kontrol et
    test = Test.query.filter_by(course_id=course_id).first()
    if not test:
        test = Test(title=title, course_id=course_id, passing_score=passing_score)
        db.session.add(test)
        db.session.commit()
    else:
        test.title = title
        test.passing_score = passing_score
        # Eski soruları ve şıkları sil
        for q in test.questions:
            for o in q.options:
                db.session.delete(o)
            db.session.delete(q)
        db.session.commit()

    # Soruları ve şıkları ekle
    questions = []
    i = 0
    while True:
        q_text = request.form.get(f'question_{i}')
        if not q_text:
            break
        question = Question(text=q_text, test_id=test.id)
        db.session.add(question)
        db.session.commit()
        # Şıklar
        options = []
        correct_index = request.form.get(f'correct_{i}')
        for j in range(2):
            o_text = request.form.get(f'option_{i}_{j}')
            if o_text:
                is_correct = (str(j) == correct_index)
                option = Option(text=o_text, is_correct=is_correct, question_id=question.id)
                db.session.add(option)
        db.session.commit()
        i += 1

    flash('Test başarıyla kaydedildi.')
    return redirect(url_for('course', course_id=course_id))

@app.route('/admin/course/<int:course_id>/testpdf', methods=['POST'])
@login_required
def upload_test_pdf(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    course = Course.query.get_or_404(course_id)
    file = request.files.get('test_pdf')
    question_count = int(request.form.get('question_count'))
    answer_key = request.form.get('answer_key').replace(' ', '').upper()  # e.g. A,B,C,D

    # PDF dosyasını kaydet
    if file and file.filename.endswith('.pdf'):
        filename = f"test_{course_id}_{secure_filename(file.filename)}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        # Test PDF ve anahtarını kursa kaydet (basit çözüm: Course modeline alan ekle)
        course.test_pdf = filename
        course.test_question_count = question_count
        course.test_answer_key = answer_key
        db.session.commit()
        flash('Test PDF ve cevap anahtarı kaydedildi.')
    else:
        flash('Geçerli bir PDF dosyası seçmelisiniz.')
    return redirect(url_for('course', course_id=course_id))

@app.route('/admin/certificate/<int:certificate_id>/upload', methods=['POST'])
@login_required
def admin_upload_certificate_file(certificate_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    certificate = Certificate.query.get_or_404(certificate_id)
    file = request.files.get('certificate_file')
    if file and file.filename:
        filename = secure_filename(f"cert_{certificate_id}_{file.filename}")
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(upload_path)
        certificate.certificate_file = filename
        db.session.commit()
        flash('Sertifika dosyası yüklendi.')
    else:
        flash('Dosya seçilmedi.')
    return redirect(url_for('admin_certificates'))

@app.route('/certificates')
@login_required
def user_certificates():
    certificates = Certificate.query.filter_by(user_id=current_user.id).all()
    return render_template('user_certificates.html', certificates=certificates)

@app.route('/certificate/<int:certificate_id>')
@login_required
def view_certificate(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    if certificate.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('dashboard'))
    return render_template('view_certificate.html', certificate=certificate)

@app.route('/certificate/<int:certificate_id>/print')
@login_required
def print_certificate(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    if certificate.user_id != current_user.id and not current_user.is_admin:
        return redirect(url_for('dashboard'))
    return render_template('certificate_print.html', certificate=certificate)

@app.route('/admin/generate-certificate/<int:user_id>', methods=['POST'])
@login_required
def generate_certificate(user_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    certificate_type_id = request.form.get('certificate_type_id', type=int)
    certificate_type = CertificateType.query.get_or_404(certificate_type_id)
    
    # Kullanıcının tamamladığı kursları kontrol et
    completed_courses = []
    for course in certificate_type.courses:
        progress = Progress.query.filter_by(
            user_id=user.id,
            video_id=course.videos[-1].id,
            test_completed=True
        ).first()
        if progress and progress.test_score >= course.passing_score:
            completed_courses.append(course)
    
    if len(completed_courses) >= certificate_type.required_course_count:
        # Belge oluştur
        certificate = Certificate(
            user_id=user.id,
            certificate_type_id=certificate_type_id,
            certificate_number=f"CERT-{uuid.uuid4().hex[:8].upper()}"
        )
        certificate.courses = completed_courses
        db.session.add(certificate)
        db.session.commit()
        flash('Belge başarıyla oluşturuldu.')
    else:
        flash('Kullanıcı belge için gerekli kursları tamamlamamış.')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/certificates')
@login_required
def admin_certificates():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    certificates = Certificate.query.order_by(Certificate.issue_date.desc()).all()
    return render_template('admin_certificates.html', certificates=certificates)

@app.route('/admin/announcements', methods=['GET', 'POST'])
@login_required
def admin_announcements():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        if title and content:
            ann = Announcement(title=title, content=content)
            db.session.add(ann)
            db.session.commit()
            flash('Duyuru eklendi.', 'success')
        else:
            flash('Başlık ve içerik zorunlu.', 'danger')
    announcements = Announcement.query.order_by(Announcement.created_at.desc()).all()
    return render_template('admin_announcements.html', announcements=announcements)

@app.route('/admin/announcements/<int:ann_id>/delete', methods=['POST'])
@login_required
def delete_announcement(ann_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    ann = Announcement.query.get_or_404(ann_id)
    db.session.delete(ann)
    db.session.commit()
    flash('Duyuru silindi.', 'success')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/announcements/<int:ann_id>/edit', methods=['POST'])
@login_required
def edit_announcement(ann_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    ann = Announcement.query.get_or_404(ann_id)
    title = request.form.get('title')
    content = request.form.get('content')
    if title and content:
        ann.title = title
        ann.content = content
        db.session.commit()
        flash('Duyuru güncellendi.', 'success')
    else:
        flash('Başlık ve içerik zorunlu.', 'danger')
    return redirect(url_for('admin_announcements'))

@app.route('/admin/categories', methods=['GET', 'POST'])
@login_required
def admin_categories():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        category = Category(
            name=request.form.get('name'),
            description=request.form.get('description')
        )
        db.session.add(category)
        db.session.commit()
        flash('Kategori başarıyla eklendi.')
        return redirect(url_for('admin_categories'))
    
    categories = Category.query.all()
    return render_template('admin_categories.html', categories=categories)

@app.route('/admin/reports')
@login_required
def admin_reports():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    courses = Course.query.all()
    return render_template('admin_reports.html', courses=courses, now=datetime.now)

@app.route('/admin/reports/download', methods=['POST'])
@login_required
def download_multi_report():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    course_ids = request.form.getlist('course_ids')
    if not course_ids:
        flash('En az bir kurs seçmelisiniz.')
        return redirect(url_for('admin_reports'))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Raporlar'
    row = 1
    for course_id in course_ids:
        course = Course.query.get(int(course_id))
        # Kurs başlığı
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
        ws.cell(row=row, column=1, value=f"{course.title} - Rapor Tarihi: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
        ws.cell(row=row, column=1).font = Font(bold=True, size=13, color='4f8cff')
        ws.cell(row=row, column=1).alignment = Alignment(horizontal='center')
        row += 1
        # Sütun başlıkları
        headers = ['Kullanıcı Adı', 'E-posta', 'T. Video', 'Tamamlanan', 'İlerleme (%)', 'Test Sonucu', 'Durum', 'Son Tamamlanma']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='6A82FB', end_color='6A82FB', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(left=Side(style='thin', color='B4B4B4'), right=Side(style='thin', color='B4B4B4'), top=Side(style='thin', color='B4B4B4'), bottom=Side(style='thin', color='B4B4B4'))
        row += 1
        # Kullanıcı satırları
        for user in course.assigned_users:
            completed_videos = 0
            last_completed_at = ''
            test_score = '-'
            test_status = 'Devam Ediyor'
            for video in course.videos:
                progress = Progress.query.filter_by(user_id=user.id, video_id=video.id).first()
                if progress and progress.completed:
                    completed_videos += 1
                    if progress.completed_at:
                        last_completed_at = progress.completed_at.strftime('%d.%m.%Y %H:%M')
                    if progress.test_score is not None:
                        test_score = progress.test_score
                    if progress.test_completed:
                        test_status = 'Tamamlandı'
            total_videos = len(course.videos)
            percent = int((completed_videos / total_videos) * 100) if total_videos else 0
            ws.cell(row=row, column=1, value=f"{user.first_name} {user.last_name}")
            ws.cell(row=row, column=2, value=user.email)
            ws.cell(row=row, column=3, value=total_videos)
            ws.cell(row=row, column=4, value=completed_videos)
            ws.cell(row=row, column=5, value=f"{percent}%")
            ws.cell(row=row, column=6, value=test_score)
            ws.cell(row=row, column=7, value=test_status)
            ws.cell(row=row, column=8, value=last_completed_at)
            for col in range(1, 9):
                ws.cell(row=row, column=col).border = Border(left=Side(style='thin', color='B4B4B4'), right=Side(style='thin', color='B4B4B4'), top=Side(style='thin', color='B4B4B4'), bottom=Side(style='thin', color='B4B4B4'))
            row += 1
        # Her kursun tablosundan sonra bir satır boşluk bırak
        row += 1
    # Sütun genişlikleri (MergedCell hatasına karşı güvenli)
    for col in ws.columns:
        first_cell = next((cell for cell in col if hasattr(cell, 'column_letter')), None)
        if not first_cell:
            continue
        column = first_cell.column_letter
        max_length = 0
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column].width = max_length + 4
    report_path = os.path.join(app.config['UPLOAD_FOLDER'], f'multi_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    wb.save(report_path)
    return send_file(report_path, as_attachment=True)

@app.route('/course/<int:course_id>/pdf-test', methods=['GET', 'POST'])
@login_required
def pdf_test(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Test daha önce tamamlanmış mı kontrol et
    last_video = Video.query.filter_by(course_id=course_id).order_by(Video.order.desc()).first()
    if last_video:
        existing_progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
        if existing_progress and existing_progress.test_completed:
            flash(f'Bu testi daha önce tamamladınız! Sonuç: %{existing_progress.test_score}', 'info')
            return redirect(url_for('course', course_id=course_id))
    
    # Test dosyası tipi ve adı
    test_file_type = None
    test_file_name = None
    if course.test_pdf:
        test_file_type = 'pdf'
        test_file_name = course.test_pdf
    elif course.test_images:
        test_file_type = 'image'
        test_file_name = course.test_images
    if not test_file_type or not course.test_question_count or not course.test_answer_key:
        flash('Bu kurs için test tanımlanmamış.')
        return redirect(url_for('course', course_id=course_id))

    if request.method == 'POST':
        user_answers = []
        for i in range(1, course.test_question_count + 1):
            user_answers.append(request.form.get(f'q{i}', '').upper())
        answer_key = [x.strip() for x in course.test_answer_key.split(',')]
        correct = 0
        for idx, ans in enumerate(user_answers):
            if idx < len(answer_key) and ans == answer_key[idx]:
                correct += 1
        percent = int((correct / course.test_question_count) * 100)
        # Sonucu Progress'e kaydet (son video üzerinden)
        if last_video:
            progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
            if not progress:
                progress = Progress(user_id=current_user.id, video_id=last_video.id)
                db.session.add(progress)
            progress.test_score = percent
            progress.test_completed = True  # Test tamamlandı olarak işaretle
            progress.completed_at = datetime.utcnow()
            db.session.commit()
            
            # Başarı durumuna göre mesaj
            passing_score = course.passing_score or 70
            if percent >= passing_score:
                flash(f'Tebrikler! Testi başarıyla geçtiniz. Sonuç: %{percent} (Geçme notu: %{passing_score})', 'success')
            else:
                flash(f'Test tamamlandı ancak geçeme notunu karşılayamadınız. Sonuç: %{percent} (Geçme notu: %{passing_score})', 'warning')
        
        return redirect(url_for('course', course_id=course_id))

    return render_template('pdf_test.html', course=course, test_file_type=test_file_type, test_file_name=test_file_name)

@app.route('/admin/certificate-operations', methods=['GET', 'POST'])
@login_required
def admin_certificate_operations():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    from models import User, Course, CertificateType, Certificate, Progress, Video
    courses = Course.query.all()
    certificate_types = CertificateType.query.all()
    selected_course_id = request.args.get('course_id', type=int)
    selected_course = Course.query.get(selected_course_id) if selected_course_id else None
    eligible_users = []
    if selected_course:
        videos = selected_course.videos
        video_ids = set(v.id for v in videos)
        for user in selected_course.assigned_users:
            completed_videos = len({p.video_id for p in user.progress if p.completed and p.video_id in video_ids})
            total_videos = len(video_ids)
            # Testi de tamamlamış olmalı (varsa)
            test_ok = True
            if (selected_course.test_pdf or selected_course.test_images) and selected_course.test_question_count and selected_course.test_answer_key:
                last_video = sorted(videos, key=lambda v: v.order)[-1] if videos else None
                progress = next((p for p in user.progress if p.video_id == (last_video.id if last_video else -1)), None)
                test_ok = progress and progress.test_completed
            if completed_videos == total_videos and total_videos > 0 and test_ok:
                eligible_users.append(user)
    if request.method == 'POST':
        selected_user_ids = request.form.getlist('user_ids')
        certificate_type_id = request.form.get('certificate_type_id')
        cert_file = request.files.get('certificate_file')
        if not selected_user_ids or not certificate_type_id or not cert_file or not cert_file.filename:
            flash('Tüm alanları doldurun ve dosya seçin.')
            return redirect(url_for('admin_certificate_operations', course_id=selected_course_id))
        filename = secure_filename(f"admincert_{certificate_type_id}_{cert_file.filename}")
        upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        cert_file.save(upload_path)
        for user_id in selected_user_ids:
            cert = Certificate(
                user_id=user_id,
                certificate_type_id=certificate_type_id,
                certificate_number=f"ADMINCERT-{uuid.uuid4().hex[:8].upper()}",
                certificate_file=filename
            )
            # İlgili kursu ilişkilendir
            if selected_course:
                cert.courses.append(selected_course)
            db.session.add(cert)
        db.session.commit()
        flash('Sertifika(lar) başarıyla gönderildi!')
        return redirect(url_for('admin_certificate_operations', course_id=selected_course_id))
    return render_template('admin_certificate_operations.html', courses=courses, selected_course=selected_course, eligible_users=eligible_users, certificate_types=certificate_types)

@app.route('/admin/user-certificates', methods=['GET', 'POST'])
@login_required
def admin_user_certificates():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    users = User.query.filter_by(is_admin=False).all()
    selected_user_id = request.args.get('user_id', type=int)
    selected_user = User.query.get(selected_user_id) if selected_user_id else None
    user_certificates = []
    if selected_user:
        user_certificates = Certificate.query.filter_by(user_id=selected_user.id).all()
    return render_template('admin_user_certificates.html', users=users, selected_user=selected_user, user_certificates=user_certificates)

@app.route('/admin/certificate/<int:certificate_id>/delete', methods=['POST'])
@login_required
def admin_delete_certificate(certificate_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    cert = Certificate.query.get_or_404(certificate_id)
    db.session.delete(cert)
    db.session.commit()
    flash('Sertifika silindi.')
    return redirect(url_for('admin_user_certificates', user_id=cert.user_id))

@app.route('/admin/database')
@login_required
def admin_database():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    from models import User, Course, Video, Progress, Category, CertificateType, Certificate, Announcement
    
    # Database istatistikleri
    stats = {
        'users': User.query.count(),
        'courses': Course.query.count(),
        'videos': Video.query.count(),
        'categories': Category.query.count(),
        'certificate_types': CertificateType.query.count(),
        'certificates': Certificate.query.count(),
        'announcements': Announcement.query.count(),
        'total_progress': Progress.query.count()
    }
    
    # Son eklenen kayıtlar
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    recent_courses = Course.query.order_by(Course.created_at.desc()).limit(5).all()
    
    return render_template('admin_database.html', stats=stats, recent_users=recent_users, recent_courses=recent_courses)

@app.route('/admin/database/backup', methods=['POST'])
@login_required
def backup_database():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    import shutil
    from datetime import datetime
    
    try:
        # Mevcut database dosyası
        source_db = 'instance/isg.db'
        if not os.path.exists(source_db):
            flash('Database dosyası bulunamadı!', 'danger')
            return redirect(url_for('admin_database'))
        
        # Yedek dosya adı
        backup_name = f'isg_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        backup_path = os.path.join('instance', backup_name)
        
        # Database'i kopyala
        shutil.copy2(source_db, backup_path)
        
        flash(f'Database başarıyla yedeklendi: {backup_name}', 'success')
        
    except Exception as e:
        flash(f'Yedekleme hatası: {str(e)}', 'danger')
    
    return redirect(url_for('admin_database'))

@app.route('/admin/database/reset', methods=['POST'])
@login_required
def reset_database():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    try:
        # Database'i sıfırla
        from create_db import create_db
        create_db()
        flash('Database başarıyla sıfırlandı!', 'success')
        
    except Exception as e:
        flash(f'Database sıfırlama hatası: {str(e)}', 'danger')
    
    return redirect(url_for('admin_database'))

@app.route('/admin/database/export', methods=['POST'])
@login_required
def export_database():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    try:
        import sqlite3
        import json
        from datetime import datetime
        
        # Database bağlantısı
        conn = sqlite3.connect('instance/isg.db')
        cursor = conn.cursor()
        
        # Tüm tabloları al
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        export_data = {}
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            
            # Sütun adlarını al
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Verileri dictionary formatında sakla
            table_data = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    row_dict[columns[i]] = value
                table_data.append(row_dict)
            
            export_data[table_name] = table_data
        
        conn.close()
        
        # JSON dosyası olarak kaydet
        export_filename = f'database_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        export_path = os.path.join('static', 'uploads', export_filename)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
        
        return send_file(export_path, as_attachment=True, download_name=export_filename)
        
    except Exception as e:
        flash(f'Export hatası: {str(e)}', 'danger')
        return redirect(url_for('admin_database'))

@app.route('/admin/database/import', methods=['POST'])
@login_required
def import_database():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    if 'database_file' not in request.files:
        flash('Dosya seçilmedi!', 'danger')
        return redirect(url_for('admin_database'))
    
    file = request.files['database_file']
    if file.filename == '':
        flash('Dosya seçilmedi!', 'danger')
        return redirect(url_for('admin_database'))
    
    if not file.filename.endswith('.json'):
        flash('Sadece JSON dosyaları kabul edilir!', 'danger')
        return redirect(url_for('admin_database'))
    
    try:
        import json
        import sqlite3
        
        # JSON dosyasını oku
        data = json.load(file)
        
        # Database bağlantısı
        conn = sqlite3.connect('instance/isg.db')
        cursor = conn.cursor()
        
        # Mevcut verileri temizle
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]
            cursor.execute(f"DELETE FROM {table_name}")
        
        # Yeni verileri ekle
        for table_name, table_data in data.items():
            if table_data:
                # İlk satırdan sütun adlarını al
                columns = list(table_data[0].keys())
                placeholders = ', '.join(['?' for _ in columns])
                column_names = ', '.join(columns)
                
                for row in table_data:
                    values = [row.get(col) for col in columns]
                    cursor.execute(f"INSERT INTO {table_name} ({column_names}) VALUES ({placeholders})", values)
        
        conn.commit()
        conn.close()
        
        flash('Database başarıyla import edildi!', 'success')
        
    except Exception as e:
        flash(f'Import hatası: {str(e)}', 'danger')
    
    return redirect(url_for('admin_database'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)