#!/usr/bin/env python3
"""
Migration script to copy data from old database to new structure
"""

import os
import shutil
import sqlite3
from app import create_app
from models import db, Category
from models.category import Certificate
from datetime import datetime
import uuid

def migrate_database():
    """Migrate data from old database to new structure"""
    app = create_app()
    
    with app.app_context():
        print("🔄 Starting database migration...")
        
        # Path to old database
        old_db_path = '../instance/isg.db'
        new_db_path = 'app.db'
        
        if os.path.exists(old_db_path):
            print(f"📋 Found old database: {old_db_path}")
            
            # Create new database structure
            db.create_all()
            print("✅ New database structure created")
            
            # Copy the old database file as backup and use it
            if os.path.exists(old_db_path):
                shutil.copy2(old_db_path, 'old_backup.db')
                shutil.copy2(old_db_path, new_db_path)
                print("✅ Database copied successfully")
            
        else:
            print("⚠️  Old database not found, creating fresh database")
            db.create_all()
            
            # Create default admin user
            from models import User
            if not User.query.filter_by(username='admin').first():
                admin = User(
                    username='admin',
                    email='admin@trt.com.tr',
                    first_name='Admin',
                    last_name='User',
                    is_admin=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("✅ Default admin user created (username: admin, password: admin123)")
        
        # Kategorilerden herhangi biri yoksa ekle
        categories = [
            "İş Sağlığı ve Güvenliği",
            "Mağaza Eğitimleri",
            "Genel Olarak"
        ]
        for cat_name in categories:
            if not Category.query.filter_by(name=cat_name).first():
                db.session.add(Category(name=cat_name))
        db.session.commit()
        
        print("🎉 Migration completed successfully!")

        # Admin kullanıcısını yeniden oluştur (şifre hash sorunu için)
        try:
            admin_user = User.query.filter_by(username='admin').first()
            if not admin_user:
                admin = User(
                    username='admin',
                    email='admin@trt.com.tr',
                    first_name='Admin',
                    last_name='User',
                    is_admin=True
                )
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                print("✅ Admin kullanıcısı oluşturuldu (username: admin, password: admin123)")
            else:
                # Mevcut admin'in şifresini yenile (hash sorununu çözmek için)
                admin_user.set_password('admin123')
                db.session.commit()
                print("✅ Admin kullanıcısı şifresi yenilendi")
        except Exception as e:
            print(f"Admin kullanıcı oluşturma hatası: {e}")
            db.session.rollback()

        # Sertifika güncelleme - eski database'de course_id olmayabilir
        try:
            certs = Certificate.query.filter((Certificate.certificate_number==None)|(Certificate.issued_at==None)).all()
            updated = 0
            for cert in certs:
                if not cert.certificate_number:
                    cert.certificate_number = f'CERT-{uuid.uuid4().hex[:8].upper()}'
                if not cert.issued_at:
                    cert.issued_at = datetime.utcnow()
                updated += 1
            if updated > 0:
                db.session.commit()
            print(f"{updated} sertifika güncellendi.")
        except Exception as e:
            print(f"Sertifika güncellemesi atlandı (eski database formatı): {e}")
            db.session.rollback()
            print("0 sertifika güncellendi.")

if __name__ == '__main__':
    migrate_database() 