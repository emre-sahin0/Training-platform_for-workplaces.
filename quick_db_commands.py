from app import app
from models import db, User, Course, Video, Progress

def create_admin_user():
    """Hızlıca admin kullanıcısı oluştur"""
    with app.app_context():
        admin = User(
            username='admin',
            email='admin@example.com',
            first_name='Admin',
            last_name='User',
            is_admin=True
        )
        admin.set_password('Admin123!')
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin kullanıcısı oluşturuldu!")
        print("   Kullanıcı adı: admin")
        print("   Şifre: Admin123!")

def clear_all_data():
    """Tüm verileri temizle (tablolar kalır)"""
    with app.app_context():
        Progress.query.delete()
        Video.query.delete()
        Course.query.delete()
        User.query.delete()
        db.session.commit()
        print("✅ Tüm veriler temizlendi!")

def show_user_count():
    """Kullanıcı sayısını göster"""
    with app.app_context():
        count = User.query.count()
        print(f"👥 Toplam kullanıcı sayısı: {count}")
        if count > 0:
            users = User.query.all()
            for user in users:
                print(f"  • {user.username} ({user.email}) - {'Admin' if user.is_admin else 'User'}")

if __name__ == '__main__':
    print("=== Hızlı DB Komutları ===")
    print("1. Kullanıcı sayısını kontrol et")
    show_user_count()
    
    print("\n2. Admin kullanıcısı oluştur")
    create_admin_user()
    
    print("\n3. Son durum")
    show_user_count() 