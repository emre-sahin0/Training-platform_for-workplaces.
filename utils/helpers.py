from flask import flash, redirect, url_for
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3

def register_error_handlers(app):
    """Register error handlers for the application"""
    
    @app.errorhandler(413)
    def request_entity_too_large(error):
        """Handle file too large error"""
        max_size_mb = app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024)
        flash(f'❌ Dosya çok büyük! Maximum {max_size_mb:.0f}MB yükleyebilirsiniz.', 'danger')
        return redirect(url_for('admin.new_course'))
    
    @app.errorhandler(404)
    def not_found_error(error):
        flash('Aradığınız sayfa bulunamadı.', 'warning')
        return redirect(url_for('user.dashboard'))
    
    @app.errorhandler(500)
    def internal_error(error):
        flash('Bir hata oluştu. Lütfen daha sonra tekrar deneyin.', 'danger')
        return redirect(url_for('user.dashboard'))

def setup_sqlite_optimizations():
    """Setup SQLite performance optimizations"""
    
    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """SQLite performance optimizations"""
        if isinstance(dbapi_connection, sqlite3.Connection):
            cursor = dbapi_connection.cursor()
            # Performance optimizations
            cursor.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            cursor.execute("PRAGMA synchronous=NORMAL")  # Faster sync
            cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
            cursor.execute("PRAGMA temp_store=MEMORY")  # Memory temp storage
            cursor.close()
            print("🔧 SQLite PRAGMA optimizations applied")

def password_policy_check(password):
    """Check if password meets security requirements"""
    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalı."
    if not any(c.isupper() for c in password):
        return False, "Şifre en az bir büyük harf içermeli."
    if not any(c.islower() for c in password):
        return False, "Şifre en az bir küçük harf içermeli."
    if not any(c.isdigit() for c in password):
        return False, "Şifre en az bir rakam içermeli."
    if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
        return False, "Şifre en az bir özel karakter içermeli (!@#$%^&* vb.)."
    return True, "" 

def generate_certificate_pdf(user_fullname, course_title, score, date_str, output_path, certificate_number=None):
    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    
    # Sayfa boyutu (yatay A4)
    width, height = landscape(A4)
    c = canvas.Canvas(output_path, pagesize=(width, height))
    
    # Türkçe karakter desteği için encoding
    c._doc.defaultEncoding = 'utf-8'
    
    # Renkler
    navy = HexColor('#1a365d')           
    gold = HexColor('#d69e2e')           
    light_blue = HexColor('#ebf8ff')     
    dark_gray = HexColor('#2d3748')      
    blue = HexColor('#3182ce')           
    
    # Beyaz arka plan
    c.setFillColor(HexColor('#ffffff'))
    c.rect(0, 0, width, height, fill=1, stroke=0)
    
    # Güvenli alan hesaplama - sayfa kenarlarından 2cm içerde
    margin = 2*cm
    safe_width = width - 2*margin
    safe_height = height - 2*margin
    
    # Dış çerçeve
    c.setStrokeColor(gold)
    c.setLineWidth(4)
    c.rect(margin, margin, safe_width, safe_height, fill=0, stroke=1)
    
    # İç çerçeve
    inner_margin = margin + 0.5*cm
    c.setStrokeColor(navy)
    c.setLineWidth(2)
    c.rect(inner_margin, inner_margin, safe_width-1*cm, safe_height-1*cm, fill=0, stroke=1)
    
    # Y pozisyonlarını matematiksel olarak hesapla
    content_height = safe_height - 2*cm  # İç çerçeve için
    top_y = height - margin - 1*cm
    
    # Y pozisyonları
    y1 = top_y - 1*cm                    # ANA BAŞLIK
    y2 = y1 - 1*cm                       # BASARI BELGESI  
    y3 = y2 - 1*cm                       # Çizgi
    y4 = y3 - 2*cm                       # Bu belge ile
    y5 = y4 - 2*cm                       # İsim
    y6 = y5 - 1.5*cm                     # AdaWall metin başlangıç
    y7 = y6 - 0.8*cm                     # İkinci satır
    y8 = y7 - 0.8*cm                     # Üçüncü satır
    y9 = y8 - 2*cm                       # Kurs kutusu
    y10 = y9 - 2*cm                      # Puan
    
    # ANA BAŞLIK
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 32)
    title_text = "TRT EGITIM SERTIFIKASI"
    c.drawCentredString(width/2, y1, title_text)
    
    # Alt başlık
    c.setFont("Helvetica", 14)
    subtitle_text = "BASARI BELGESI"
    c.drawCentredString(width/2, y2, subtitle_text)
    
    # Altın çizgi
    c.setStrokeColor(gold)
    c.setLineWidth(3)
    line_width = 8*cm
    c.line(width/2 - line_width/2, y3, width/2 + line_width/2, y3)
    
    # Ana metin
    c.setFillColor(dark_gray)
    c.setFont("Helvetica", 16)
    text1 = "Bu belge ile onaylanir ki"
    c.drawCentredString(width/2, y4, text1)
    
    # Kullanıcı adı
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, y5, user_fullname.upper())
    
    # Ana açıklama metni - 3 satırda
    c.setFillColor(dark_gray)
    c.setFont("Helvetica", 16)
    
    text_line1 = "TRT Egitim Platformunda asagidaki"
    text_line2 = "egitimi basariyla tamamlamistir ve"
    text_line3 = "yeterlilik kazanmistir."
    
    c.drawCentredString(width/2, y6, text_line1)
    c.drawCentredString(width/2, y7, text_line2)
    c.drawCentredString(width/2, y8, text_line3)
    
    # Kurs adı kutusu
    # Kurs ismini basit şekilde işle
    course_display = course_title.replace('ğ', 'g').replace('ü', 'u').replace('ş', 's').replace('ı', 'i').replace('ç', 'c').replace('ö', 'o')
    course_display = course_display.replace('Ğ', 'G').replace('Ü', 'U').replace('Ş', 'S').replace('İ', 'I').replace('Ç', 'C').replace('Ö', 'O')
    
    text_width = len(course_display) * 0.5*cm
    box_width = max(text_width + 2*cm, 8*cm)
    box_height = 1.5*cm
    
    # Kutu genişliği sayfa genişliğini aşmasın
    if box_width > safe_width - 2*cm:
        box_width = safe_width - 2*cm
    
    box_x = (width - box_width) / 2
    
    c.setFillColor(light_blue)
    c.setStrokeColor(blue)
    c.setLineWidth(2)
    c.rect(box_x, y9 - box_height/2, box_width, box_height, fill=1, stroke=1)
    
    # Kurs adı
    c.setFillColor(blue)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width/2, y9 - 0.2*cm, course_display)
    
    # Test puanı
    if score is not None:
        c.setFillColor(gold)
        c.setFont("Helvetica-Bold", 16)
        score_text = f"Basari Notu: %{int(score)}"
        c.drawCentredString(width/2, y10, score_text)
    
    # Alt bilgiler - sabit pozisyonlar
    footer_y = margin + 1.5*cm
    
    # Sertifika numarası - sol
    c.setFillColor(dark_gray)
    c.setFont("Helvetica", 11)
    if certificate_number:
        cert_text = f"Sertifika No: {certificate_number}"
        c.drawString(margin + 0.5*cm, footer_y, cert_text)
    
    # Tarih - sağ
    date_text = f"Tarih: {date_str}"
    c.drawRightString(width - margin - 0.5*cm, footer_y, date_text)
    
    # Platform adı - orta
    footer_y -= 0.8*cm
    c.setFillColor(navy)
    c.setFont("Helvetica-Bold", 12)
    platform_text = "TRT Egitim Platformu"
    c.drawCentredString(width/2, footer_y, platform_text)
    
    # Web sitesi
    footer_y -= 0.6*cm
    c.setFillColor(dark_gray)
    c.setFont("Helvetica", 10)
    c.drawCentredString(width/2, footer_y, "www.trt.com.tr")
    
    # Köşe süsleri
    c.setFillColor(gold)
    corner_size = 0.25*cm
    corner_margin = margin + 0.8*cm
    
    c.circle(corner_margin, height - corner_margin, corner_size, fill=1, stroke=0)
    c.circle(width - corner_margin, height - corner_margin, corner_size, fill=1, stroke=0)
    c.circle(corner_margin, corner_margin, corner_size, fill=1, stroke=0)
    c.circle(width - corner_margin, corner_margin, corner_size, fill=1, stroke=0)
    
    c.showPage()
    c.save() 