import sqlite3
from app import app
from models import db

def show_tables():
    """Tüm tabloları listele"""
    with app.app_context():
        connection = sqlite3.connect('instance/isg.db')
        cursor = connection.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("📋 Veritabanındaki Tablolar:")
        for table in tables:
            print(f"  • {table[0]}")
            
        connection.close()

def show_table_data(table_name):
    """Belirli bir tablonun verilerini göster"""
    with app.app_context():
        connection = sqlite3.connect('instance/isg.db')
        cursor = connection.cursor()
        
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 10;")
            rows = cursor.fetchall()
            
            # Sütun adlarını al
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [column[1] for column in cursor.fetchall()]
            
            print(f"\n📊 {table_name} Tablosu (İlk 10 Kayıt):")
            print("Sütunlar:", columns)
            for row in rows:
                print(row)
                
        except Exception as e:
            print(f"❌ Hata: {e}")
        
        connection.close()

def count_records():
    """Tüm tablolardaki kayıt sayılarını say"""
    with app.app_context():
        connection = sqlite3.connect('instance/isg.db')
        cursor = connection.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print("\n📈 Kayıt Sayıları:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"  • {table_name}: {count} kayıt")
        
        connection.close()

if __name__ == '__main__':
    print("=== SQLite Veritabanı Yöneticisi ===")
    show_tables()
    count_records()
    
    # Kullanıcı tablosu varsa detaylarını göster
    show_table_data('user') 