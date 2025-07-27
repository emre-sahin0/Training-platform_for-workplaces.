from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import login_required, current_user
from models import Course, Video, Pdf, Progress, PdfProgress, db
from sqlalchemy.exc import IntegrityError
from datetime import datetime
import os
from werkzeug.utils import secure_filename

course_bp = Blueprint('course', __name__)

@course_bp.route('/<int:course_id>')
@login_required
def view_course(course_id):
    """View course details and content"""
    course = Course.query.get_or_404(course_id)
    
    # Check if user is assigned to this course
    if course not in current_user.assigned_courses and not current_user.is_admin:
        flash('Bu kursa erişim izniniz yok.', 'danger')
        return redirect(url_for('dashboard'))
    
    progress_info = course.get_user_progress(current_user)
    
    # Sort content by order
    videos = sorted(course.videos, key=lambda x: x.order)
    pdfs = sorted(course.pdfs, key=lambda x: x.order)
    
    # Kullanıcı listesi ve ilerleme durumu (sadece admin görsün)
    user_progress_list = []
    if current_user.is_admin:
        for user in course.assigned_users:
            progress = course.get_user_progress(user)
            user_progress_list.append({
                'user': user,
                'progress': progress
            })
    
    return render_template('course.html', 
                         course=course, 
                         videos=videos, 
                         pdfs=pdfs,
                         progress=progress_info,
                         user_progress_list=user_progress_list)

@course_bp.route('/video/<int:video_id>')
@login_required
def video(video_id):
    video = Video.query.get_or_404(video_id)
    course = video.course
    if course not in current_user.assigned_courses and not current_user.is_admin:
        flash('Bu kursa erişim izniniz yok.', 'danger')
        return redirect(url_for('dashboard'))
    ordered_contents = course.get_ordered_contents()
    # Mevcut adım ve toplam adım
    current_step = None
    for idx, item in enumerate(ordered_contents):
        if item['type'] == 'video' and item['object'].id == video.id:
            current_step = idx
            break
    total_steps = len(ordered_contents)
    # Önceki ve sonraki adım url'leri
    prev_url, next_url = None, None
    if current_step is not None:
        if current_step > 0:
            prev = ordered_contents[current_step-1]
            if prev['type'] == 'video':
                prev_url = url_for('course.video', video_id=prev['object'].id)
            elif prev['type'] == 'pdf':
                prev_url = url_for('course.pdf_viewer', pdf_id=prev['object'].id)
            elif prev['type'] == 'test':
                prev_url = url_for('course.pdf_test', course_id=course.id)
        if current_step < total_steps-1:
            nxt = ordered_contents[current_step+1]
            if nxt['type'] == 'video':
                next_url = url_for('course.video', video_id=nxt['object'].id)
            elif nxt['type'] == 'pdf':
                next_url = url_for('course.pdf_viewer', pdf_id=nxt['object'].id)
            elif nxt['type'] == 'test':
                next_url = url_for('course.pdf_test', course_id=course.id)
    # İlerleme bilgisi
    progress = Progress.query.filter_by(user_id=current_user.id, video_id=video.id).first()
    progress_info = course.get_user_progress(current_user)
    return render_template('video.html', video=video, course=course, ordered_contents=ordered_contents, current_step=current_step, total_steps=total_steps, prev_url=prev_url, next_url=next_url, progress=progress, completed_steps=progress_info.completed_steps, progress_percent=progress_info.progress_percent)

@course_bp.route('/pdf_viewer/<int:pdf_id>')
@login_required  
def pdf_viewer(pdf_id):
    pdf = Pdf.query.get_or_404(pdf_id)
    course = pdf.course
    if course not in current_user.assigned_courses and not current_user.is_admin:
        flash('Bu kursa erişim izniniz yok.', 'danger')
        return redirect(url_for('dashboard'))
    ordered_contents = course.get_ordered_contents()
    current_step = None
    for idx, item in enumerate(ordered_contents):
        if item['type'] == 'pdf' and item['object'].id == pdf.id:
            current_step = idx
            break
    total_steps = len(ordered_contents)
    prev_url, next_url = None, None
    if current_step is not None:
        if current_step > 0:
            prev = ordered_contents[current_step-1]
            if prev['type'] == 'video':
                prev_url = url_for('course.video', video_id=prev['object'].id)
            elif prev['type'] == 'pdf':
                prev_url = url_for('course.pdf_viewer', pdf_id=prev['object'].id)
            elif prev['type'] == 'test':
                prev_url = url_for('course.pdf_test', course_id=course.id)
        if current_step < total_steps-1:
            nxt = ordered_contents[current_step+1]
            if nxt['type'] == 'video':
                next_url = url_for('course.video', video_id=nxt['object'].id)
            elif nxt['type'] == 'pdf':
                next_url = url_for('course.pdf_viewer', pdf_id=nxt['object'].id)
            elif nxt['type'] == 'test':
                next_url = url_for('course.pdf_test', course_id=course.id)
    # PDF ilerlemesi (görüntülendi mi?)
    pdf_progress = PdfProgress.query.filter_by(user_id=current_user.id, pdf_id=pdf.id).first()
    progress_info = course.get_user_progress(current_user)
    return render_template('pdf_viewer.html', pdf=pdf, course=course, ordered_contents=ordered_contents, current_step=current_step, total_steps=total_steps, prev_url=prev_url, next_url=next_url, pdf_progress=pdf_progress, completed_steps=progress_info.completed_steps, progress_percent=progress_info.progress_percent)

@course_bp.route('/pdf_test/<int:course_id>', methods=['GET', 'POST'])
@login_required
def pdf_test(course_id):
    course = Course.query.get_or_404(course_id)
    if course not in current_user.assigned_courses and not current_user.is_admin:
        flash('Bu kursa erişim izniniz yok.', 'danger')
        return redirect(url_for('dashboard'))
    from flask import request
    progress_info = course.get_user_progress(current_user)
    # Eğer kullanıcı testi tamamladıysa tekrar girişe izin verme
    if progress_info.passed_test or (hasattr(progress_info, 'test_score') and progress_info.test_score is not None):
        flash('Bu test zaten tamamlandı. Tekrar girişe izin verilmiyor.', 'info')
        return redirect(url_for('course.view_course', course_id=course.id))
    if request.method == 'POST':
        # Test cevaplarını işle
        user_answers = []
        for i in range(1, course.test_question_count + 1):
            user_answers.append(request.form.get(f'q{i}'))
        correct_answers = course.test_answer_key.split(',')
        correct_count = sum(1 for i, answer in enumerate(user_answers)
                            if i < len(correct_answers) and answer and answer.strip() == correct_answers[i].strip())
        score = (correct_count / len(correct_answers)) * 100 if correct_answers else 0
        # Son videoya test sonucu kaydet
        last_video = sorted(course.videos, key=lambda x: x.order)[-1] if course.videos else None
        if last_video:
            progress = Progress.query.filter_by(user_id=current_user.id, video_id=last_video.id).first()
            if progress:
                progress.test_score = score
                progress.test_completed = True
                db.session.commit()
        if score >= course.passing_score:
            flash(f'Tebrikler! Testi başarıyla geçtiniz. Puanınız: {score:.1f}', 'success')
        else:
            flash(f'Test başarısız. Puanınız: {score:.1f}. Geçme puanı: {course.passing_score}', 'warning')
        return redirect(url_for('course.view_course', course_id=course.id))
    # GET isteği için mevcut davranış
    ordered_contents = course.get_ordered_contents()
    current_step = None
    for idx, item in enumerate(ordered_contents):
        if item['type'] == 'test':
            current_step = idx
            break
    total_steps = len(ordered_contents)
    prev_url = None
    if current_step is not None and current_step > 0:
        prev = ordered_contents[current_step-1]
        if prev['type'] == 'video':
            prev_url = url_for('course.video', video_id=prev['object'].id)
        elif prev['type'] == 'pdf':
            prev_url = url_for('course.pdf_viewer', pdf_id=prev['object'].id)
        elif prev['type'] == 'test':
            prev_url = url_for('course.pdf_test', course_id=course.id)
    test_file_type = 'pdf' if course.test_pdf else 'image' if course.test_images else None
    test_file_name = course.test_pdf or course.test_images
    return render_template('pdf_test.html', course=course, ordered_contents=ordered_contents, current_step=current_step, total_steps=total_steps, prev_url=prev_url, test_file_type=test_file_type, test_file_name=test_file_name, completed_steps=progress_info.completed_steps, progress_percent=progress_info.progress_percent)

@course_bp.route('/complete_video/<int:video_id>', methods=['POST'])
@login_required
def complete_video(video_id):
    """
    Videoyu tamamlandı olarak işaretle
    ---
    tags:
      - Course
    parameters:
      - name: video_id
        in: path
        type: integer
        required: true
        description: Video ID
    responses:
      200:
        description: Başarılı tamamlandı
        schema:
          type: object
          properties:
            success:
              type: boolean
      302:
        description: Yönlendirme (HTML response)
    """
    """Mark video as completed"""
    video = Video.query.get_or_404(video_id)
    from flask import request, jsonify
    try:
        progress = Progress(
            user_id=current_user.id,
            video_id=video_id,
            completed=True,
            completed_at=datetime.utcnow()
        )
        db.session.add(progress)
        db.session.commit()
        flash('Video başarıyla tamamlandı!', 'success')
    except IntegrityError:
        db.session.rollback()
        # Update existing record
        existing_progress = Progress.query.filter_by(
            user_id=current_user.id, 
            video_id=video_id
        ).first()
        if existing_progress:
            existing_progress.completed = True
            existing_progress.completed_at = datetime.utcnow()
            db.session.commit()
    # AJAX/fetch isteği ise JSON ile cevap ver
    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True}), 200
    return redirect(url_for('course.view_course', course_id=video.course_id))

@course_bp.route('/submit_test/<int:course_id>', methods=['POST'])
@login_required
def submit_test(course_id):
    """
    Test cevaplarını gönder
    ---
    tags:
      - Course
    parameters:
      - name: course_id
        in: path
        type: integer
        required: true
        description: Kurs ID
      - name: answers
        in: formData
        type: array
        items:
          type: string
        required: true
        description: Kullanıcı cevapları
    responses:
      302:
        description: Yönlendirme (HTML response)
    """
    """Submit test answers"""
    course = Course.query.get_or_404(course_id)
    
    # Calculate score
    user_answers = request.form.getlist('answers')
    correct_answers = course.test_answer_key.split(',')
    
    correct_count = sum(1 for i, answer in enumerate(user_answers) 
                       if i < len(correct_answers) and answer.strip() == correct_answers[i].strip())
    
    score = (correct_count / len(correct_answers)) * 100 if correct_answers else 0
    
    # Find the last completed video to update test score
    last_video = sorted(course.videos, key=lambda x: x.order)[-1] if course.videos else None
    
    if last_video:
        progress = Progress.query.filter_by(
            user_id=current_user.id,
            video_id=last_video.id
        ).first()
        
        if progress:
            progress.test_score = score
            progress.test_completed = True
            db.session.commit()
    
    if score >= course.passing_score:
        flash(f'Tebrikler! Testi başarıyla geçtiniz. Puanınız: {score:.1f}', 'success')
    else:
        flash(f'Test başarısız. Puanınız: {score:.1f}. Geçme puanı: {course.passing_score}', 'warning')
    
    return redirect(url_for('course.view_course', course_id=course_id)) 

@course_bp.route('/<int:course_id>/delete', methods=['POST'])
@login_required
def delete_course(course_id):
    if not current_user.is_admin:
        abort(403)
    course = Course.query.get_or_404(course_id)
    db.session.delete(course)
    db.session.commit()
    flash('Kurs silindi.', 'success')
    return redirect(url_for('admin.courses'))

@course_bp.route('/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_course(course_id):
    if not current_user.is_admin:
        abort(403)
    course = Course.query.get_or_404(course_id)
    from models import Category, Group, User
    if request.method == 'POST':
        course.title = request.form.get('title')
        course.description = request.form.get('description')
        course.category_id = request.form.get('category_id')
        assign_type = request.form.get('assign_type')
        user_ids = request.form.getlist('user_ids')
        group_ids = request.form.getlist('group_ids')
        # Kullanıcı atamalarını güncelle
        assigned_users = set()
        if assign_type == 'users':
            for user_id in user_ids:
                user = User.query.get(user_id)
                if user:
                    assigned_users.add(user)
        elif assign_type == 'groups':
            for group_id in group_ids:
                group = Group.query.get(group_id)
                if group:
                    for user in group.users:
                        assigned_users.add(user)
        course.assigned_users = list(assigned_users)
        db.session.commit()
        flash('Kurs güncellendi.', 'success')
        return redirect(url_for('course.view_course', course_id=course.id))
    users = User.query.filter_by(is_admin=False).all()
    groups = Group.query.all()
    categories = Category.query.all()
    return render_template('edit_course.html', course=course, users=users, groups=groups, categories=categories) 

@course_bp.route('/<int:course_id>/add_video', methods=['GET', 'POST'])
@login_required
def add_video(course_id):
    if not current_user.is_admin:
        abort(403)
    course = Course.query.get_or_404(course_id)
    if request.method == 'POST':
        title = request.form.get('title')
        order = request.form.get('order', type=int)
        file = request.files.get('video_file')
        if not file or not file.filename:
            flash('Video dosyası seçilmedi!', 'danger')
            return redirect(request.url)
        filename = secure_filename(file.filename)
        upload_path = os.path.join('static', 'uploads', filename)
        file.save(upload_path)
        video = Video(title=title, video_path=filename, course_id=course.id, order=order)
        db.session.add(video)
        db.session.commit()
        flash('Video başarıyla eklendi.', 'success')
        return redirect(url_for('course.view_course', course_id=course.id))
    return render_template('add_video.html', course=course) 

@course_bp.route('/mark_pdf_viewed/<int:pdf_id>', methods=['POST'])
@login_required
def mark_pdf_viewed(pdf_id):
    """
    PDF'i görüntülendi olarak işaretle
    ---
    tags:
      - Course
    parameters:
      - name: pdf_id
        in: path
        type: integer
        required: true
        description: PDF ID
    responses:
      200:
        description: Başarılı
        schema:
          type: object
          properties:
            success:
              type: boolean
      500:
        description: Hata
    """
    """Mark PDF as viewed"""
    pdf = Pdf.query.get_or_404(pdf_id)
    from flask import request, jsonify
    
    try:
        # PDF progress oluştur veya güncelle
        existing_progress = PdfProgress.query.filter_by(
            user_id=current_user.id, 
            pdf_id=pdf_id
        ).first()
        
        if not existing_progress:
            pdf_progress = PdfProgress(
                user_id=current_user.id,
                pdf_id=pdf_id,
                viewed_at=datetime.utcnow()
            )
            db.session.add(pdf_progress)
            db.session.commit()
        
        return jsonify({'success': True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500 