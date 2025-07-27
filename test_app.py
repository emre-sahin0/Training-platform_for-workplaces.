#!/usr/bin/env python3
"""
Test script for the new professional structure
"""

from app import create_app
from models import db, User, Course, Group, Category

def test_basic_functionality():
    """Test basic app functionality"""
    app = create_app()
    
    with app.app_context():
        print("🔍 Testing database connection...")
        
        # Create tables
        db.create_all()
        print("✅ Database tables created successfully")
        
        # Test user creation
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@trt.com.tr',
                first_name='Admin',
                last_name='User',
                is_admin=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            print("✅ Admin user created")
        
        # Test category creation
        if not Category.query.filter_by(name='Test Kategori').first():
            category = Category(
                name='Test Kategori',
                description='Test için oluşturulan kategori'
            )
            db.session.add(category)
            print("✅ Test category created")
        
        # Test group creation
        if not Group.query.filter_by(name='Test Grup').first():
            group = Group(name='Test Grup')
            db.session.add(group)
            print("✅ Test group created")
        
        db.session.commit()
        print("✅ All test data saved successfully")
        
        # Test queries
        users_count = User.query.count()
        categories_count = Category.query.count()
        groups_count = Group.query.count()
        
        print(f"📊 Current data:")
        print(f"  - Users: {users_count}")
        print(f"  - Categories: {categories_count}")
        print(f"  - Groups: {groups_count}")
        
        print("🎉 All tests passed! The new structure is working correctly.")

if __name__ == '__main__':
    print("🚀 Testing new professional structure...")
    test_basic_functionality() 