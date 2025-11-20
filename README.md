# Book2Pdf Automation 📚✨

![Version](https://img.shields.io/github/v/release/mehyaz/Book2Pdf?style=flat-square)
![License](https://img.shields.io/github/license/mehyaz/Book2Pdf?style=flat-square)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-blue?style=flat-square)

**Book2Pdf**, dijital kitapları (E-kitap, Z-kitap) otomatik olarak ekran görüntüsü alarak yüksek kaliteli PDF formatına dönüştüren açık kaynaklı bir otomasyon aracıdır.

![Book2Pdf Screenshot](assets/screenshot.png)

## 🌟 Özellikler

*   **Otomatik Sayfa Çevirme**: Siz sadece başlangıcı yapın, gerisini Book2Pdf halleder.
*   **Retina & Yüksek Çözünürlük (High DPI)**: macOS Retina ekranlarda ve yüksek çözünürlüklü monitörlerde **Flameshot kalitesinde**, bulanık olmayan, kristal netliğinde çıktılar.
*   **Görüntü İyileştirme**:
    *   **Keskinleştirme**: Metinleri daha okunaklı hale getirir.
    *   **Kontrast Artırma**: Arka planı beyazlatır, yazıları koyulaştırır.
    *   **Siyah-Beyaz Modu**: Gereksiz renkleri atarak dosya boyutunu düşürür ve okumayı kolaylaştırır.
*   **Ultra Kalite (Upscaling)**: Yazılımsal olarak görüntüyü 2 kat büyüterek (Lanczos filtresi ile) zoom yapıldığında bile bozulmayan PDF'ler oluşturur.
*   **Çapraz Platform**: Windows, macOS ve Linux üzerinde çalışır.

## 🚀 Kurulum

### Hazır Paketler (Önerilen)
En son sürümü **[Releases](https://github.com/mehyaz/Book2Pdf/releases)** sayfasından indirebilirsiniz.
*   **Windows**: `.exe` dosyasını indirin ve çalıştırın.
*   **macOS**: `.app` veya zip dosyasını indirin.
*   **Linux**: Binary dosyasını indirin.

### Kaynak Koddan Çalıştırma
Geliştirici iseniz veya kaynak koddan çalıştırmak isterseniz:

1.  Depoyu klonlayın:
    ```bash
    git clone https://github.com/mehyaz/Book2Pdf.git
    cd Book2Pdf
    ```

2.  Gerekli kütüphaneleri yükleyin:
    ```bash
    pip install -r requirements.txt
    ```

3.  Uygulamayı başlatın:
    ```bash
    python gui_app_final.py
    ```

## 📖 Kullanım

1.  **Alanları Seçin**:
    *   **Sayfa Alanı**: Kitabın sadece sayfa kısmını ekranda seçin.
    *   **Sonraki Butonu**: Sayfayı çeviren butona tıklayın.
2.  **Ayarları Yapın**:
    *   Kaç sayfa çekileceğini ve her sayfa arasında kaç saniye bekleneceğini girin.
    *   **Kalite**: En iyi sonuç için **"Yüksek (Yavaş)"** seçeneğini kullanın.
3.  **Görüntü İyileştirme (İsteğe Bağlı)**:
    *   Daha net metinler için **Keskinleştirme** ve **Kontrast** kutucuklarını işaretleyin.
4.  **Başlatın**:
    *   "Otomasyonu Başlat" butonuna basın ve arkanıza yaslanın. PDF masaüstünüze kaydedilecektir.

## 🤝 Katkıda Bulunma
Hataları bildirmek veya yeni özellikler eklemek için [Issues](https://github.com/mehyaz/Book2Pdf/issues) sayfasını kullanabilir veya Pull Request gönderebilirsiniz.

## 📄 Lisans
Bu proje MIT Lisansı ile lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.
