from flask import current_app, url_for
from flask_mail import Mail, Message

mail = Mail()

def send_password_reset_email(user, token):
    """Send password reset email to user"""
    subject = "TRT Eğitim Platformu - Şifre Sıfırlama"
    
    reset_url = url_for('reset_password_with_token', token=token, _external=True)
    
    body = f"""
    Merhaba {user.first_name},
    
    TRT Eğitim Platformu için şifre sıfırlama talebiniz alınmıştır.
    
    Şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın:
    {reset_url}
    
    Bu bağlantı 1 saat geçerlidir.
    
    Eğer bu talebi siz yapmadıysanız, bu e-postayı görmezden gelebilirsiniz.
    
    TRT Eğitim Platformu
    """
    
    # Development modunda email'i console'a yazdır
    if current_app.config.get('DEBUG') or not current_app.config.get('MAIL_USERNAME'):
        print("="*50)
        print("🔐 DEVELOPMENT MODE - EMAIL SIMÜLASYONU")
        print("="*50)
        print(f"Alıcı: {user.email}")
        print(f"Konu: {subject}")
        print(f"Reset URL: {reset_url}")
        print("="*50)
        return True
    
    # Production modunda gerçek email gönder
    try:
        msg = Message(
            subject=subject,
            recipients=[user.email],
            body=body,
            sender=current_app.config['MAIL_DEFAULT_SENDER']
        )
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email gönderme hatası: {e}")
        raise e 