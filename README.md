# Book2Pdf Otomasyonu

Bu proje, dijital kitapları veya web tabanlı dökümanları otomatik olarak ekran görüntüsü alarak bir PDF dosyasına dönüştüren görsel arayüzlü (GUI) bir uygulamadır.

![Uygulama Arayüzü](https://i.imgur.com/your-image-url.png) <!-- TODO: Add a real screenshot URL -->

## Özellikler

- **Görsel Arayüz:** Tüm ayarları ve işlemleri basit bir arayüz üzerinden yönetin.
- **Akıllı Alan Seçimi:** Kitabın sayfa alanını ve "sonraki sayfa" butonunu ekrandan tıklayarak kolayca seçin.
- **HiDPI/Retina Desteği:** Yüksek çözünürlüklü ekranlarda doğru koordinat tespiti için otomatik ölçeklendirme yapar.
- **Kalite Ayarı:** Oluşturulacak PDF'nin kalitesini (Yüksek, Normal, Düşük) seçerek dosya boyutu ve görüntü netliği arasında denge kurun.
- **Geri Sayım:** Otomasyon başlamadan önce 3 saniyelik bir geri sayım ile size hazırlık süresi tanır.
- **Paketlenmiş Uygulama:** Proje, macOS için tek tıklamayla çalıştırılabilir bir `.app` paketi haline getirilmiştir.

## Kurulum ve Çalıştırma

### 1. Yöntem: Paketlenmiş Uygulamayı Kullanma (macOS)

1.  `dist` klasörüne gidin.
2.  `Book2Pdf.app` uygulamasına çift tıklayarak çalıştırın.

### 2. Yöntem: Kaynak Kodundan Çalıştırma

Eğer uygulamayı kaynak kodundan çalıştırmak veya geliştirmek isterseniz:

**Adım 1: Depoyu Klonlama**
```bash
git clone https://github.com/mehyaz/Book2Pdf.git
cd Book2Pdf
```

**Adım 2: Sanal Ortam Oluşturma ve Aktive Etme**
```bash
# Sanal ortamı oluştur
python3 -m venv book2pdf-env

# Sanal ortamı aktive et (macOS/Linux)
source book2pdf-env/bin/activate
```

**Adım 3: Gerekli Kütüphaneleri Yükleme**
```bash
pip install -r requirements.txt
```

**Adım 4: Uygulamayı Başlatma**
```bash
python3 gui_app_final.py
```

## Kullanım Kılavuzu

1.  **Sayfa Alanı Seç:**
    - `Sayfa Alanı Seç` düğmesine tıklayın. Ekran karardığında kitabınızın sayfasının **sol üst** ve ardından **sağ alt** köşesine tıklayın.
2.  **Sonraki Butonu Seç:**
    - `Sonraki Butonu Seç` düğmesine tıklayın ve kitabınızdaki "sonraki sayfa" düğmesinin üzerine tıklayın.
3.  **Ayarları Girme:**
    - "Toplam Sayfa", "Bekleme Süresi", "PDF Dosya Adı" ve "PDF Kalitesi" alanlarını doldurun.
4.  **Başlatma:**
    - `Otomasyonu Başlat` düğmesine tıklayın.
    - 3 saniyelik geri sayım sırasında dijital kitabınızın penceresini öne getirin.
    - İşlem bitene kadar fare ve klavyeye dokunmayın. PDF'iniz proje klasöründe oluşturulacaktır.

## Gelecekteki Geliştirme Fikirleri

- **Otomatik Koordinat Tespiti:** Görüntü işleme ile sayfa alanını ve "sonraki" butonunu otomatik bulma.
- **Duraklatma/Devam Etme:** Otomasyon sırasında işlemi duraklatıp devam ettirme özelliği.
- **Farklı Çıktı Formatları:** `.zip` veya `.cbz` (Çizgi Roman Arşivi) olarak kaydetme seçeneği.
- **Windows Paketi:** Proje için bir Windows `.exe` paketi oluşturma.

