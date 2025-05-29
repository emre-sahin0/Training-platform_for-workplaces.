from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

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
    videos = db.relationship('Video', backref='course', lazy=True)
    tests = db.relationship('Test', backref='course', lazy=True)
    test_pdf = db.Column(db.String(200))
    test_question_count = db.Column(db.Integer)
    test_answer_key = db.Column(db.String(200))
    test_images = db.Column(db.Text)
    assigned_users = db.relationship('User', secondary='assigned_courses', back_populates='assigned_courses')
    passing_score = db.Column(db.Integer, default=70)  # Geçme notu

    def get_user_progress(self, user):
        """Calculate user's progress for this course."""
        from collections import namedtuple
        Progress = namedtuple('Progress', ['completed', 'total'])
        
        # Get all video IDs for this course
        video_ids = {v.id for v in self.videos}
        
        # Count completed videos
        completed = len({p.video_id for p in user.progress 
                        if p.completed and p.video_id in video_ids})
        
        # Total is the number of videos in the course
        total = len(video_ids)
        
        return Progress(completed=completed, total=total)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_path = db.Column(db.String(200), nullable=False)
    duration = db.Column(db.Integer)  # Duration in seconds
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)  # For maintaining video sequence
    progress = db.relationship('Progress', backref='video', lazy=True)

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