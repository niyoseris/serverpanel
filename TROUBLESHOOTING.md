# VDS Panel - Troubleshooting Guide

## "Failed to start project locally. Check logs for details."

Bu hata, projenin virtual environment'ı (venv) eksik olduğunda veya gerekli bağımlılıklar kurulu olmadığında oluşur.

### Çözüm Adımları

#### 1. Proje Klasörüne Git
```bash
cd /path/to/your/project
```

#### 2. Virtual Environment Oluştur
```bash
python3 -m venv venv
```

#### 3. Virtual Environment'ı Aktif Et
```bash
source venv/bin/activate
```

#### 4. Bağımlılıkları Kur
```bash
pip install -r requirements.txt
```

#### 5. Gunicorn'u Kur (eğer requirements.txt'de yoksa)
```bash
pip install gunicorn
```

#### 6. VDS Panel'den Projeyi Başlat
- Panel'e geri dön
- Projeyi "Start" butonuyla başlat
- Artık çalışması gerekiyor!

---

## "Log file not found."

Bu sorun artık düzeltildi! Şimdi panel log dosyalarını doğru yerden okuyacak:
1. Proje klasörünün içinden (`/your/project/name.out.log`)
2. Panel root dizininden
3. Linux sistemlerde `/var/log/` dizininden

### Log Dosyası Konumları

**Local Development (macOS/Windows):**
```
/path/to/project/projectname.out.log
/path/to/project/projectname.err.log
```

**Production (Linux Supervisor):**
```
/var/log/projectname.out.log
/var/log/projectname.err.log
```

---

## Proje Başlatma Kontrol Listesi

Panel şimdi başlatmadan önce otomatik kontrol yapıyor ve size uyarılar veriyor:

### ✅ Kontroller:
1. **Proje dizini var mı?**
2. **Virtual environment var mı?** (venv, .venv, env klasörleri)
3. **Gunicorn kurulu mu?**

### Uyarı Mesajları:

#### "Warning: No virtual environment found"
```bash
# Çözüm:
cd /your/project/path
python3 -m venv venv
venv/bin/pip install -r requirements.txt
venv/bin/pip install gunicorn
```

#### "Warning: Gunicorn not found in project venv"
```bash
# Çözüm:
cd /your/project/path
source venv/bin/activate
pip install gunicorn
```

---

## Yaygın Hatalar ve Çözümleri

### 1. Port Çakışması
**Hata:** `Address already in use`

**Çözüm:**
- Proje ayarlarından farklı bir port seçin
- Veya çakışan servisi durdurun:
```bash
# Port'u kullanan servisi bul
lsof -i :PORT_NUMBER

# Process'i durdur
kill PID
```

### 2. Permission Denied
**Hata:** `Permission denied: '/path/to/project'`

**Çözüm:**
```bash
# Dosya izinlerini düzelt
chmod -R 755 /path/to/project
```

### 3. ModuleNotFoundError
**Hata:** `ModuleNotFoundError: No module named 'flask'`

**Çözüm:**
Bağımlılıkları tekrar kur:
```bash
cd /your/project
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Import Error
**Hata:** `cannot import name 'app' from 'app'`

**Çözüm:**
Entry point'i kontrol edin:
- Flask: `app:app` veya `run:app`
- Django: `projectname.wsgi:application`

Panel'de **Settings** sekmesinden entry point'i düzenleyebilirsiniz.

---

## Debug İpuçları

### 1. Log Dosyalarını Manuel Kontrol
```bash
# Proje klasöründe
cat /path/to/project/projectname.err.log

# Production'da
tail -f /var/log/projectname.err.log
```

### 2. Manuel Başlatma Testi
```bash
cd /path/to/project
source venv/bin/activate

# Flask test
python app.py

# Gunicorn test
gunicorn -w 1 -b 0.0.0.0:5000 app:app
```

### 3. Dependency Check
```bash
cd /path/to/project
source venv/bin/activate
pip list  # Kurulu paketleri listele
```

### 4. VDS Panel Terminal Output
VDS Panel'i terminal'den çalıştırıp hata mesajlarını görebilirsiniz:
```bash
cd /Users/niyoseris/Desktop/Python/vdspanel
source venv/bin/activate
python run.py
```

Tarayıcıda işlem yaparken terminal'de detaylı debug output görürsünüz.

---

## Sunucu (Production) İçin

### Log İzleme
```bash
# VDS Panel logs
journalctl -u vdspanel -f

# Belirli bir proje
tail -f /var/log/projectname.err.log
```

### Servis Durumu
```bash
# Panel durumu
systemctl status vdspanel

# Supervisor durumu (varsa)
supervisorctl status
```

### Process Kontrolü
```bash
# Çalışan Python processleri
ps aux | grep python

# Port kullanımı
ss -tuln | grep :PORT
```

---

## Hızlı Komutlar

### Local Development
```bash
# Panel'i başlat
cd /Users/niyoseris/Desktop/Python/vdspanel
source venv/bin/activate
python run.py

# Access: http://localhost:5012
```

### Production
```bash
# SSH bağlan
ssh root@YOUR_SERVER_IP

# Panel'i yeniden başlat
systemctl restart vdspanel

# Log'ları izle
journalctl -u vdspanel -f
```

---

## İletişim ve Destek

Sorun devam ediyorsa:
1. Log dosyalarını kontrol edin
2. Terminal output'u kontrol edin
3. Proje venv ve bağımlılıklarını kontrol edin
4. Entry point doğru mu kontrol edin

Panel artık daha detaylı hata mesajları veriyor, bu mesajları takip edin!
