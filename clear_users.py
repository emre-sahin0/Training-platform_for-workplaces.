from app import app
from models import db, User, Progress, Certificate

def clear_all_users():
    with app.app_context():
        try:
            # Önce ilgili tabloları temizle
            Progress.query.delete()
            Certificate.query.delete()
            User.query.delete()
            
            db.session.commit()
            print("✅ Tüm kullanıcılar ve ilgili veriler başarıyla silindi!")
            print(f"📊 Kalan kullanıcı sayısı: {User.query.count()}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Hata oluştu: {e}")

if __name__ == '__main__':
    clear_all_users() 