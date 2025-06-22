#!/usr/bin/env python3
import os
import sys
from datetime import datetime

# Veritabanı yolunu belirle
DB_PATH = 'instance/isg.db'

def reset_database():
    """Veritabanını sıfırla ve yeniden oluştur"""
    
    # Eğer veritabanı varsa yedek al
    if os.path.exists(DB_PATH):
        backup_name = f'instance/isg_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        os.rename(DB_PATH, backup_name)
        print(f'✅ Mevcut veritabanı yedeklendi: {backup_name}')
    
    # Yeni veritabanını oluştur
    try:
        from app import app, db
        from models import Category, Course, CertificateType
        
        with app.app_context():
            # Tabloları oluştur
            db.create_all()
            print('✅ Tablolar oluşturuldu')
            
            # Kategorileri ekle
            categories = [
                ('İş Sağlığı ve Güvenliği', 'Zorunlu iş sağlığı ve güvenliği eğitimleri'),
                ('Genel Eğitimler', 'Genel eğitimler ve kişisel gelişim'),
                ('Mağaza Eğitimleri', 'Mağaza çalışanları için özel eğitimler')
            ]
            
            for name, desc in categories:
                if not Category.query.filter_by(name=name).first():
                    cat = Category(name=name, description=desc)
                    db.session.add(cat)
                    print(f'✅ Kategori eklendi: {name}')
            
            db.session.commit()
            
            # Sertifika türlerini ekle
            cat1 = Category.query.filter_by(name='İş Sağlığı ve Güvenliği').first()
            cat2 = Category.query.filter_by(name='Genel Eğitimler').first()
            cat3 = Category.query.filter_by(name='Mağaza Eğitimleri').first()
            
            certificates = [
                ('İş Sağlığı ve Güvenliği Eğitimi Sertifikası', 'İSG zorunlu eğitim sertifikası', cat1.id),
                ('Genel Sertifika', 'Genel eğitimler için sertifika', cat2.id),
                ('Mağaza Eğitim Sertifikası', 'Mağaza çalışanları için eğitim sertifikası', cat3.id)
            ]
            
            for name, desc, cat_id in certificates:
                if not CertificateType.query.filter_by(name=name).first():
                    cert = CertificateType(name=name, description=desc, category_id=cat_id)
                    db.session.add(cert)
                    print(f'✅ Sertifika türü eklendi: {name}')
            
            db.session.commit()
            print('🎉 Veritabanı başarıyla sıfırlandı ve yeniden oluşturuldu!')
            
    except Exception as e:
        print(f'❌ Hata oluştu: {str(e)}')
        return False
    
    return True

if __name__ == '__main__':
    print('🔄 Veritabanını sıfırlıyor...')
    
    # Kullanıcıdan onay al
    response = input('⚠️  Mevcut veritabanı silinecek! Devam etmek istiyor musunuz? (y/N): ')
    
    if response.lower() in ['y', 'yes', 'evet', 'e']:
        if reset_database():
            print('✅ İşlem tamamlandı!')
        else:
            print('❌ İşlem başarısız!')
            sys.exit(1)
    else:
        print('❌ İşlem iptal edildi.') 