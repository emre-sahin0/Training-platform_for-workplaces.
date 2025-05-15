from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
import os
from datetime import datetime
import openpyxl
from config import Config
from models import db, login_manager, User, Course, Video, Test, Question, Option, Progress, Announcement
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'

    return app

app = create_app()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
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
    if request.method == 'POST':
        course = Course(
            title=request.form.get('title'),
            description=request.form.get('description')
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
    return render_template('new_course.html', users=users)

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
    headers = ['Kullanıcı', 'E-posta', 'Kurs', 'Tamamlanan Video', 'Toplam Video', 'İlerleme (%)', 'Test Sonucu', 'Durum', 'Tamamlanma Tarihi']
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
        ws.cell(row=row, column=4, value=completed_videos)
        ws.cell(row=row, column=5, value=total_videos)
        percent_cell = ws.cell(row=row, column=6, value=f"{percent}%")
        percent_cell.alignment = Alignment(horizontal='center')
        percent_cell.fill = PatternFill(start_color='A1C4FD', end_color='A1C4FD', fill_type='solid')
        ws.cell(row=row, column=7, value=test_score)
        status_cell = ws.cell(row=row, column=8, value=test_status)
        if test_status == 'Tamamlandı':
            status_cell.fill = PatternFill(start_color='43E97B', end_color='43E97B', fill_type='solid')
            status_cell.font = Font(bold=True, color='222222')
        else:
            status_cell.fill = PatternFill(start_color='FFB347', end_color='FFB347', fill_type='solid')
            status_cell.font = Font(bold=True, color='222222')
        ws.cell(row=row, column=9, value=last_completed_at)
        for col in range(1, 10):
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
    progress = Progress.query.filter_by(user_id=current_user.id, video_id=video_id).first()
    if not progress:
        progress = Progress(user_id=current_user.id, video_id=video_id)
        db.session.add(progress)
    
    progress.completed = True
    progress.completed_at = datetime.utcnow()
    db.session.commit()
    
    return {'success': True}

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
            flash('Tüm alanları doldurun.')
            return render_template('register.html')
        if password != confirm:
            flash('Şifreler eşleşmiyor.')
            return render_template('register.html')
        if User.query.filter_by(username=username).first():
            flash('Bu kullanıcı adı zaten alınmış.')
            return render_template('register.html')
        if User.query.filter_by(email=email).first():
            flash('Bu e-posta zaten kayıtlı.')
            return render_template('register.html')
        
        # Admin şifre kontrolü
        if is_admin:
            if not admin_password or admin_password != app.config['ADMIN_REGISTRATION_KEY']:
                flash('Geçersiz admin kayıt şifresi.')
                return render_template('register.html')

        user = User(username=username, email=email, first_name=first_name, last_name=last_name, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Kayıt başarılı! Giriş yapabilirsiniz.')
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
    users = User.query.filter_by(is_admin=False).all()
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        # Kullanıcı atamalarını güncelle
        assigned_user_ids = request.form.getlist('assigned_users')
        course.assigned_users = User.query.filter(User.id.in_(assigned_user_ids)).all()
        db.session.commit()
        flash('Kurs güncellendi.')
        return redirect(url_for('course', course_id=course_id))
    return render_template('edit_course.html', course=course, users=users)

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

@app.route('/course/<int:course_id>/pdf-test', methods=['GET', 'POST'])
@login_required
def pdf_test(course_id):
    course = Course.query.get_or_404(course_id)
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
        # Sonucu Progress'e veya ayrı bir tabloya kaydet (şimdilik Progress'e son video üzerinden kaydediyoruz)
        last_video = Video.query.filter_by(course_id=course_id).order_by(Video.order.desc()).first()
        if last_video:
            progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
            if not progress:
                progress = Progress(user_id=current_user.id, video_id=last_video.id)
                db.session.add(progress)
            progress.test_score = percent
            progress.test_completed = percent >= 70  # 70 barajı örnek
            progress.completed_at = datetime.utcnow()
            db.session.commit()
        flash(f'Test tamamlandı! Başarı: %{percent}')
        return redirect(url_for('course', course_id=course_id))

    return render_template('pdf_test.html', course=course, test_file_type=test_file_type, test_file_name=test_file_name)

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True) 