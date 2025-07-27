from datetime import datetime
from .base import db

# Association table for course-group many-to-many relationship
course_groups = db.Table('course_groups',
    db.Column('course_id', db.Integer, db.ForeignKey('course.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True)
)

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
    passing_score = db.Column(db.Integer, default=70)
    test_required = db.Column(db.Boolean, default=True, nullable=False)
    groups = db.relationship('Group', secondary='course_groups', back_populates='courses')

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
        
        # PDF ilerlemesi
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
            total_steps += 1  # Test için bir adım ekle
            if passed_test:
                completed_steps += 1
        
        # İlerleme yüzdesini hesapla
        if total_steps == 0:
            progress_percent = 100.0
        else:
            progress_percent = (completed_steps / total_steps) * 100
            # Yüzdeyi 100'le sınırla
            progress_percent = min(progress_percent, 100.0)

        # Return namedtuple for consistency
        ProgressInfo = namedtuple('ProgressInfo', [
            'completed_videos', 'total_videos', 'all_videos_watched',
            'completed_pdfs', 'total_pdfs', 'all_pdfs_viewed',
            'all_content_completed', 'passed_test', 'test_score', 'progress_percent',
            'completed_steps', 'total_steps'
        ])
        
        return ProgressInfo(
            completed_videos=completed_videos_count,
            total_videos=total_videos,
            all_videos_watched=all_videos_watched,
            completed_pdfs=completed_pdfs_count,
            total_pdfs=total_pdfs,
            all_pdfs_viewed=all_pdfs_viewed,
            all_content_completed=all_content_completed,
            passed_test=passed_test,
            test_score=test_score,
            progress_percent=progress_percent,
            completed_steps=completed_steps,
            total_steps=total_steps
        )

    def get_ordered_contents(self):
        """Kursun tüm içeriklerini (video, pdf) ve varsa testi sıralı şekilde döndürür.
        Her içerik: {'type': 'video'/'pdf'/'test', 'object': <Video/Pdf/None>, 'order': int}
        Test varsa en sona eklenir.
        """
        contents = []
        for v in self.videos:
            contents.append({'type': 'video', 'object': v, 'order': v.order})
        for p in self.pdfs:
            contents.append({'type': 'pdf', 'object': p, 'order': p.order})
        # Sıralama: önce order'a göre, sonra type'a göre (video önce)
        contents.sort(key=lambda x: (x['order'], 0 if x['type']=='video' else 1))
        # Test varsa en sona ekle
        if self.test_required and (self.test_pdf or self.test_images or self.test_answer_key):
            contents.append({'type': 'test', 'object': None, 'order': (max([c['order'] for c in contents], default=0) + 1)})
        return contents

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    video_path = db.Column(db.String(200), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order = db.Column(db.Integer, default=1)

class Pdf(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    pdf_path = db.Column(db.String(200), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    order = db.Column(db.Integer, default=1)

class Progress(db.Model):
    __table_args__ = (
        db.UniqueConstraint('user_id', 'video_id', name='unique_user_video_progress'),
        db.Index('ix_progress_user_id', 'user_id'),
        db.Index('ix_progress_video_id', 'video_id'),
    )
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'), nullable=False)
    completed = db.Column(db.Boolean, default=False)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)
    test_score = db.Column(db.Integer, nullable=True)

class PdfProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    pdf_id = db.Column(db.Integer, db.ForeignKey('pdf.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow) 