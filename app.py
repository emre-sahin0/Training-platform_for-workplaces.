from dotenv import load_dotenv
load_dotenv()
from flask import Flask, render_template, request, redirect, url_for
from flask_migrate import Migrate
from models.base import db, login_manager
from services.email_service import mail
from config import Config
from controllers.video_stream import video_stream_bp
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user
# from flasgger import Swagger



def create_app():
    """Application Factory Pattern"""
    app = Flask(__name__)
    app.config.from_object(Config)
    # Swagger(app)
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    mail.init_app(app)
    
    # Initialize migration
    migrate = Migrate(app, db)
    
    # Register Blueprints
    from controllers.auth import auth_bp
    from controllers.admin import admin_bp
    from controllers.course import course_bp
    from controllers.user import user_bp
    from controllers.api_auth import api_auth_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(course_bp, url_prefix='/course')
    app.register_blueprint(user_bp)
    app.register_blueprint(api_auth_bp)
    app.register_blueprint(video_stream_bp)
    
    # Rate Limiter
    limiter = Limiter(app=app, key_func=get_remote_address, default_limits=["100 per minute"])
    
    # Import all route functions
    from controllers.user import dashboard, profile, certificates, delete_account
    from controllers.auth import login, logout, register, forgot_password, reset_password_with_token
    from controllers.admin import (courses, users, groups, reports, new_course, announcements, 
                                 certificates as admin_certificates, certificate_operations, 
                                 user_certificates as admin_user_certificates, database, password_requests,
                                 approve_password_request, reject_password_request,
                                 delete_group, edit_group, download_multi_report, backup_database,
                                 export_database, import_database, reset_database, edit_user, delete_user, admin_dashboard)
    from controllers.course import view_course, video, pdf_viewer, pdf_test
    
    # Add old-style routes for template compatibility
    def index():
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated and getattr(current_user, 'is_admin', False):
            return redirect(url_for('admin_dashboard'))
        return render_template('index.html')
    app.add_url_rule('/', 'index', index)
    def dashboard_router():
        if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated and getattr(current_user, 'is_admin', False):
            return redirect(url_for('admin_dashboard'))
        return dashboard()
    app.add_url_rule('/dashboard', 'dashboard', dashboard_router, methods=['GET'])
    app.add_url_rule('/login', 'login', login, methods=['GET', 'POST'])
    app.add_url_rule('/logout', 'logout', logout)
    app.add_url_rule('/register', 'register', register, methods=['GET', 'POST'])
    app.add_url_rule('/forgot_password', 'forgot_password', forgot_password, methods=['GET', 'POST'])
    app.add_url_rule('/reset_password/<token>', 'reset_password_with_token', reset_password_with_token, methods=['GET', 'POST'])
    app.add_url_rule('/profile', 'profile', profile, methods=['GET', 'POST'])
    app.add_url_rule('/user_certificates', 'user_certificates', certificates)
    app.add_url_rule('/delete_account', 'delete_account', delete_account, methods=['POST'])
    
    # Admin routes
    app.add_url_rule('/admin_courses', 'admin_courses', courses)
    app.add_url_rule('/admin_users', 'admin_users', users)
    app.add_url_rule('/admin_groups', 'admin_groups', groups, methods=['GET', 'POST'])
    app.add_url_rule('/admin_reports', 'admin_reports', reports)
    app.add_url_rule('/new_course', 'new_course', new_course, methods=['GET', 'POST'])
    app.add_url_rule('/admin_announcements', 'admin_announcements', announcements, methods=['GET', 'POST'])
    app.add_url_rule('/admin_certificates', 'admin_certificates', admin_certificates)
    app.add_url_rule('/admin_certificate_operations', 'admin_certificate_operations', certificate_operations, methods=['GET', 'POST'])
    app.add_url_rule('/admin_user_certificates', 'admin_user_certificates', admin_user_certificates)
    app.add_url_rule('/admin_database', 'admin_database', database)
    app.add_url_rule('/admin_password_requests', 'admin_password_requests', password_requests)
    app.add_url_rule('/approve_password_request/<int:request_id>', 'approve_password_request', approve_password_request, methods=['POST'])
    app.add_url_rule('/reject_password_request/<int:request_id>', 'reject_password_request', reject_password_request, methods=['POST'])
    app.add_url_rule('/delete_group/<int:group_id>', 'delete_group', delete_group, methods=['POST'])
    app.add_url_rule('/edit_group/<int:group_id>', 'edit_group', edit_group, methods=['GET', 'POST'])
    app.add_url_rule('/edit_user/<int:user_id>', 'edit_user', edit_user, methods=['GET', 'POST'])
    app.add_url_rule('/delete_user/<int:user_id>', 'delete_user', delete_user, methods=['POST'])
    app.add_url_rule('/download_multi_report', 'download_multi_report', download_multi_report, methods=['POST'])
    app.add_url_rule('/backup_database', 'backup_database', backup_database, methods=['POST'])
    app.add_url_rule('/export_database', 'export_database', export_database, methods=['POST'])
    app.add_url_rule('/import_database', 'import_database', import_database, methods=['POST'])
    app.add_url_rule('/reset_database', 'reset_database', reset_database, methods=['POST'])
    
    # Course routes  
    app.add_url_rule('/course/<int:course_id>', 'course', view_course)
    app.add_url_rule('/video/<int:video_id>', 'video', video)
    app.add_url_rule('/pdf_viewer/<int:pdf_id>', 'pdf_viewer', pdf_viewer)
    app.add_url_rule('/pdf_test/<int:course_id>', 'pdf_test', pdf_test)
    
    # Error handlers
    from utils.helpers import register_error_handlers
    register_error_handlers(app)
    
    # SQLite optimizations
    from utils.helpers import setup_sqlite_optimizations
    setup_sqlite_optimizations()
    
    return app 