from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime, timedelta
import openpyxl
from config import Config
from models import db, login_manager, User, Course, Video, Test, Question, Option, Progress, Announcement, Category, CertificateType, Certificate, PasswordReset, Pdf, PdfProgress
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import uuid
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired, Length, Regexp, EqualTo
import secrets
from flask_migrate import Migrate
from flask_mail import Mail, Message
from flask_weasyprint import render_pdf
from flask_weasyprint import HTML

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
mail = Mail(app)
migrate = Migrate(app, db)

# --- Güçlü şifre politikası için yardımcı fonksiyon ---
def password_policy_check(password):
    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalı."
    if not any(c.isupper() for c in password):
        return False, "Şifre en az bir büyük harf içermeli."
    if not any(c.islower() for c in password):
        return False, "Şifre en az bir küçük harf içermeli."
    if not any(c.isdigit() for c in password):
        return False, "Şifre en az bir rakam içermeli."
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        return False, "Şifre en az bir özel karakter içermeli (!@#$%^&* vb.)."
    return True, ""

def send_password_reset_email(user, token):
    """Kullanıcıya şifre sıfırlama e-postası gönderir."""
    msg = Message(
        'AdaWall Eğitim - Şifre Sıfırlama İsteği',
        sender=app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email]
    )
    reset_url = url_for('reset_password_with_token', token=token, _external=True)
    msg.html = render_template('email/reset_password.html', user=user, reset_url=reset_url)
    try:
        mail.send(msg)
        return True
    except Exception as e:
        app.logger.error(f"E-posta gönderme hatası: {e}")
        return False

# --- Form Sınıfları ---

class EmptyForm(FlaskForm):
    """CSRF koruması için boş form."""
    pass

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

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Yeni Şifre', validators=[DataRequired()] + password_policy)
    confirm = PasswordField('Yeni Şifreyi Onayla', validators=[
        DataRequired(),
        EqualTo('password', message='Şifreler eşleşmelidir.')
    ])

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
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
    # Admin ise kurs yönetim sayfasına yönlendir
    if current_user.is_admin:
        return redirect(url_for('admin_manage_course', course_id=course_id))
    
    course = Course.query.get_or_404(course_id)
    content = get_course_content(course.id)

    # Eğer kursta hiç içerik yoksa
    if not content:
        return render_template('course.html', course=course, status='empty', button_text='Kursta İçerik Yok', start_url=url_for('dashboard'))

    # Kullanıcının ilerlemesini al
    progress_details = course.get_user_progress(current_user)
    
    # Kullanıcının tamamladığı videoları bul
    completed_video_ids = set()
    for progress in current_user.progress:
        if progress.completed and progress.video:
            if progress.video.course_id == course_id:
                completed_video_ids.add(progress.video_id)

    # Görüntülenen PDF'leri al (database'den)
    viewed_pdf_ids = set()
    pdf_progress_list = PdfProgress.query.filter_by(user_id=current_user.id).all()
    for pdf_progress in pdf_progress_list:
        if pdf_progress.pdf.course_id == course_id:
            viewed_pdf_ids.add(pdf_progress.pdf_id)

    # Sıradaki içeriği bul
    next_item = None
    for item in content:
        if item['type'] == 'video':
            # Video tamamlanmamışsa, bu sıradaki adım
            if item['id'] not in completed_video_ids:
                next_item = item
                break
        elif item['type'] == 'pdf':
            # PDF görüntülenmemişse, bu sıradaki adım
            if item['id'] not in viewed_pdf_ids:
                next_item = item
                break

    # URL ve durumu belirle
    start_url = url_for('dashboard') 
    status = 'not_started'
    button_text = 'Eğitime Başla'
    
    # Hiç başlanmamış mı?
    has_any_progress = bool(completed_video_ids or viewed_pdf_ids)
    
    if next_item:
        # Sonraki adım var
        if next_item['type'] == 'video':
            start_url = url_for('video', video_id=next_item['id'])
        else: # pdf
            start_url = url_for('pdf_viewer', pdf_id=next_item['id'])
        
        # Başlanmış mı?
        if has_any_progress:
            status = 'in_progress'
            button_text = 'Eğitime Devam Et'
        else:
            status = 'not_started'
            button_text = 'Eğitime Başla'
    else:
        # Sonraki adım yok - tüm içerik tamamlandı mı kontrol et
        if progress_details.all_content_completed:
            status = 'completed'
            if course.test_required and (course.test_pdf or course.test_images):
                # Test tamamlanmış mı kontrol et
                if not progress_details.passed_test:
                    start_url = url_for('pdf_test', course_id=course.id)
                    button_text = 'Kursu Bitirme Testine Git'
                    status = 'test_required'
                else:
                    button_text = 'Kurs Tamamlandı'
                    start_url = url_for('dashboard')
                    status = 'completed'
            else:
                button_text = 'Kurs Tamamlandı'
                start_url = url_for('dashboard')
                status = 'completed'
        else:
            # İçerik tamamlanmamış ama sonraki adım bulunamadı - bu bir hata durumu
            # En son erişilebilir içeriğe yönlendir
            if has_any_progress:
                # Son tamamlanan içeriği bul
                last_accessible_item = None
                for item in content:
                    if item['type'] == 'video' and item['id'] in completed_video_ids:
                        last_accessible_item = item
                    elif item['type'] == 'pdf' and item['id'] in viewed_pdf_ids:
                        last_accessible_item = item
                
                if last_accessible_item:
                    if last_accessible_item['type'] == 'video':
                        start_url = url_for('video', video_id=last_accessible_item['id'])
                    else:
                        start_url = url_for('pdf_viewer', pdf_id=last_accessible_item['id'])
                    status = 'in_progress'
                    button_text = 'Eğitime Devam Et'
                else:
                    # İlk içeriğe yönlendir
                    first_item = content[0]
                    if first_item['type'] == 'video':
                        start_url = url_for('video', video_id=first_item['id'])
                    else:
                        start_url = url_for('pdf_viewer', pdf_id=first_item['id'])
                    status = 'in_progress'
                    button_text = 'Eğitime Devam Et'
            else:
                # Hiç başlanmamış, ilk içeriğe yönlendir
                first_item = content[0]
                if first_item['type'] == 'video':
                    start_url = url_for('video', video_id=first_item['id'])
                else:
                    start_url = url_for('pdf_viewer', pdf_id=first_item['id'])
                status = 'not_started'
                button_text = 'Eğitime Başla'

    return render_template('course.html', course=course, start_url=start_url, status=status, button_text=button_text)

def get_course_content(course_id):
    course = Course.query.get_or_404(course_id)
    videos = [{'type': 'video', 'id': v.id, 'data': v} for v in course.videos]
    pdfs = [{'type': 'pdf', 'id': p.id, 'data': p} for p in course.pdfs]
    return sorted(videos + pdfs, key=lambda x: x['data'].order)

@app.route('/video/<int:video_id>')
@login_required
def video(video_id):
    video = Video.query.get_or_404(video_id)
    course = video.course
    
    content_list = get_course_content(course.id)
    current_index = -1
    for i, item in enumerate(content_list):
        if item['type'] == 'video' and item['id'] == video_id:
            current_index = i
            break
    
    # Kullanıcının tamamladığı videoları bul
    completed_video_ids = set()
    for progress in current_user.progress:
        if progress.completed and progress.video:
            if progress.video.course_id == course.id:
                completed_video_ids.add(progress.video_id)
    
    # Görüntülenen PDF'leri al (database'den)
    viewed_pdf_ids = set()
    pdf_progress_list = PdfProgress.query.filter_by(user_id=current_user.id).all()
    for pdf_progress in pdf_progress_list:
        if pdf_progress.pdf.course_id == course.id:
            viewed_pdf_ids.add(pdf_progress.pdf_id)
    
    # Önceki ve sonraki URL'leri belirle
    prev_url = None
    next_url = None
    can_access_next = False
    
    # Önceki içerik (her zaman erişilebilir)
    if current_index > 0:
        prev_item = content_list[current_index - 1]
        if prev_item['type'] == 'video':
            prev_url = url_for('video', video_id=prev_item['id'])
        else:
            prev_url = url_for('pdf_viewer', pdf_id=prev_item['id'])
    
    # Sonraki içerik belirleme
    current_video_completed = video_id in completed_video_ids
    
    if current_index < len(content_list) - 1:
        # Henüz son içerik değil, sonraki video/PDF var
        if current_video_completed:
            next_item = content_list[current_index + 1]
            can_access_next = True
            if next_item['type'] == 'video':
                next_url = url_for('video', video_id=next_item['id'])
            else:
                next_url = url_for('pdf_viewer', pdf_id=next_item['id'])
    else:
        # Bu son içerik, test kontrolü yap
        if current_video_completed:
            # Bu video tamamlandıysa, test var mı kontrol et
            if course.test_required and (course.test_pdf or course.test_images):
                # Test tamamlanmış mı kontrol et
                existing_progress = Progress.query.filter_by(user_id=current_user.id, video_id=video_id).first()
                if not existing_progress or not existing_progress.test_completed:
                    next_url = url_for('pdf_test', course_id=course.id)
                    can_access_next = True

    progress_details = course.get_user_progress(current_user)
    video_progress = video.get_progress(current_user)

    return render_template(
        'video.html',
        video=video,
        course=course,
        progress=video_progress,
        completed_steps=progress_details.completed_steps,
        total_steps=progress_details.total_steps,
        progress_percent=progress_details.progress_percent,
        prev_url=prev_url,
        next_url=next_url,
        can_access_next=can_access_next
    )

@app.route('/pdf/<int:pdf_id>')
@login_required
def pdf_viewer(pdf_id):
    pdf = Pdf.query.get_or_404(pdf_id)
    course = pdf.course

    # PDF görüntüleme kaydını oluştur/güncelle (database'de)
    existing_progress = PdfProgress.query.filter_by(user_id=current_user.id, pdf_id=pdf_id).first()
    if not existing_progress:
        pdf_progress = PdfProgress(user_id=current_user.id, pdf_id=pdf_id)
        db.session.add(pdf_progress)
        db.session.commit()

    content_list = get_course_content(course.id)
    current_index = -1
    for i, item in enumerate(content_list):
        if item['type'] == 'pdf' and item['id'] == pdf_id:
            current_index = i
            break
    
    # Navigasyon URL'leri
    prev_url = None
    next_url = None
    
    # Önceki içerik
    if current_index > 0:
        prev_item = content_list[current_index - 1]
        if prev_item['type'] == 'video':
            prev_url = url_for('video', video_id=prev_item['id'])
        else:
            prev_url = url_for('pdf_viewer', pdf_id=prev_item['id'])
    
    # Sonraki içerik belirleme
    if current_index < len(content_list) - 1:
        # Henüz son içerik değil, sonraki video/PDF var
        next_item = content_list[current_index + 1]
        if next_item['type'] == 'video':
            next_url = url_for('video', video_id=next_item['id'])
        else:
            next_url = url_for('pdf_viewer', pdf_id=next_item['id'])
    else:
        # Bu son içerik, test kontrolü yap
        progress_details = course.get_user_progress(current_user)
        if course.test_required and progress_details.all_content_completed:
            if (course.test_pdf or course.test_images):
                # Test tamamlanmış mı kontrol et
                course_videos = sorted(course.videos, key=lambda v: v.order)
                last_video = course_videos[-1] if course_videos else None
                test_progress = None
                if last_video:
                    test_progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
                
                if not test_progress or not test_progress.test_completed:
                    next_url = url_for('pdf_test', course_id=course.id)

    # Progress bilgilerini al
    progress_details = course.get_user_progress(current_user)

    return render_template('pdf_viewer.html', 
                         pdf=pdf, 
                         course=course, 
                         prev_url=prev_url, 
                         next_url=next_url,
                         completed_steps=progress_details.completed_steps,
                         total_steps=progress_details.total_steps,
                         progress_percent=progress_details.progress_percent)

@app.route('/video/<int:video_id>/complete', methods=['POST'])
@login_required
def complete_video_and_get_next(video_id):
    """Videoyu tamamlandı olarak işaretler ve bir sonraki adımın URL'sini döndürür."""
    video = Video.query.get_or_404(video_id)
    progress = Progress.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    if not progress:
        progress = Progress(user_id=current_user.id, video_id=video_id)
        db.session.add(progress)
    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.session.commit()

    course = video.course
    content_list = get_course_content(course.id)
    
    # Mevcut video'nun content listesindeki pozisyonunu bul
    current_index = -1
    for i, item in enumerate(content_list):
        if item['type'] == 'video' and item['id'] == video_id:
            current_index = i
            break
    
    next_url = None
    message = "Video tamamlandı!"

    # Sonraki içerik var mı?
    if current_index != -1 and current_index < len(content_list) - 1:
        next_item = content_list[current_index + 1]
        if next_item['type'] == 'video':
            next_url = url_for('video', video_id=next_item['id'])
            message = "Sonraki videoya geçebilirsiniz."
        else:  # PDF
            next_url = url_for('pdf_viewer', pdf_id=next_item['id'])
            message = "Sonraki PDF materyaline geçebilirsiniz."
    else:
        # Tüm içerik tamamlandı, test var mı kontrol et
        user_progress_details = course.get_user_progress(current_user)
        if course.test_required and user_progress_details.all_content_completed:
            if (course.test_pdf or course.test_images):
                # Test henüz tamamlanmamışsa teste yönlendir
                course_videos = sorted(course.videos, key=lambda v: v.order)
                last_video = course_videos[-1] if course_videos else None
                test_progress = None
                if last_video:
                    test_progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
                
                if not test_progress or not test_progress.test_completed:
                    next_url = url_for('pdf_test', course_id=course.id)
                    message = "Tüm içerik tamamlandı! Teste geçebilirsiniz."
                else:
                    message = "Tebrikler, kursu tamamladınız!"
            else:
                message = "Tebrikler, kursu tamamladınız!"
        else:
            message = "Tebrikler, kursu tamamladınız!"
            
    return jsonify({
        'success': True, 
        'next_url': next_url,
        'message': message
    })

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

@app.route('/admin/new-course', methods=['GET', 'POST'])
@login_required
def new_course():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Temel kurs bilgilerini al
        title = request.form.get('title')
        description = request.form.get('description')
        category_id = request.form.get('category_id')
        assigned_user_ids = request.form.getlist('assigned_users')
        passing_score = request.form.get('passing_score', 70, type=int)
        test_required = 'test_required' in request.form

        # Yeni kursu oluştur ve session'a ekle
        new_course = Course(
            title=title, 
            description=description, 
            category_id=category_id,
            passing_score=passing_score,
            test_required=test_required,
            certificate_type_id=None # Şimdilik boş, gerekirse güncellenebilir
        )
        db.session.add(new_course)
        
        # Kullanıcıları ata
        new_course.assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()

        # Commit edip ID'yi al
        db.session.commit()

        # Kurs içeriğini işle
        content_titles = request.form.getlist('content_titles[]')
        content_types = request.form.getlist('content_types[]')
        content_orders = request.form.getlist('content_orders[]')
        content_files = request.files.getlist('content_files[]')

        for i, file in enumerate(content_files):
            if file and file.filename:
                content_type = content_types[i]
                timestamp = datetime.utcnow().timestamp()
                
                if content_type == 'video':
                    filename = secure_filename(f"video_{new_course.id}_{timestamp}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    item = Video(
                        title=content_titles[i],
                        video_path=filename,
                        course_id=new_course.id,
                        order=int(content_orders[i])
                    )
                    db.session.add(item)
                elif content_type == 'pdf':
                    filename = secure_filename(f"pdf_{new_course.id}_{timestamp}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    item = Pdf(
                        title=content_titles[i],
                        pdf_path=filename,
                        course_id=new_course.id,
                        order=int(content_orders[i])
                    )
                    db.session.add(item)
        
        # Test dosyası (PDF veya resim) - Sadece test zorunlu ise işle
        if new_course.test_required:
            test_file = request.files.get('test_file')
            pdf_question_count = request.form.get('pdf_question_count')
            pdf_answer_key = request.form.get('pdf_answer_key')

            if test_file and test_file.filename and pdf_question_count and pdf_answer_key:
                ext = os.path.splitext(test_file.filename)[1].lower()
                if ext == '.pdf':
                    filename = secure_filename(f"test_{new_course.id}_{test_file.filename}")
                    new_course.test_pdf = filename
                    new_course.test_images = None
                elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    filename = secure_filename(f"testimg_{new_course.id}_{datetime.utcnow().timestamp()}_{test_file.filename}")
                    new_course.test_images = filename
                    new_course.test_pdf = None
                
                test_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_course.test_question_count = int(pdf_question_count)
                new_course.test_answer_key = pdf_answer_key
        
        db.session.commit()
        flash('Kurs başarıyla oluşturuldu!', 'success')
        return redirect(url_for('dashboard'))

    # GET request için
    users = User.query.filter_by(is_admin=False).all()
    categories = Category.query.all()
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

@app.route('/admin/course/<int:course_id>/pdf/upload', methods=['POST'])
@login_required
def upload_pdf(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    if 'pdf' not in request.files:
        flash('PDF dosyası bulunamadı.', 'danger')
        return redirect(url_for('edit_course', course_id=course_id))
    
    file = request.files['pdf']
    if file.filename == '':
        flash('Dosya seçilmedi.', 'danger')
        return redirect(url_for('edit_course', course_id=course_id))

    if file:
        filename = secure_filename(f"pdf_{course_id}_{datetime.utcnow().timestamp()}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        new_pdf = Pdf(
            title=request.form.get('title'),
            pdf_path=filename,
            course_id=course_id,
            order=int(request.form.get('order'))
        )
        db.session.add(new_pdf)
        db.session.commit()
        flash('PDF materyal başarıyla eklendi.', 'success')
    
    return redirect(url_for('edit_course', course_id=course_id))

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
    headers = ['Kullanıcı', 'E-posta', 'Kurs', 'Kategori', 'Tamamlanan İçerik', 'Toplam İçerik', 'İlerleme (%)', 'Test Sonucu', 'Durum', 'Tamamlanma Tarihi']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill(start_color='6A82FB', end_color='6A82FB', fill_type='solid')
        cell.alignment = Alignment(horizontal='center', vertical='center')
        cell.border = Border(left=Side(style='thin', color='B4B4B4'), right=Side(style='thin', color='B4B4B4'), top=Side(style='thin', color='B4B4B4'), bottom=Side(style='thin', color='B4B4B4'))

    row = 2
    users = selected_course.assigned_users
    for user in users:
        # Yeni progress sistemi ile hesapla
        progress_details = selected_course.get_user_progress(user)
        
        # Test sonucu ve durumu
        test_score = '-'
        test_status = 'Devam Ediyor'
        last_completed_at = ''
        
        if progress_details.passed_test:
            test_score = progress_details.test_score if progress_details.test_score is not None else '-'
            test_status = 'Tamamlandı'
        elif progress_details.is_completed:
            test_status = 'Tamamlandı'
        
        # Son tamamlanma tarihini bul
        latest_date = None
        for video in selected_course.videos:
            progress = Progress.query.filter_by(user_id=user.id, video_id=video.id).first()
            if progress and progress.completed and progress.completed_at:
                if latest_date is None or progress.completed_at > latest_date:
                    latest_date = progress.completed_at
        
        if latest_date:
            last_completed_at = latest_date.strftime('%Y-%m-%d %H:%M:%S')
        
        ws.cell(row=row, column=1, value=f"{user.first_name} {user.last_name}")
        ws.cell(row=row, column=2, value=user.email)
        ws.cell(row=row, column=3, value=selected_course.title)
        ws.cell(row=row, column=4, value=selected_course.category.name if selected_course.category else '')
        ws.cell(row=row, column=5, value=progress_details.completed_steps)
        ws.cell(row=row, column=6, value=progress_details.total_steps)
        percent_cell = ws.cell(row=row, column=7, value=f"{progress_details.progress_percent}%")
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
    report_path = os.path.join(app.config['UPLOAD_FOLDER'], f'report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
    wb.save(report_path)
    return send_file(report_path, as_attachment=True)

def check_course_completion(user, course):
    """
    Kullanıcının belirli bir kursu tamamlayıp tamamlamadığını kontrol eder.
    Bu mantık artık Course modelindeki 'get_user_progress' metoduna taşındı.
    """
    return course.get_user_progress(user).is_completed

@app.route('/complete-video/<int:video_id>', methods=['POST'])
@login_required
def complete_video(video_id):
    """Video tamamlama isteğini (AJAX/Fetch) işler ve JSON döner."""
    video = Video.query.get_or_404(video_id)
    progress = Progress.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    
    if not progress:
        progress = Progress(user_id=current_user.id, video_id=video_id)
        db.session.add(progress)

    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.session.commit()

    return jsonify({'success': True, 'message': 'İlerleme kaydedildi.'})

@app.route('/api/course/<int:course_id>/progress')
@login_required
def api_course_progress(course_id):
    """Kurs ilerlemesini kontrol eden API endpoint'i."""
    course = Course.query.get_or_404(course_id)
    
    # Kullanıcının bu kurstaki video ilerlemelerini al
    video_progress = {}
    completed_videos = 0
    
    for video in course.videos:
        progress = Progress.query.filter_by(
            user_id=current_user.id, 
            video_id=video.id
        ).first()
        
        video_progress[video.id] = progress.completed if progress else False
        if video_progress[video.id]:
            completed_videos += 1
    
    # Kurs bilgilerini hazırla
    course_data = {
        'id': course.id,
        'title': course.title,
        'test_pdf': course.test_pdf,
        'test_images': course.test_images,
        'videos': [{'id': v.id, 'title': v.title, 'order': v.order} for v in course.videos]
    }
    
    return jsonify({
        'success': True,
        'course': course_data,
        'completed_videos': completed_videos,
        'total_videos': len(course.videos),
        'video_progress': video_progress
    })

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
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
        is_valid, message = password_policy_check(password)
        if not is_valid:
            flash(message, 'danger')
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

@app.route('/admin/edit-course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        course.category_id = request.form.get('category_id')
        course.certificate_type_id = request.form.get('certificate_type_id') or None
        course.passing_score = request.form.get('passing_score', 70, type=int)
        course.test_required = 'test_required' in request.form

        if course.certificate_type_id == 'yok':
            course.certificate_type_id = None

        # Kullanıcı atama
        assigned_user_ids = request.form.getlist('assigned_users')
        course.assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()
        
        db.session.commit()
        flash('Kurs başarıyla güncellendi.', 'success')
        return redirect(url_for('admin_manage_course', course_id=course_id))
    
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
    upload_folder = app.config['UPLOAD_FOLDER']
    
    # Önce testleri, soruları ve şıkları sil
    for test in course.tests:
        for question in test.questions:
            for option in question.options:
                db.session.delete(option)
            db.session.delete(question)
        db.session.delete(test)
    
    # Kursun tüm videolarını ve ilerlemeleri sil
    for video in course.videos:
        # Video dosyasını sil
        video_path = os.path.join(upload_folder, video.video_path)
        if os.path.exists(video_path):
            try:
                os.remove(video_path)
                print(f"Video dosyası silindi: {video_path}")
            except Exception as e:
                print(f"Video dosyası silinemedi: {video_path} - {e}")
        Progress.query.filter_by(video_id=video.id).delete()
        db.session.delete(video)
    
    # Kursun tüm PDF dosyalarını sil
    for pdf in course.pdfs:
        # PDF progress kayıtlarını sil
        PdfProgress.query.filter_by(pdf_id=pdf.id).delete()
        
        # PDF dosyasını sil
        pdf_path = os.path.join(upload_folder, pdf.pdf_path)
        if os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
                print(f"PDF dosyası silindi: {pdf_path}")
            except Exception as e:
                print(f"PDF dosyası silinemedi: {pdf_path} - {e}")
        db.session.delete(pdf)
    
    # Test PDF dosyasını sil
    if course.test_pdf:
        test_pdf_path = os.path.join(upload_folder, course.test_pdf)
        if os.path.exists(test_pdf_path):
            try:
                os.remove(test_pdf_path)
                print(f"Test PDF dosyası silindi: {test_pdf_path}")
            except Exception as e:
                print(f"Test PDF dosyası silinemedi: {test_pdf_path} - {e}")
    
    # Test resim dosyasını sil (tek dosya)
    if course.test_images:
        test_img_path = os.path.join(upload_folder, course.test_images)
        if os.path.exists(test_img_path):
            try:
                os.remove(test_img_path)
                print(f"Test resim dosyası silindi: {test_img_path}")
            except Exception as e:
                print(f"Test resim dosyası silinemedi: {test_img_path} - {e}")
    
    # Rapor dosyalarını sil
    # Tekli rapor
    report_path = os.path.join(upload_folder, f'report_{course.id}.xlsx')
    if os.path.exists(report_path):
        try:
            os.remove(report_path)
            print(f"Rapor dosyası silindi: {report_path}")
        except Exception as e:
            print(f"Rapor dosyası silinemedi: {report_path} - {e}")
    
    # Çoklu raporlar (multi_report_...xlsx) - tüm raporları sil
    try:
        for fname in os.listdir(upload_folder):
            if fname.startswith('multi_report_') and fname.endswith('.xlsx'):
                multi_report_path = os.path.join(upload_folder, fname)
                try:
                    os.remove(multi_report_path)
                    print(f"Multi rapor dosyası silindi: {multi_report_path}")
                except Exception as e:
                    print(f"Multi rapor dosyası silinemedi: {multi_report_path} - {e}")
    except Exception as e:
        print(f"Upload klasörü okunamadı: {e}")
    
    # Database'den kursu sil
    db.session.delete(course)
    db.session.commit()
    flash('Kurs ve tüm dosyaları başarıyla silindi.', 'success')
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
    if not current_user.is_admin and current_user.id != certificate.user_id:
        return redirect(url_for('dashboard'))
    return render_template('certificate_print.html', certificate=certificate)

@app.route('/certificate/<int:certificate_id>/download')
@login_required
def download_certificate_pdf(certificate_id):
    """Sertifika sayfasını render edip PDF olarak indirir."""
    certificate = Certificate.query.get_or_404(certificate_id)
    # Yetki kontrolü
    if not current_user.is_admin and current_user.id != certificate.user_id:
        flash('Bu işlemi yapmaya yetkiniz yok.', 'danger')
        return redirect(url_for('dashboard'))

    # Sertifika şablonunu render et
    html_string = render_template('view_certificate.html', certificate=certificate, for_pdf=True)
    html = HTML(string=html_string, base_url=request.url_root)
    # PDF olarak döndür
    return render_pdf(html, download_filename=f'sertifika_{certificate.certificate_number}.pdf')

@app.route('/admin/generate-certificate/<int:user_id>/<int:course_id>', methods=['POST'])
@login_required
def admin_generate_certificate(user_id, course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    user = User.query.get_or_404(user_id)
    course = Course.query.get_or_404(course_id)
    
    # Kullanıcının tamamladığı kursları kontrol et
    completed_courses = []
    for c in course.assigned_users:
        if check_course_completion(c, course):
            completed_courses.append(c)
    
    if len(completed_courses) >= course.certificate_type.required_course_count:
        # Belge oluştur
        certificate = Certificate(
            user_id=user.id,
            certificate_type_id=course.certificate_type_id,
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
        headers = ['Kullanıcı Adı', 'E-posta', 'T. İçerik', 'Tamamlanan', 'İlerleme (%)', 'Test Sonucu', 'Durum', 'Son Tamamlanma']
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=row, column=col, value=header)
            cell.font = Font(bold=True, color='FFFFFF')
            cell.fill = PatternFill(start_color='6A82FB', end_color='6A82FB', fill_type='solid')
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = Border(left=Side(style='thin', color='B4B4B4'), right=Side(style='thin', color='B4B4B4'), top=Side(style='thin', color='B4B4B4'), bottom=Side(style='thin', color='B4B4B4'))
        row += 1
        # Kullanıcı satırları
        for user in course.assigned_users:
            # Yeni progress sistemi ile hesapla
            progress_details = course.get_user_progress(user)
            
            # Test sonucu ve durumu
            test_score = '-'
            test_status = 'Devam Ediyor'
            last_completed_at = ''
            
            if progress_details.passed_test:
                test_score = progress_details.test_score if progress_details.test_score is not None else '-'
                test_status = 'Tamamlandı'
            elif progress_details.is_completed:
                test_status = 'Tamamlandı'
            
            # Son tamamlanma tarihini bul
            latest_date = None
            for video in course.videos:
                progress = Progress.query.filter_by(user_id=user.id, video_id=video.id).first()
                if progress and progress.completed and progress.completed_at:
                    if latest_date is None or progress.completed_at > latest_date:
                        latest_date = progress.completed_at
            
            if latest_date:
                last_completed_at = latest_date.strftime('%d.%m.%Y %H:%M')
            
            ws.cell(row=row, column=1, value=f"{user.first_name} {user.last_name}")
            ws.cell(row=row, column=2, value=user.email)
            ws.cell(row=row, column=3, value=progress_details.total_steps)
            ws.cell(row=row, column=4, value=progress_details.completed_steps)
            ws.cell(row=row, column=5, value=f"{progress_details.progress_percent}%")
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
    
    courses = Course.query.all()
    certificate_types = CertificateType.query.all()
    course_id = request.args.get('course_id', type=int)
    selected_course = Course.query.get(course_id) if course_id else None
    
    eligible_users = []
    if selected_course:
        for user in selected_course.assigned_users:
            # Kullanıcının bu kurs için zaten bir sertifikası olup olmadığını kontrol et
            existing_cert = Certificate.query.filter(
                Certificate.user_id == user.id,
                Certificate.courses.any(id=selected_course.id)
            ).first()

            if not existing_cert:
                user_progress = selected_course.get_user_progress(user)
                # Sadece kursu tamamlayan kullanıcıları listeye ekle
                if user_progress.is_completed:
                    eligible_users.append({'user': user, 'progress': user_progress})

    if request.method == 'POST':
        user_ids = request.form.getlist('user_ids')
        certificate_type_id = request.form.get('certificate_type_id')
        certificate_file = request.files.get('certificate_file')

        if not user_ids or not certificate_type_id:
            flash('Lütfen kullanıcı ve belge türü seçin.', 'danger')
            return redirect(url_for('admin_certificate_operations', course_id=course_id))

        filename = None
        if certificate_file and certificate_file.filename:
            # Dosyayı güvenli bir şekilde kaydet
            filename = secure_filename(f"cert_{datetime.utcnow().timestamp()}_{certificate_file.filename}")
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            certificate_file.save(upload_path)
        
        # Seçilen her kullanıcı için sertifika oluştur
        for user_id in user_ids:
            user = User.query.get(user_id)
            if user:
                certificate = Certificate(
                    user_id=user.id,
                    certificate_type_id=certificate_type_id,
                    certificate_number=f"CERT-{uuid.uuid4().hex[:8].upper()}",
                    certificate_file=filename  # Dosya yoksa None (boş) olacak
                )
                # Sertifikayı kursla ilişkilendir
                if selected_course:
                    certificate.courses.append(selected_course)
                
                db.session.add(certificate)
        
        db.session.commit()
        flash(f'{len(user_ids)} kullanıcıya başarıyla sertifika atandı.', 'success')
        return redirect(url_for('admin_certificate_operations', course_id=course_id))
    
    return render_template('admin_certificate_operations.html', 
                           courses=courses, 
                           selected_course=selected_course,
                           eligible_users=eligible_users,
                           certificate_types=certificate_types,
                           course_id=course_id)

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
    
    # Sertifika dosyasını sil
    if cert.certificate_file:
        cert_path = os.path.join(app.config['UPLOAD_FOLDER'], cert.certificate_file)
        if os.path.exists(cert_path):
            try:
                os.remove(cert_path)
                print(f"Sertifika dosyası silindi: {cert_path}")
            except Exception as e:
                print(f"Sertifika dosyası silinemedi: {cert_path} - {e}")
    
    user_id = cert.user_id
    db.session.delete(cert)
    db.session.commit()
    flash('Sertifika ve dosyası başarıyla silindi.')
    return redirect(url_for('admin_user_certificates', user_id=user_id))

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

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'message': 'E-posta adresi gerekli.', 'category': 'danger'}), 400

        user = User.query.filter_by(email=email).first()
        
        if user:
            # Aktif (onaylanmış veya bekleyen) bir istek var mı kontrol et
            existing_request = PasswordReset.query.filter(
                PasswordReset.user_id == user.id,
                PasswordReset.status.in_(['pending', 'approved'])
            ).first()

            if existing_request:
                # Eğer istek ONAYLANMIŞSA ve token geçerliyse, yenileme sayfasına yönlendir
                if existing_request.status == 'approved' and existing_request.token and existing_request.expires_at > datetime.utcnow():
                    return jsonify({
                        'redirect_url': url_for('reset_password_with_token', token=existing_request.token)
                    })
                
                # Eğer istek BEKLEMEDEYSE, bilgi ver
                return jsonify({
                    'message_long': get_status_message('pending', True), 
                    'category': 'info'
                })

            # Aktif istek yoksa yeni bir tane oluştur
            reset_request = PasswordReset(user_id=user.id)
            db.session.add(reset_request)
            db.session.commit()
            
            return jsonify({
                'message_long': get_status_message('pending', True),
                'category': 'success'
            })
        else:
            return jsonify({'message': 'Bu e-posta adresi ile kayıtlı kullanıcı bulunamadı.', 'category': 'danger'}), 404
    
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password_with_token(token):
    # Token'a göre isteği bul
    reset_request = PasswordReset.query.filter_by(token=token, status='approved').first()

    # Token geçerli değilse veya süresi dolmuşsa
    if not reset_request or reset_request.expires_at < datetime.utcnow():
        flash('Şifre sıfırlama linki geçersiz veya süresi dolmuş. Lütfen yeni bir istek gönderin.', 'danger')
        return redirect(url_for('forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        # Şifreyi güncelle ve isteği tamamla
        user = reset_request.user
        user.set_password(form.password.data)
        reset_request.status = 'completed'
        db.session.commit()

        flash('Şifreniz başarıyla güncellendi! Yeni şifrenizle giriş yapabilirsiniz.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password_with_token.html', token=token, form=form)

@app.route('/admin/password-requests')
@login_required
def admin_password_requests():
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    pending_requests = PasswordReset.query.filter_by(status='pending').order_by(PasswordReset.requested_at.desc()).all()
    
    # Onaylanmış, tamamlanmış ve reddedilmiş olanlar
    processed_requests = PasswordReset.query.filter(PasswordReset.status != 'pending').order_by(PasswordReset.approved_at.desc()).limit(20).all()
    
    return render_template('admin_password_requests.html', 
                         pending_requests=pending_requests,
                         processed_requests=processed_requests)

@app.route('/admin/password-request/<int:request_id>/approve', methods=['POST'])
@login_required
def approve_password_request(request_id):
    if not current_user.is_admin:
        flash('Yetkisiz işlem.', 'danger')
        return redirect(url_for('dashboard'))
    
    reset_request = PasswordReset.query.get_or_404(request_id)
    
    # Token oluştur ve son kullanma tarihi belirle (örn: 1 saat)
    reset_request.token = secrets.token_urlsafe(32)
    reset_request.expires_at = datetime.utcnow() + timedelta(hours=1)
    reset_request.status = 'approved'
    reset_request.approved_by = current_user.id
    reset_request.approved_at = datetime.utcnow()
    
    db.session.commit()
    flash(f'{reset_request.user.username} kullanıcısının isteği onaylandı. Kullanıcı artık şifresini sıfırlayabilir.', 'success')

    return redirect(url_for('admin_password_requests'))

@app.route('/admin/password-request/<int:request_id>/reject', methods=['POST'])
@login_required
def reject_password_request(request_id):
    if not current_user.is_admin:
        flash('Yetkisiz işlem.', 'danger')
        return redirect(url_for('dashboard'))
    
    reset_request = PasswordReset.query.get_or_404(request_id)
    reset_request.status = 'rejected'
    reset_request.approved_by = current_user.id
    reset_request.approved_at = datetime.utcnow()
    db.session.commit()
    
    flash(f'{reset_request.user.username} kullanıcısının şifre sıfırlama isteği reddedildi.', 'warning')
    return redirect(url_for('admin_password_requests'))

@app.route('/check-password-status')
def check_password_status():
    email = request.args.get('email')
    if not email:
        return jsonify({'status': 'error', 'message': 'E-posta adresi gerekli'})
    
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'Kullanıcı bulunamadı'})
    
    reset_request = PasswordReset.query.filter(
        PasswordReset.user_id == user.id,
        PasswordReset.status.in_(['pending', 'approved'])
    ).order_by(PasswordReset.requested_at.desc()).first()
    
    if not reset_request:
        return jsonify({'status': 'none', 'message': 'Aktif bir şifre sıfırlama isteği bulunamadı.'})
    
    response_data = {
        'status': reset_request.status,
        'message_long': get_status_message(reset_request.status, True),
        'requested_at': reset_request.requested_at.strftime('%d.%m.%Y %H:%M')
    }

    if reset_request.status == 'approved':
        response_data['token'] = reset_request.token

    return jsonify(response_data)

def get_status_message(status, long=False):
    messages = {
        'pending': 'İsteğiniz admin onayı için gönderildi. Lütfen daha sonra tekrar kontrol edin.',
        'approved': 'İsteğiniz onaylandı! Şifrenizi şimdi sıfırlayabilirsiniz.',
        'rejected': 'İsteğiniz reddedildi. Lütfen admin ile iletişime geçin.',
        'completed': 'Şifreniz güncellendi. Yeni şifrenizle giriş yapabilirsiniz.'
    }
    long_messages = {
        'pending': """
            <strong>İsteğiniz Alındı ve Admin Onayına Gönderildi</strong><br>
            <small>
            Bir yöneticinin isteğinizi onaylaması gerekiyor. Onaylandıktan sonra bu sayfaya tekrar gelerek şifrenizi yenileyebilirsiniz.
            </small>
        """,
        'approved': """
            <strong>İsteğiniz Onaylandı!</strong><br>
            <small>
            Şimdi şifrenizi sıfırlayabilirsiniz. Lütfen aşağıdaki butonu kullanarak yeni şifrenizi belirleyin. Bu link 1 saat geçerlidir.
            </small>
        """,
        'rejected': """
            <strong>İsteğiniz Reddedildi</strong><br>
            <small>
            Şifre sıfırlama isteğiniz bir admin tarafından reddedildi. 
            Daha fazla bilgi almak veya nedenini öğrenmek için lütfen kurumunuzun yetkilisiyle iletişime geçin.
            </small>
        """,
        'completed': """
            <strong>Şifreniz Zaten Güncellendi</strong><br>
            <small>
            Bu istek kullanılarak şifreniz daha önce güncellenmiş. Yeni şifrenizle giriş yapabilirsiniz. 
            Tekrar sıfırlamak isterseniz, yeni bir istek oluşturun.
            </small>
        """
    }
    if long:
        return long_messages.get(status, 'Bilinmeyen durum.')
    return messages.get(status, 'Bilinmeyen durum')

@app.route('/admin/manage-course/<int:course_id>', methods=['GET', 'POST'])
@login_required
def admin_manage_course(course_id):
    if not current_user.is_admin:
        return redirect(url_for('dashboard'))
    
    course = Course.query.get_or_404(course_id)
    categories = Category.query.all()
    
    if request.method == 'POST':
        # Sadece kurs bilgilerini güncelle
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        course.category_id = request.form.get('category_id')
        course.passing_score = request.form.get('passing_score', 70, type=int)
        course.test_required = 'test_required' in request.form
        
        db.session.commit()
        flash('Kurs bilgileri başarıyla güncellendi.', 'success')
        return redirect(url_for('admin_manage_course', course_id=course_id))
    
    return render_template('admin_manage_course.html', course=course, categories=categories)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)