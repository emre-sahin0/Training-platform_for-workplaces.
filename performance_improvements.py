#!/usr/bin/env python3
"""
Advanced Performance Improvements for VPS
Bu script sistem performansını en üst seviyeye çıkarmak için gelişmiş optimizasyonlar içerir
"""

import os
import sqlite3
from datetime import datetime

def optimize_sqlite_database():
    """SQLite database'i performans için optimize et"""
    db_path = 'instance/isg.db'
    
    if not os.path.exists(db_path):
        print("❌ Database dosyası bulunamadı!")
        return
    
    print("🔧 SQLite database optimizasyonu başlıyor...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # WAL mode aktive et (Write-Ahead Logging)
        cursor.execute("PRAGMA journal_mode = WAL;")
        print("✅ WAL mode aktif")
        
        # Synchronous mode'u optimize et
        cursor.execute("PRAGMA synchronous = NORMAL;")
        print("✅ Synchronous mode optimized")
        
        # Cache size'ı artır (64MB)
        cursor.execute("PRAGMA cache_size = -64000;")
        print("✅ Cache size increased to 64MB")
        
        # Temp store'u memory'de tut
        cursor.execute("PRAGMA temp_store = MEMORY;")
        print("✅ Temp store set to memory")
        
        # Auto vacuum aktive et
        cursor.execute("PRAGMA auto_vacuum = INCREMENTAL;")
        print("✅ Auto vacuum enabled")
        
        # Analyze komutu ile statistics güncelle
        cursor.execute("ANALYZE;")
        print("✅ Database statistics updated")
        
        # VACUUM ile database'i optimize et
        print("🔄 Running VACUUM (this may take a while)...")
        cursor.execute("VACUUM;")
        print("✅ Database vacuumed")
        
        conn.commit()
        conn.close()
        
        print("🎉 SQLite optimization completed!")
        
    except Exception as e:
        print(f"❌ Optimization error: {e}")

def create_optimized_indexes():
    """Performance için optimize edilmiş indexler oluştur"""
    db_path = 'instance/isg.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("📊 Creating optimized indexes...")
        
        # Progress tablosu için composite index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_progress_user_video 
            ON progress(user_id, video_id);
        """)
        
        # Progress tablosu için completed index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_progress_completed 
            ON progress(completed, completed_at);
        """)
        
        # User tablosu için email index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_email 
            ON user(email);
        """)
        
        # Course tablosu için category index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_course_category 
            ON course(category_id);
        """)
        
        # Video tablosu için course+order index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_video_course_order 
            ON video(course_id, "order");
        """)
        
        # PDF tablosu için course+order index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pdf_course_order 
            ON pdf(course_id, "order");
        """)
        
        # PdfProgress tablosu için user+pdf index
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pdf_progress_user_pdf 
            ON pdf_progress(user_id, pdf_id);
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Optimized indexes created!")
        
    except Exception as e:
        print(f"❌ Index creation error: {e}")

def cleanup_upload_folder():
    """Upload klasörünü temizle ve optimize et"""
    upload_folder = 'static/uploads'
    
    if not os.path.exists(upload_folder):
        print("❌ Upload folder bulunamadı!")
        return
    
    print("🧹 Upload folder cleanup başlıyor...")
    
    total_size = 0
    file_count = 0
    
    # Tüm dosyaları tara
    for root, dirs, files in os.walk(upload_folder):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                file_size = os.path.getsize(file_path)
                total_size += file_size
                file_count += 1
            except:
                pass
    
    total_size_mb = total_size / (1024 * 1024)
    
    print(f"📊 Upload folder stats:")
    print(f"   📁 Total files: {file_count}")
    print(f"   💾 Total size: {total_size_mb:.1f}MB")
    
    # 1GB üzerindeyse uyarı ver
    if total_size_mb > 1024:
        print("⚠️  Upload folder çok büyük! Temizlik yapılması önerilir.")
    else:
        print("✅ Upload folder boyutu normal")

def optimize_system_performance():
    """Sistem performansını genel olarak optimize et"""
    print("🚀 System Performance Optimization")
    print("=" * 50)
    
    # SQLite optimizasyonu
    optimize_sqlite_database()
    print()
    
    # Index optimizasyonu
    create_optimized_indexes()
    print()
    
    # Upload folder temizliği
    cleanup_upload_folder()
    print()
    
    print("🎉 All optimizations completed!")
    print("\n📋 Öneriler:")
    print("1. Flask uygulamasını restart edin")
    print("2. Browser cache'ini temizleyin") 
    print("3. Büyük dosyalar için sıkıştırma kullanın")
    print("4. Düzenli olarak bu optimizasyonu çalıştırın")

def monitor_performance():
    """Performance metrikleri göster"""
    print("📊 Performance Monitoring")
    print("=" * 30)
    
    # Database boyutu
    db_path = 'instance/isg.db'
    if os.path.exists(db_path):
        db_size = os.path.getsize(db_path) / (1024 * 1024)
        print(f"💾 Database size: {db_size:.1f}MB")
    
    # Upload folder boyutu
    upload_folder = 'static/uploads'
    if os.path.exists(upload_folder):
        total_size = 0
        for root, dirs, files in os.walk(upload_folder):
            for file in files:
                try:
                    total_size += os.path.getsize(os.path.join(root, file))
                except:
                    pass
        upload_size = total_size / (1024 * 1024)
        print(f"📁 Upload folder size: {upload_size:.1f}MB")
    
    # Memory usage (requires psutil)
    try:
        import psutil
        memory = psutil.virtual_memory()
        print(f"💻 System memory: {memory.percent}% used")
        print(f"💿 Disk usage: {psutil.disk_usage('/').percent}%")
    except ImportError:
        print("⚠️  psutil not installed - install for detailed monitoring")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == 'optimize':
            optimize_system_performance()
        elif command == 'monitor':
            monitor_performance()
        elif command == 'database':
            optimize_sqlite_database()
        elif command == 'indexes':
            create_optimized_indexes()
        elif command == 'cleanup':
            cleanup_upload_folder()
        else:
            print("❌ Unknown command")
    else:
        print("🎯 Performance Improvements Tool")
        print("\nKullanım:")
        print("  python performance_improvements.py optimize    # Tüm optimizasyonları yap")
        print("  python performance_improvements.py monitor     # Performance'ı izle")
        print("  python performance_improvements.py database    # Sadece database'i optimize et")
        print("  python performance_improvements.py indexes     # Sadece indexleri oluştur")
        print("  python performance_improvements.py cleanup     # Upload folder'ı temizle") 