# Versiyon Yönetimi (Version Management)

VDS Panel artık otomatik proje versiyon yönetimi ve yedekleme özelliğine sahiptir.

## Özellikler

### 🔄 Otomatik Yedekleme
- Mevcut bir projeyi güncellerken, eski versiyon otomatik olarak yedeklenir
- Her güncelleme için benzersiz bir versiyon numarası atanır
- Yedekler zaman damgalı ve açıklamalıdır

### 📦 Versiyon Yönetimi
- Her projenin tüm versiyonlarını görüntüleyin
- Versiyon detayları: numara, tarih, boyut, açıklama
- Dilediğiniz versiyona kolayca geri dönün
- İstediğiniz versiyonu silin

### 🧹 Otomatik Temizleme
- Eski versiyonları otomatik temizleme
- En son N adet versiyonu tutma (varsayılan: 5)
- Disk alanı yönetimi

## Kurulum

### 1. Veritabanı Migration
Yeni ProjectVersion tablosunu oluşturmak için migration script'ini çalıştırın:

```bash
python migrate_versions.py
```

### 2. Backups Klasörü
Sistem otomatik olarak `backups/` klasörünü oluşturur. Bu klasör:
- `uploads/` klasörü ile aynı seviyededir
- Her proje için ayrı alt klasör içerir
- Versiyonlar `v1_20231121_143022` formatında saklanır

## Kullanım

### Proje Güncelleme
1. "Upload Project" sayfasına gidin
2. Mevcut bir projenin adını kullanın
3. Yeni dosyaları yükleyin
4. Sistem otomatik olarak:
   - Çalışan projeyi durdurur
   - Mevcut versiyonu yedekler
   - Yeni versiyonu yükler

### Versiyonları Görüntüleme
1. Proje detay sayfasına gidin
2. "Versions" butonuna tıklayın
3. Tüm versiyonları listede görün:
   - Versiyon numarası
   - Oluşturulma tarihi
   - Boyut (MB)
   - Açıklama

### Versiyon Geri Yükleme
1. Versions sayfasında istediğiniz versiyonu bulun
2. "Restore" butonuna tıklayın
3. Onay verin
4. Sistem:
   - Güvenlik için mevcut durumu yedekler
   - Seçili versiyonu geri yükler
   - Projeyi durdurur (gerekirse)

### Versiyon Silme
1. Versions sayfasında silmek istediğiniz versiyonu bulun
2. "Delete" butonuna tıklayın
3. Onay verin

### Eski Versiyonları Temizleme
1. Versions sayfasının üst kısmında "Cleanup" bölümü
2. Kaç versiyon tutmak istediğinizi seçin (3, 5, veya 10)
3. "Clean Up" butonuna tıklayın
4. En eski versiyonlar silinir

## Teknik Detaylar

### Dosya Yapısı
```
vdspanel/
├── backups/                 # Tüm yedekler burada
│   ├── project1/
│   │   ├── v1_20231121_120000/
│   │   ├── v2_20231121_130000/
│   │   └── v3_20231121_140000/
│   └── project2/
│       └── v1_20231121_150000/
└── uploads/                 # Aktif projeler
    ├── project1/
    └── project2/
```

### Veritabanı Modeli
```python
class ProjectVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    version_number = db.Column(db.Integer)
    backup_path = db.Column(db.String(512))
    created_at = db.Column(db.DateTime)
    description = db.Column(db.Text)
```

### API Endpoints
- `GET /projects/<id>/versions` - Versiyonları listele
- `POST /projects/<id>/versions/<version_id>/restore` - Versiyonu geri yükle
- `POST /projects/<id>/versions/<version_id>/delete` - Versiyonu sil
- `POST /projects/<id>/versions/cleanup` - Eski versiyonları temizle

### Yedekleme Davranışı
Yedekleme sırasında şunlar **dahil edilmez**:
- `__pycache__/`
- `*.pyc`, `*.pyo` dosyaları
- `.git/` klasörü
- `venv/`, `env/` klasörleri
- `node_modules/`
- `*.log` dosyaları
- `.DS_Store`

### Güvenlik Özellikleri
1. **Geri yükleme öncesi güvenlik yedeği**: Bir versiyonu geri yüklerken, mevcut durum otomatik olarak yedeklenir
2. **Hata durumu koruması**: Yedekleme veya geri yükleme başarısız olursa, değişiklikler geri alınır
3. **Otomatik proje durdurma**: Güncelleme veya geri yükleme öncesi çalışan projeler güvenli şekilde durdurulur

## Örnek Senaryo

### Proje Güncelleme ve Geri Yükleme
```
1. İlk yükleme:
   - "myapp" projesini yükleyin
   - Versiyon yok (henüz güncelleme olmadı)

2. İlk güncelleme:
   - "myapp" adıyla yeni dosyalar yükleyin
   - Sistem otomatik v1 oluşturur
   - Yeni dosyalar aktif olur

3. İkinci güncelleme:
   - "myapp" adıyla yeni dosyalar yükleyin
   - Sistem otomatik v2 oluşturur
   - v1 ve v2 backups'ta saklanır

4. Geri yükleme:
   - v1'e geri dönmek isterseniz
   - "Restore" butonuna tıklayın
   - Mevcut durum v3 olarak yedeklenir
   - v1 aktif olur
```

## Sorun Giderme

### Yedekleme Başarısız
- Disk alanını kontrol edin
- `backups/` klasörü yazma izinlerini kontrol edin
- Log dosyalarını inceleyin

### Geri Yükleme Başarısız
- Yedek dosyalarının varlığını kontrol edin
- Proje path'inin doğru olduğundan emin olun
- Güvenlik yedeğinin oluşturulduğunu kontrol edin

### Versiyon Silme Başarısız
- Dosya izinlerini kontrol edin
- Yedek klasörünün silinebilir olduğundan emin olun

## Sık Sorulan Sorular

**S: Versiyon limiti var mı?**
C: Hayır, ancak düzenli olarak eski versiyonları temizlemeniz önerilir.

**S: Yedekler ne kadar yer kaplar?**
C: Her yedek, projenizin o anki boyutu kadar yer kaplar. Versions sayfasında her versiyonun boyutunu görebilirsiniz.

**S: Otomatik yedekleme devre dışı bırakılabilir mi?**
C: Hayır, güvenlik için tüm güncellemelerde otomatik yedekleme yapılır.

**S: Silinen bir versiyon geri getirilebilir mi?**
C: Hayır, silinen versiyonlar kalıcı olarak kaldırılır. Dikkatli olun!

## Yardım ve Destek

Sorun yaşarsanız:
1. `drawly.err.log` dosyasını kontrol edin
2. Migration script'ini yeniden çalıştırın
3. Veritabanı bağlantısını kontrol edin
