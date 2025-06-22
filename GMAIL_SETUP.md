# Admin Onaylı Şifre Sıfırlama Sistemi

## 🔐 Sistem Nasıl Çalışır?

### 1. **Kullanıcı İsteği Gönderir**
- Login sayfasında "Şifremi unuttum" linkine tıklar
- E-posta adresini girer
- İstek admin onayına gönderilir

### 2. **Admin Onayı**
- Admin panelinde "Şifre Sıfırlama İstekleri" sayfasına gider
- Bekleyen istekleri görür
- İsteği onaylar ve yeni şifre belirler
- Şifreyi günceller

### 3. **Kullanıcı Bilgilendirilir**
- Kullanıcı durumu kontrol edebilir
- Admin şifreyi güncellediğinde bilgilendirilir

## 🎯 Avantajlar

- ✅ **Güvenli:** Admin kontrolü ile
- ✅ **Basit:** E-posta ayarı gerektirmez
- ✅ **Hızlı:** Anında işlem
- ✅ **Kontrol:** Admin tüm istekleri görür
- ✅ **Ücretsiz:** Ek maliyet yok

## 🚀 Kullanım

### Kullanıcı Tarafı:
1. Login sayfasında "Şifremi unuttum" tıkla
2. E-posta adresini gir
3. İsteği gönder
4. Durumu kontrol et

### Admin Tarafı:
1. Admin panelinde "Şifre Sıfırlama İstekleri" seç
2. Bekleyen istekleri gör
3. İsteği onayla ve yeni şifre belirle
4. Şifreyi güncelle

## 📊 İstek Durumları

- **Bekliyor (Pending):** Admin onayını bekliyor
- **Onaylandı (Approved):** Admin onayladı, şifre belirlendi
- **Reddedildi (Rejected):** Admin reddetti
- **Tamamlandı (Completed):** Şifre güncellendi

## 🔧 Kurulum

Sistem otomatik olarak çalışır. Ek kurulum gerektirmez.

### VPS'de Kullanım:
```bash
# Git'ten güncelle
git pull origin main

# PM2'yi yeniden başlat
pm2 restart trainplatform
```

## 📱 Özellikler

- ✅ **Gerçek Zamanlı:** Durum anında kontrol edilir
- ✅ **Güvenli:** Admin onayı zorunlu
- ✅ **Kullanıcı Dostu:** Basit arayüz
- ✅ **Responsive:** Mobil uyumlu
- ✅ **Türkçe:** Tam Türkçe destek

## 🎉 Sonuç

Bu sistem sayesinde:
- Kullanıcılar şifrelerini kolayca sıfırlatabilir
- Adminler tüm istekleri kontrol edebilir
- Güvenlik maksimum seviyede
- Maliyet sıfır 