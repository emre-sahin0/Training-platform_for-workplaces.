from datetime import datetime
from .base import db

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
    required_course_count = db.Column(db.Integer, default=1)
    courses = db.relationship('Course', backref='certificate_type', lazy=True)

class Certificate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    certificate_path = db.Column(db.String(200), nullable=False)
    certificate_number = db.Column(db.String(32), unique=True, nullable=True)
    
    user = db.relationship('User', backref='certificates')
    course = db.relationship('Course', backref='certificates') 