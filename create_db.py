from app import app, db
from models import Category, Course, CertificateType

def create_db():
    """Database'i oluştur ve temel verileri ekle"""
    with app.app_context():
        db.create_all()
        # Kategorileri kontrol et ve ekle
        cat1 = Category.query.filter_by(name='İş Sağlığı ve Güvenliği').first()
        if not cat1:
            cat1 = Category(name='İş Sağlığı ve Güvenliği', description='Zorunlu iş sağlığı ve güvenliği eğitimleri')
            db.session.add(cat1)
            db.session.commit()
            print('İş Sağlığı ve Güvenliği kategorisi eklendi.')
        cat2 = Category.query.filter_by(name='Genel Eğitimler').first()
        if not cat2:
            cat2 = Category(name='Genel Eğitimler', description='Genel eğitimler ve kişisel gelişim')
            db.session.add(cat2)
            db.session.commit()
            print('Genel Eğitimler kategorisi eklendi.')
        cat3 = Category.query.filter_by(name='Mağaza Eğitimleri').first()
        if not cat3:
            cat3 = Category(name='Mağaza Eğitimleri', description='Mağaza çalışanları için özel eğitimler')
            db.session.add(cat3)
            db.session.commit()
            print('Mağaza Eğitimleri kategorisi eklendi.')
        # Kurs ekle
        if not Course.query.first():
            course = Course(title='Temel İş Sağlığı Eğitimi', description='Temel iş sağlığı eğitimi kursu', category_id=cat1.id)
            db.session.add(course)
            db.session.commit()
            print('Kurs eklendi.')
        # Belge türlerini kontrol et ve ekle
        cert1 = CertificateType.query.filter_by(name='İş Sağlığı ve Güvenliği Eğitimi Sertifikası').first()
        if not cert1:
            cert1 = CertificateType(name='İş Sağlığı ve Güvenliği Eğitimi Sertifikası', description='İSG zorunlu eğitim sertifikası', category_id=cat1.id)
            db.session.add(cert1)
            db.session.commit()
            print('İş Sağlığı ve Güvenliği Eğitimi Sertifikası eklendi.')
        cert2 = CertificateType.query.filter_by(name='Genel Sertifika').first()
        if not cert2:
            cert2 = CertificateType(name='Genel Sertifika', description='Genel eğitimler için sertifika', category_id=cat2.id)
            db.session.add(cert2)
            db.session.commit()
            print('Genel Sertifika eklendi.')
        cert3 = CertificateType.query.filter_by(name='Mağaza Eğitim Sertifikası').first()
        if not cert3:
            cert3 = CertificateType(name='Mağaza Eğitim Sertifikası', description='Mağaza çalışanları için eğitim sertifikası', category_id=cat3.id)
            db.session.add(cert3)
            db.session.commit()
            print('Mağaza Eğitim Sertifikası eklendi.')
        print('Veritabanı ve tablolar başarıyla oluşturuldu.')

if __name__ == '__main__':
    create_db() 