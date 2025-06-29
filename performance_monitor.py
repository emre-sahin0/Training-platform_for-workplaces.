#!/usr/bin/env python3
"""
VPS Performance Monitor - Sistem kaynaklarını izler ve loglar
Bu script VPS'deki sistem performansını izlemek için kullanılır
"""

import psutil
import time
import logging
from datetime import datetime
import os

# Logging ayarları
logging.basicConfig(
    filename='performance.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_system_info():
    """Sistem bilgilerini al"""
    try:
        # CPU kullanımı
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory kullanımı
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available = memory.available / (1024**3)  # GB
        
        # Disk kullanımı
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        disk_free = disk.free / (1024**3)  # GB
        
        # Network I/O (varsa)
        try:
            network = psutil.net_io_counters()
            bytes_sent = network.bytes_sent / (1024**2)  # MB
            bytes_recv = network.bytes_recv / (1024**2)  # MB
        except:
            bytes_sent = bytes_recv = 0
        
        # Load average
        try:
            load_avg = os.getloadavg()
            load_1min = load_avg[0]
        except:
            load_1min = 0
        
        return {
            'timestamp': datetime.now().isoformat(),
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent,
            'memory_available_gb': round(memory_available, 2),
            'disk_percent': disk_percent,
            'disk_free_gb': round(disk_free, 2),
            'network_sent_mb': round(bytes_sent, 2),
            'network_recv_mb': round(bytes_recv, 2),
            'load_1min': round(load_1min, 2)
        }
    except Exception as e:
        logging.error(f"Sistem bilgileri alınamadı: {e}")
        return None

def check_performance_issues(info):
    """Performance sorunlarını kontrol et"""
    warnings = []
    
    if info['cpu_percent'] > 80:
        warnings.append(f"⚠️ Yüksek CPU kullanımı: %{info['cpu_percent']}")
    
    if info['memory_percent'] > 85:
        warnings.append(f"⚠️ Yüksek RAM kullanımı: %{info['memory_percent']}")
    
    if info['disk_percent'] > 90:
        warnings.append(f"⚠️ Disk dolumu: %{info['disk_percent']}")
    
    if info['disk_free_gb'] < 1:
        warnings.append(f"⚠️ Çok az disk alanı: {info['disk_free_gb']}GB")
    
    if info['load_1min'] > 2:
        warnings.append(f"⚠️ Yüksek system load: {info['load_1min']}")
    
    return warnings

def monitor_system(duration_minutes=5, interval_seconds=30):
    """Sistemi belirli süre izle"""
    print(f"🔍 Sistem {duration_minutes} dakika boyunca {interval_seconds}s aralıklarla izleniyor...")
    print("📊 Performans raporları 'performance.log' dosyasına kaydediliyor\n")
    
    end_time = time.time() + (duration_minutes * 60)
    
    while time.time() < end_time:
        info = get_system_info()
        if info:
            # Console'a anlık bilgi yazdır
            print(f"⏱️  {info['timestamp'][:19]}")
            print(f"💻 CPU: %{info['cpu_percent']:<5} | RAM: %{info['memory_percent']:<5} | Disk: %{info['disk_percent']}")
            print(f"💾 Available RAM: {info['memory_available_gb']}GB | Free Disk: {info['disk_free_gb']}GB")
            print(f"🌐 Network: ↑{info['network_sent_mb']}MB ↓{info['network_recv_mb']}MB | Load: {info['load_1min']}")
            
            # Performans sorunlarını kontrol et
            warnings = check_performance_issues(info)
            for warning in warnings:
                print(warning)
                logging.warning(warning)
            
            # Log'a kaydet
            logging.info(f"System Stats: {info}")
            print("-" * 70)
        
        time.sleep(interval_seconds)
    
    print("✅ Monitoring tamamlandı!")

def get_disk_usage_by_directory():
    """Upload klasörünün disk kullanımını kontrol et"""
    upload_dirs = [
        'static/uploads',
        'instance',
        'migrations'
    ]
    
    print("📁 Klasör boyutları:")
    for directory in upload_dirs:
        if os.path.exists(directory):
            total_size = 0
            file_count = 0
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                        file_count += 1
                    except:
                        pass
            
            size_mb = total_size / (1024 * 1024)
            print(f"  {directory:<20}: {size_mb:>8.1f}MB ({file_count} dosya)")
        else:
            print(f"  {directory:<20}: Bulunamadı")

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == 'quick':
            # Hızlı kontrol
            info = get_system_info()
            if info:
                print("🚀 Anlık Sistem Durumu:")
                print(f"💻 CPU: %{info['cpu_percent']}")
                print(f"💾 RAM: %{info['memory_percent']} (Available: {info['memory_available_gb']}GB)")
                print(f"💿 Disk: %{info['disk_percent']} (Free: {info['disk_free_gb']}GB)")
                print(f"📈 Load: {info['load_1min']}")
                
                warnings = check_performance_issues(info)
                if warnings:
                    print("\n⚠️  Uyarılar:")
                    for warning in warnings:
                        print(f"  {warning}")
                else:
                    print("\n✅ Sistem normal çalışıyor")
        
        elif sys.argv[1] == 'disk':
            get_disk_usage_by_directory()
        
        elif sys.argv[1] == 'monitor':
            duration = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            monitor_system(duration_minutes=duration)
    else:
        print("🎯 VPS Performance Monitor")
        print("\nKullanım:")
        print("  python performance_monitor.py quick     # Anlık durum")
        print("  python performance_monitor.py disk      # Disk kullanımı")
        print("  python performance_monitor.py monitor 5 # 5 dakika izle") 