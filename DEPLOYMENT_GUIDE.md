# VDS Deployment Guide

Bu rehber, VDS Panel'i sunucunuza yüklemeniz için hazırlanmıştır.

## Hızlı Başlangıç

```bash
# 1. SSH key kurulumu (tek seferlik, şifresiz giriş için)
bash setup_ssh.sh

# 2. Sunucu analizi (opsiyonel, mevcut uygulamaları görmek için)
bash deploy.sh

# 3. Deployment (projeyi yükle ve çalıştır)
bash deploy_to_server.sh
```

## Adım Adım Kurulum

### Adım 1: SSH Key Kurulumu (Şifresiz Giriş)

```bash
bash setup_ssh.sh
```

Bu script:
- SSH key pair oluşturur (varsa kullanır)
- Public key'i sunucuya yükler
- Bir kez root şifresi ister
- Ardından şifresiz giriş aktif olur

**Not:** Root şifresini sadece bir kez girmeniz gerekir.

### Adım 2: Sunucu Analizi (Opsiyonel)

Mevcut uygulamaları ve portları görmek için:

```bash
bash deploy.sh
```

Bu script sunucuda çalışan:
- Python uygulamalarını
- Kullanılan portları
- Nginx konfigürasyonlarını
- Supervisor servislerini
listeler.

### Adım 3: Deployment

Ana deployment script'ini çalıştırın:

```bash
bash deploy_to_server.sh
```

Bu script otomatik olarak:
1. ✓ Projeyi paketler
2. ✓ Sunucuya yükler
3. ✓ Sistem bağımlılıklarını kurar (nginx, certbot, supervisor)
4. ✓ Python virtual environment oluşturur
5. ✓ Bağımlılıkları yükler
6. ✓ Admin kullanıcı oluşturur
7. ✓ Systemd service oluşturur
8. ✓ Port 5012'de başlatır
9. ✓ Firewall kurallarını ayarlar
10. ✓ Otomatik başlatmayı aktif eder

## Deployment Sonrası

### Panel'e Erişim

Panel şu adreste çalışacak:
```
http://YOUR_SERVER_IP:5012
```

**Varsayılan Giriş Bilgileri:**
- Kullanıcı adı: `admin`
- Şifre: `changeme123`

⚠️ **ÖNEMLİ:** İlk girişten sonra mutlaka şifreyi değiştirin!

### Servis Yönetimi

Sunucuda aşağıdaki komutları kullanabilirsiniz:

```bash
# SSH ile sunucuya bağlan (artık şifre istenmez)
ssh root@YOUR_SERVER_IP

# Servis durumunu kontrol et
systemctl status vdspanel

# Servisi yeniden başlat
systemctl restart vdspanel

# Servisi durdur
systemctl stop vdspanel

# Servisi başlat
systemctl start vdspanel

# Log'ları izle (canlı)
journalctl -u vdspanel -f

# Son 100 satır log
journalctl -u vdspanel -n 100
```

### Dosya Konumları

```
/opt/vdspanel/              # Ana uygulama dizini
/opt/vdspanel/venv/         # Virtual environment
/opt/vdspanel/instance/     # Veritabanı
/opt/vdspanel/uploads/      # Upload edilen projeler
/opt/vdspanel/*.log         # Log dosyaları
/etc/systemd/system/vdspanel.service  # Systemd service dosyası
```

## Güvenlik

### Firewall Portları

Script otomatik olarak şu portları açar:
- 5012 (VDS Panel)
- 80 (HTTP)
- 443 (HTTPS)

### SSH Güvenliği

SSH key kurulduktan sonra, ek güvenlik için password authentication'ı kapatabilirsiniz:

```bash
ssh root@YOUR_SERVER_IP

# SSH config'i düzenle
nano /etc/ssh/sshd_config

# Bu satırı bulun ve değiştirin:
PasswordAuthentication no

# SSH'yi yeniden başlatın
systemctl restart sshd
```

⚠️ **UYARI:** Bunu yapmadan önce SSH key ile bağlanabildiğinizden emin olun!

## Mevcut Uygulamalarla Çakışma Önleme

VDS Panel port 5012 kullanır. Bu port çakışma yapmamalıdır çünkü:
- Standart web portları (80, 443, 8000, 8080, 3000, 5000) değil
- Panel kendi projeleri için diğer portları kullanır
- Nginx reverse proxy ile domain routing yapılır

### Çakışma Durumunda

Eğer port 5012 kullanımdaysa, `deploy_to_server.sh` dosyasını düzenleyin:

```bash
nano deploy_to_server.sh

# Bu satırı değiştirin:
APP_PORT="5012"
# Şuna:
APP_PORT="5013"  # veya başka boş bir port
```

## Domain Yapılandırması (Opsiyonel)

Panel'e domain üzerinden erişmek için:

1. DNS ayarlarınızda A kaydı ekleyin:
   ```
   panel.yourdomain.com  →  YOUR_SERVER_IP
   ```

2. Panel'de yeni proje oluştururken:
   - Domain: panel.yourdomain.com
   - Port: 5012
   - SSL: Aktif et (Let's Encrypt)

3. Nginx reverse proxy otomatik yapılandırılır
4. SSL sertifikası otomatik alınır

## Sorun Giderme

### Panel açılmıyor

```bash
# Servis durumunu kontrol et
systemctl status vdspanel

# Log'lara bak
journalctl -u vdspanel -n 50

# Port'u kontrol et
ss -tuln | grep 5012
```

### Database hatası

```bash
cd /opt/vdspanel
source venv/bin/activate
python run.py create-user admin newpassword
```

### Servisi tamamen yeniden kur

```bash
systemctl stop vdspanel
cd /opt/vdspanel
rm -rf instance/vdspanel.db
source venv/bin/activate
python run.py create-user admin newpassword
systemctl start vdspanel
```

## Güncelleme

Proje güncellemesi yapmak için:

```bash
# Yerel değişiklikleri yap, sonra:
bash deploy_to_server.sh
```

Bu komut:
1. Servisi durdurur
2. Yeni dosyaları yükler
3. Servisi yeniden başlatır
4. Veritabanı ve konfigürasyonu korur

## Destek

Sorun yaşarsanız:
1. Log dosyalarını kontrol edin
2. Service status'u kontrol edin
3. Port'ların açık olduğundan emin olun
4. Firewall kurallarını kontrol edin

## Hızlı Erişim Komutları

```bash
# SSH bağlantısı (şifresiz)
ssh root@YOUR_SERVER_IP

# Panel log'larını izle
ssh root@YOUR_SERVER_IP "journalctl -u vdspanel -f"

# Panel'i yeniden başlat
ssh root@YOUR_SERVER_IP "systemctl restart vdspanel"

# Servis durumu
ssh root@YOUR_SERVER_IP "systemctl status vdspanel"
```
