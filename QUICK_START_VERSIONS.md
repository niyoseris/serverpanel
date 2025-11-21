# Versiyon Yönetimi - Hızlı Başlangıç

## 🎯 Yapılanlar

VDS Panel'e tam otomatik versiyon yönetimi sistemi eklendi!

## 🚀 Kurulum (Otomatik)

Veritabanı tabloları uygulamayı başlattığınızda otomatik olarak oluşturulur:

```bash
# Virtual environment'ı aktifleştir (varsa)
source venv/bin/activate

# Uygulamayı başlat - otomatik migration
python run.py
```

veya manuel migration için:

```bash
source venv/bin/activate
python migrate_versions.py
```

## ✨ Özellikler

### 1. Otomatik Yedekleme ✅
- Mevcut bir projeyi yeniden yüklediğinizde, eski versiyon otomatik olarak yedeklenir
- Hiçbir veri kaybı riski yok!

### 2. Kolay Versiyon Görüntüleme 📦
- Proje detay sayfasında yeni "Versions" butonu
- Tüm versiyonları tek sayfada görün
- Her versiyonun boyutunu ve tarihini görün

### 3. Tek Tıkla Geri Yükleme 🔄
- Herhangi bir versiyona geri dönün
- Güvenlik için geri yükleme öncesi otomatik yedek

### 4. Disk Alanı Yönetimi 🧹
- Eski versiyonları temizleyin
- En son N adet versiyonu tutun

## 📝 Kullanım Örnekleri

### Senaryo 1: Proje Güncelleme
1. "Upload Project" sayfasına git
2. Mevcut proje adını kullan (örn: "myapp")
3. Yeni dosyaları yükle
4. ✓ Eski versiyon otomatik yedeklendi!
5. ✓ Yeni versiyon aktif!

### Senaryo 2: Versiyonları Görüntüleme
1. Proje detay sayfasına git
2. "Versions" butonuna tık
3. Tüm versiyonları gör (v1, v2, v3...)

### Senaryo 3: Eski Versiyona Dön
1. Versions sayfasında istediğin versiyonu bul
2. "Restore" butonuna tık
3. Onayla
4. ✓ Eski versiyon aktif!

## 🛠️ Teknik Bilgiler

### Yeni Dosyalar
```
app/
├── models.py (güncellendi)          # ProjectVersion modeli eklendi
├── routes.py (güncellendi)          # 4 yeni route eklendi
├── utils/
│   └── version_manager.py (YENİ)   # Versiyon yönetimi logic
└── templates/
    ├── project_versions.html (YENİ) # Versiyon listesi UI
    ├── project_details.html (güncellendi)
    └── upload_project.html (güncellendi)

backups/ (YENİ)                      # Tüm yedekler burada
migrate_versions.py (YENİ)           # Migration script
VERSION_MANAGEMENT.md (YENİ)         # Detaylı dokümantasyon
```

### Yeni Routes
- `GET /projects/<id>/versions` - Versiyonları listele
- `POST /projects/<id>/versions/<version_id>/restore` - Geri yükle
- `POST /projects/<id>/versions/<version_id>/delete` - Sil
- `POST /projects/<id>/versions/cleanup` - Temizle

### Database Schema
```sql
CREATE TABLE project_version (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    backup_path VARCHAR(512) NOT NULL,
    created_at DATETIME,
    description TEXT,
    FOREIGN KEY(project_id) REFERENCES project(id)
);
```

## 🎨 UI Değişiklikleri

1. **Upload Project Sayfası**
   - Yeni bilgi kutusu: "Mevcut projeyi güncellerseniz otomatik yedek alınır"

2. **Project Details Sayfası**
   - Yeni "Versions" butonu (Start/Stop yanında)

3. **Yeni Versions Sayfası**
   - Modern, glassmorphism tasarım
   - Her versiyon için: numara, tarih, boyut, açıklama
   - Restore/Delete butonları
   - Cleanup bölümü

## 🔒 Güvenlik

- Geri yükleme öncesi otomatik güvenlik yedeği
- Hata durumunda rollback
- Çalışan projeleri otomatik durdurma
- Onay diyalogları (restore/delete için)

## 💡 İpuçları

1. **Disk Alanı**: Düzenli olarak eski versiyonları temizleyin
2. **Güncelleme**: İlk güncellemeden sonra versiyonlar oluşmaya başlar
3. **Restore**: Restore her zaman mevcut durumu yedekler
4. **Cleanup**: Varsayılan 5 versiyon tutun, gerekirse değiştirin

## 🐛 Sorun Giderme

**Versions butonu görünmüyor?**
- Sayfayı yenile
- Tarayıcı cache'ini temizle

**Backup oluşturulmuyor?**
- Disk alanını kontrol et
- `backups/` klasör izinlerini kontrol et

**Migration hatası?**
- `python migrate_versions.py` komutunu çalıştır
- Veritabanı bağlantısını kontrol et

## 📚 Daha Fazla Bilgi

Detaylı dokümantasyon için: `VERSION_MANAGEMENT.md`

## ✅ Test Checklist

- [ ] Migration script çalıştırıldı
- [ ] Yeni proje yüklendi
- [ ] Aynı proje güncellendi (v1 oluştu mu?)
- [ ] İkinci güncelleme yapıldı (v2 oluştu mu?)
- [ ] Versions sayfası açıldı
- [ ] v1'e restore edildi
- [ ] Bir versiyon silindi
- [ ] Cleanup çalıştırıldı

---
✨ **Versiyon yönetimi artık aktif! Artık projelerinizi güvenle güncelleyebilirsiniz.**
