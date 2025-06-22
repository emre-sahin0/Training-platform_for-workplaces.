from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask import session

db = SQLAlchemy()
login_manager = LoginManager()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

assigned_courses = db.Table('assigned_courses',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    progress = db.relationship('Progress', backref='user', lazy=True)
    assigned_courses = db.relationship('Course', secondary='assigned_courses', back_populates='assigned_users')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected, completed
    token = db.Column(db.String(100), unique=True, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    user = db.relationship('User', foreign_keys=[user_id], backref='password_reset_requests')
    admin = db.relationship('User', foreign_keys=[approved_by], backref='approved_resets')

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    courses = db.relationship('Course', backref='category', lazy=True)
    certificate_types = db.relationship('CertificateType', backref='category', lazy=True)

class CertificateType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    required_course_count = db.Column(db.Integer, default=1)  # Bu belge türü için gerekli minimum kurs sayısı
    courses = db.relationship('Course', backref='certificate_type', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    certificate_type_id = db.Column(db.Integer, db.ForeignKey('certificate_type.id'), nullable=True)
    videos = db.relationship('Video', backref='course', lazy=True, cascade="all, delete-orphan")
    pdfs = db.relationship('Pdf', backref='course', lazy=True, cascade="all, delete-orphan")
    tests = db.relationship('Test', backref='course', lazy=True, cascade="all, delete-orphan")
    test_pdf = db.Column(db.String(200))
    test_question_count = db.Column(db.Integer)
    test_answer_key = db.Column(db.String(200))
    test_images = db.Column(db.Text)
    assigned_users = db.relationship('User', secondary='assigned_courses', back_populates='assigned_courses')
    passing_score = db.Column(db.Integer, default=70)  # Geçme notu
    test_required = db.Column(db.Boolean, default=True, nullable=False)

    def get_user_progress(self, user):
        """Kullanıcının bu kurstaki ilerlemesini detaylı olarak hesaplar."""
        from collections import namedtuple
        
        # Video ilerlemesi
        video_ids = {v.id for v in self.videos}
        completed_videos_count = Progress.query.filter(
            Progress.user_id == user.id,
            Progress.video_id.in_(video_ids),
            Progress.completed == True
        ).count()
        
        # PDF ilerlemesi (database'den al)
        pdf_ids = {p.id for p in self.pdfs}
        completed_pdfs_count = PdfProgress.query.filter(
            PdfProgress.user_id == user.id,
            PdfProgress.pdf_id.in_(pdf_ids)
        ).count()
        
        total_videos = len(video_ids)
        total_pdfs = len(pdf_ids)
        all_videos_watched = completed_videos_count >= total_videos and total_videos > 0
        all_pdfs_viewed = completed_pdfs_count >= total_pdfs and total_pdfs > 0
        
        # Tüm içerik tamamlandı mı?
        all_content_completed = True
        if total_videos > 0:
            all_content_completed = all_content_completed and all_videos_watched
        if total_pdfs > 0:
            all_content_completed = all_content_completed and all_pdfs_viewed

        # Test ilerlemesi
        passed_test = False
        test_score = None
        if self.test_required and all_content_completed:
            # Test sonucu, kursun son videosuyla ilişkilendirilen Progress'te saklanır.
            course_videos = sorted(self.videos, key=lambda v: v.order)
            last_video = course_videos[-1] if course_videos else None
            
            if last_video:
                test_progress = Progress.query.filter_by(user_id=user.id, video_id=last_video.id).first()
                if test_progress and test_progress.test_score is not None:
                    passed_test = test_progress.test_score >= self.passing_score
                    test_score = test_progress.test_score

        # Toplam ilerleme hesaplama
        completed_steps = completed_videos_count + completed_pdfs_count
        total_steps = total_videos + total_pdfs
        
        if self.test_required:
            total_steps += 1
            if passed_test:
                completed_steps += 1

        progress_percent = int((completed_steps / total_steps) * 100) if total_steps > 0 else 0
        is_completed = all_content_completed and (not self.test_required or passed_test)

        ProgressDetails = namedtuple('ProgressDetails', [
            'completed_steps', 'total_steps', 'progress_percent', 
            'all_videos_watched', 'all_pdfs_viewed', 'all_content_completed',
            'passed_test', 'is_completed', 'test_score'
        ])
        
        return ProgressDetails(
            completed_steps=completed_steps,
            total_steps=total_steps,
            progress_percent=progress_percent,
            all_videos_watched=all_videos_watched,
            all_pdfs_viewed=all_pdfs_viewed,
            all_content_completed=all_content_completed,
            passed_test=passed_test,
            is_completed=is_completed,
            test_score=test_score
        )

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_path = db.Column(db.String(200), nullable=False)
    duration = db.Column(db.Integer)  # Duration in seconds
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)  # For maintaining video sequence
    progress = db.relationship('Progress', backref='video', lazy=True, cascade="all, delete-orphan")

    def get_progress(self, user):
        """Belirli bir kullanıcının bu video için ilerlemesini döndürür."""
        return Progress.query.filter_by(user_id=user.id, video_id=self.id).first()

class Pdf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    pdf_path = db.Column(db.String(200), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    passing_score = db.Column(db.Integer, nullable=False)
    questions = db.relationship('Question', backref='test', lazy=True)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    options = db.relationship('Option', backref='question', lazy=True)

class Option(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)

class Progress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime)
    test_score = db.Column(db.Integer)
    test_completed = db.Column(db.Boolean, default=False)

class Announcement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref='certificates')
    certificate_type_id = db.Column(db.Integer, db.ForeignKey('certificate_type.id'), nullable=False)
    certificate_type = db.relationship('CertificateType', backref='certificates')
    issue_date = db.Column(db.DateTime, default=datetime.utcnow)
    certificate_number = db.Column(db.String(50), unique=True)
    courses = db.relationship('Course', secondary='certificate_courses', backref='certificates')
    certificate_file = db.Column(db.String(200))  # Yüklenen sertifika dosya yolu

certificate_courses = db.Table('certificate_courses',
    db.Column('certificate_id', db.Integer, db.ForeignKey('certificate.id'), primary_key=True),
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True)
)

class PdfProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdf.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='pdf_progress')
    pdf = db.relationship('Pdf', backref='pdf_progress')
    
    # Unique constraint to prevent duplicate entries
    __table_args__ = (db.UniqueConstraint('user_id', 'pdf_id', name='unique_user_pdf'),) 