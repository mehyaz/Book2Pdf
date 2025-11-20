import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import io
from PIL import Image, ImageTk, ImageEnhance, ImageOps
from mss import mss
import fitz  # PyMuPDF
from pynput.mouse import Button, Controller
import sys
import subprocess

class SelectionWindow(tk.Toplevel):
    """Kullanıcının ekranda bir alanı veya noktayı seçmesi için bir pencere oluşturur."""
    def __init__(self, master, selection_type='rect'):
        super().__init__(master)
        self.master = master
        self.selection_type = selection_type
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.result = None

        self.overrideredirect(True) # Pencere kenarlıklarını kaldır
        self.wait_visibility(self) # Pencerenin görünür olmasını bekle
        self.grab_set() # Tüm olayları bu pencereye yönlendir

        # Tüm monitörleri kapsayan sanal ekranın boyutlarını al
        with mss() as sct:
            self.monitor_bbox = sct.monitors[0]
            # Pencereyi tüm sanal ekranı kaplayacak şekilde ayarla
            self.geometry(f"{self.monitor_bbox['width']}x{self.monitor_bbox['height']}+{self.monitor_bbox['left']}+{self.monitor_bbox['top']}")

            # Tam ekran görüntüsü al
            sct_img = sct.grab(self.monitor_bbox)
            
            # PIL Image'e çevir (Mantıksal boyutlar için, tkinter'in ölçeklemesiyle eşleşmesi amacıyla)
            # Fiziksel piksel boyutu yerine mantıksal boyuta ölçekleyebiliriz, ancak şimdilik doğrudan kullanalım.
            self.bg_image_pil = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            self.bg_image = ImageTk.PhotoImage(self.bg_image_pil)

        self.canvas = tk.Canvas(self, cursor="cross", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, image=self.bg_image, anchor="nw")

        self.bind_events()
        
    def bind_events(self):
        if self.selection_type == 'rect':
            self.first_point = None
            self.canvas.bind("<ButtonRelease-1>", self.on_rect_select_click)
        elif self.selection_type == 'point':
            self.canvas.bind("<ButtonRelease-1>", self.on_point_select)

    def on_rect_select_click(self, event):
        # Olaydan gelen mantıksal koordinatları al
        logical_x, logical_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        
        # Fiziksel koordinatlara çevir
        try:
            # En güvenilir ölçek faktörünü al
            scale = self.winfo_tkscaling()
        except Exception:
            scale = 1.0

        physical_x = logical_x * scale
        physical_y = logical_y * scale

        if not self.first_point:
            self.first_point = (physical_x, physical_y)
            # İşaretleyiciyi mantıksal koordinatlarla çiz
            self.canvas.create_oval(logical_x-5, logical_y-5, logical_x+5, logical_y+5, fill="blue", outline="white", tags="selection_marker")
            self.master.update_status(f"İlk köşe seçildi: ({int(physical_x)}, {int(physical_y)}). İkinci köşeyi seçin.")
        else:
            x1, y1 = self.first_point
            x2, y2 = physical_x, physical_y
            self.canvas.delete("selection_marker")
            
            # Dikdörtgeni mantıksal koordinatlarla çiz
            l_x1, l_y1 = self.first_point[0] / scale, self.first_point[1] / scale
            l_x2, l_y2 = physical_x / scale, physical_y / scale
            self.canvas.create_rectangle(min(l_x1, l_x2), min(l_y1, l_y2), max(l_x1, l_x2), max(l_y1, l_y2), outline='red', width=2, tags="selection_rect")
            
            # Sonucu fiziksel koordinatlar olarak ayarla
            self.result = (x1, y1, x2, y2)
            self.destroy()

    # on_button_press, on_mouse_drag, on_button_release methods are no longer needed for 'rect' selection
    # but kept for 'point' selection, which remains the same.
    def on_button_press(self, event):
        pass # Not used for two-click rect selection

    def on_mouse_drag(self, event):
        pass # Not used for two-click rect selection

    def on_button_release(self, event):
        pass # Not used for two-click rect selection, handled by on_rect_select_click


    def on_point_select(self, event):
        # Olaydan gelen mantıksal koordinatları al
        logical_x = self.canvas.canvasx(event.x)
        logical_y = self.canvas.canvasy(event.y)
        
        # Tıklanan noktayı mantıksal koordinatlarla işaretle
        self.canvas.create_oval(logical_x-5, logical_y-5, logical_x+5, logical_y+5, fill="red", outline="white")
        
        # Fiziksel koordinatlara çevir
        try:
            scale = self.winfo_tkscaling()
        except Exception:
            scale = 1.0

        physical_x = logical_x * scale
        physical_y = logical_y * scale
        
        self.result = (physical_x, physical_y)
        self.after(200, self.destroy)

class Book2PdfApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Book2Pdf Otomasyonu (v1.0)")
        self.geometry("450x550") # Yükseklik artırıldı

        self.mouse = Controller()
        
        # Seçimlerden gelen fiziksel koordinatlar için değişkenler
        self.sayfa_alani = None
        self.sonraki_buton = None

        # GUI elemanları...
        style = ttk.Style(self)
        style.configure('TLabel', font=('Helvetica', 10))
        style.configure('TButton', font=('Helvetica', 10, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill="both", expand=True)
        
        # 1. Alanları Seç
        ttk.Label(main_frame, text="1. Alanları Seç", style="Header.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.sayfa_alani_label = ttk.Label(main_frame, text="Sayfa Alanı: (Seçilmedi)")
        self.sayfa_alani_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(main_frame, text="Sayfa Alanı Seç", command=self.sec_sayfa_alani).grid(row=2, column=0, columnspan=2, sticky="ew", padx=(0, 5))
        self.sonraki_buton_label = ttk.Label(main_frame, text="Sonraki Buton: (Seçilmedi)")
        self.sonraki_buton_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(main_frame, text="Sonraki Butonu Seç", command=self.sec_sonraki_buton).grid(row=4, column=0, columnspan=2, sticky="ew", padx=(0, 5))
        
        # 2. Ayarlar
        ttk.Label(main_frame, text="2. Ayarlar", style="Header.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(20, 10))
        ttk.Label(main_frame, text="Toplam Sayfa:").grid(row=6, column=0, sticky="w")
        self.toplam_sayfa_var = tk.StringVar(value="10")
        ttk.Entry(main_frame, textvariable=self.toplam_sayfa_var, width=10).grid(row=6, column=1, sticky="w")
        ttk.Label(main_frame, text="Bekleme Süresi (sn):").grid(row=7, column=0, sticky="w")
        self.bekleme_suresi_var = tk.StringVar(value="2.5")
        ttk.Entry(main_frame, textvariable=self.bekleme_suresi_var, width=10).grid(row=7, column=1, sticky="w")
        ttk.Label(main_frame, text="PDF Dosya Adı:").grid(row=8, column=0, sticky="w")
        self.pdf_adi_var = tk.StringVar(value="dijital_kitap.pdf")
        ttk.Entry(main_frame, textvariable=self.pdf_adi_var, width=20).grid(row=8, column=1, sticky="w")
        
        ttk.Label(main_frame, text="PDF Kalitesi:").grid(row=9, column=0, sticky="w")
        self.kalite_var = tk.StringVar(value="Normal (Önerilen)")
        kalite_combo = ttk.Combobox(main_frame, textvariable=self.kalite_var, values=["Düşük (Hızlı)", "Normal (Önerilen)", "Yüksek (Yavaş)", "Ultra (Yazılımsal 2x)"], state="readonly", width=18)
        kalite_combo.grid(row=9, column=1, sticky="w")

        # 3. Görüntü İyileştirme
        ttk.Label(main_frame, text="3. Görüntü İyileştirme", style="Header.TLabel").grid(row=10, column=0, columnspan=2, sticky="w", pady=(20, 10))
        
        self.keskinlestirme_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Keskinleştirme (Netlik)", variable=self.keskinlestirme_var).grid(row=11, column=0, sticky="w")
        
        self.kontrast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Kontrast Artırma", variable=self.kontrast_var).grid(row=11, column=1, sticky="w")
        
        self.siyah_beyaz_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(main_frame, text="Siyah-Beyaz (Okunabilirlik)", variable=self.siyah_beyaz_var).grid(row=12, column=0, columnspan=2, sticky="w")

        ttk.Button(main_frame, text="Otomasyonu Başlat", command=self.baslat_otomasyon, style="TButton").grid(row=13, column=0, columnspan=2, sticky="ew", pady=(20, 5))
        self.status_label = ttk.Label(main_frame, text="Durum: Hazır.")
        self.status_label.grid(row=14, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def sec_sayfa_alani(self):
        self.withdraw()
        selector = SelectionWindow(self, 'rect')
        self.wait_window(selector)
        self.deiconify()
        
        if selector.result:
            x1, y1, x2, y2 = [int(p) for p in selector.result]
            
            # Gelen sonuç zaten fiziksel koordinat
            p_x1, p_y1 = min(x1, x2), min(y1, y2)
            p_x2, p_y2 = max(x1, x2), max(y1, y2)
            
            self.sayfa_alani = {'top': p_y1, 'left': p_x1, 'width': p_x2 - p_x1, 'height': p_y2 - p_y1}
            self.sayfa_alani_label.config(text=f"Sayfa Alanı: (x:{p_x1}, y:{p_y1}, w:{p_x2 - p_x1}, h:{p_y2 - p_y1})")
            
            self.update_status("Sayfa alanı başarıyla seçildi.")
    
    def sec_sonraki_buton(self):
        self.withdraw()
        selector = SelectionWindow(self, 'point')
        self.wait_window(selector)
        self.deiconify()
        
        if selector.result:
            # Gelen sonuç zaten fiziksel koordinat
            p_x, p_y = int(selector.result[0]), int(selector.result[1])
            self.sonraki_buton = (p_x, p_y)
            self.sonraki_buton_label.config(text=f"Sonraki Buton: {self.sonraki_buton}")

            self.update_status("Sonraki sayfa butonu seçildi.")

    def update_status(self, mesaj):
        self.status_label.config(text=f"Durum: {mesaj}")
        self.update()

    def baslat_otomasyon(self):
        try:
            self.toplam_sayfa = int(self.toplam_sayfa_var.get())
            self.bekleme_suresi = float(self.bekleme_suresi_var.get())
            pdf_adi = self.pdf_adi_var.get()
            self.kalite = self.kalite_var.get()
        except ValueError:
            messagebox.showerror("Hata", "Lütfen 'Toplam Sayfa' ve 'Bekleme Süresi' için geçerli sayılar girin.")
            return
        if not self.sayfa_alani or not self.sonraki_buton:
            messagebox.showerror("Hata", "Lütfen başlamadan önce her iki alanı da seçin.")
            return
        if not pdf_adi.lower().endswith(".pdf"):
            pdf_adi += ".pdf"

        # PDF'i kullanıcının masaüstüne kaydet
        desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
        self.full_pdf_path = os.path.join(desktop_path, pdf_adi)

        self.withdraw()
        self.start_countdown(3)

    def start_countdown(self, count):
        countdown_win = tk.Toplevel(self)
        # Pencereyi ortala
        win_w, win_h = 200, 100
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        countdown_win.geometry(f'{win_w}x{win_h}+{x}+{y}')
        countdown_win.overrideredirect(True) # Pencere çerçevesini kaldır
        
        countdown_label = ttk.Label(countdown_win, font=('Helvetica', 48, 'bold'), style='Header.TLabel')
        countdown_label.pack(expand=True)
        
        def update_label(c):
            if c > 0:
                countdown_label.config(text=str(c))
                self.after(1000, update_label, c - 1)
            else:
                countdown_win.destroy()
                threading.Thread(target=self.run_automation_logic, daemon=True).start()
        
        update_label(count)

    def run_automation_logic(self):
        # Parametreleri self'den al
        sayfa_alani = self.sayfa_alani
        sonraki_buton = self.sonraki_buton
        toplam_sayfa = self.toplam_sayfa
        bekleme_suresi = self.bekleme_suresi
        full_pdf_path = self.full_pdf_path
        kalite = self.kalite
        
        # İyileştirme ayarları
        enhancements = {
            'sharpness': self.keskinlestirme_var.get(),
            'contrast': self.kontrast_var.get(),
            'grayscale': self.siyah_beyaz_var.get()
        }

        # Ekran ölçekleme faktörünü al (Retina ekranlar için önemli)
        try:
            scale_factor = self.winfo_tkscaling()
        except:
            scale_factor = 1.0

        image_data_list = []
        try:
            with mss() as sct:
                for i in range(1, toplam_sayfa + 1):
                    # Durum etiketini ana UI thread'inde güncelle
                    self.after(0, self.update_status, f"Sayfa {i}/{toplam_sayfa} yakalanıyor...")
                    
                    if sys.platform == 'darwin' and (kalite == "Yüksek (Yavaş)" or kalite == "Ultra (Yazılımsal 2x)"):
                        # macOS ve Yüksek/Ultra Kalite: screencapture CLI kullan
                        # sayfa_alani fiziksel piksel cinsinden, screencapture point (mantıksal) bekler
                        # Bu yüzden scale_factor'e bölüyoruz.
                        l_x = sayfa_alani['left'] / scale_factor
                        l_y = sayfa_alani['top'] / scale_factor
                        l_w = sayfa_alani['width'] / scale_factor
                        l_h = sayfa_alani['height'] / scale_factor
                        
                        temp_filename = f"temp_capture_{i}.png"
                        # -x: ses çalma, -R: bölge (x,y,w,h)
                        cmd = ["screencapture", "-x", "-R", f"{l_x},{l_y},{l_w},{l_h}", temp_filename]
                        subprocess.run(cmd, check=True)
                        
                        # Dosyadan oku
                        img = Image.open(temp_filename)
                        # RGBA'ya çevir (garanti olsun)
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                            
                        # Veriyi hazırla (mss formatına benzetiyoruz)
                        # Not: screencapture zaten fiziksel çözünürlükte (Retina ise 2x) kaydeder.
                        # mss.bgra formatı yerine raw bytes kullanacağız, create_pdf fonksiyonunu buna göre güncellemeliyiz
                        # veya burada mss formatına (BGRA) çevirebiliriz.
                        # Kolaylık için BGRA'ya çevirelim:
                        bgra_data = img.tobytes("raw", "BGRA")
                        
                        image_data_list.append({
                            "pixels": bgra_data,
                            "width": img.width,
                            "height": img.height,
                        })
                        
                        # Temizlik
                        os.remove(temp_filename)
                        
                    else:
                        # Standart mss kullanımı (Windows/Linux veya Normal kalite)
                        sct_img = sct.grab(sayfa_alani)
                        image_data_list.append({
                            "pixels": sct_img.bgra,
                            "width": sct_img.width,
                            "height": sct_img.height,
                        })
                    
                    self.mouse.position = sonraki_buton
                    self.mouse.click(Button.left)
                    time.sleep(bekleme_suresi)
            
            self.after(0, self.create_pdf_with_pymupdf, image_data_list, full_pdf_path, kalite, enhancements, scale_factor)
        except Exception as e:
            self.after(0, messagebox.showerror, "Otomasyon Hatası", f"Bir hata oluştu: {e}")
        finally:
            self.after(0, self.deiconify)
            self.after(0, self.update_status, "İşlem tamamlandı veya durduruldu.")

    def create_pdf_with_pymupdf(self, image_data_list, pdf_path, kalite, enhancements, scale_factor=1.0):
        if not image_data_list:
            messagebox.showwarning("PDF Hatası", "Hiç görüntü yakalanamadı.")
            return

        try:
            doc = fitz.open()  # Boş bir PDF dokümanı oluştur
            
            for image_data in image_data_list:
                width = image_data["width"]
                height = image_data["height"]
                pixels = image_data["pixels"]
                
                # Görüntüyü işle
                pil_img = Image.frombytes("RGBA", (width, height), pixels, "raw", "BGRA")
                
                # 1. Siyah-Beyaz
                if enhancements['grayscale']:
                    pil_img = ImageOps.grayscale(pil_img).convert("RGB") # RGB'ye geri dön (PyMuPDF uyumu için)
                elif pil_img.mode == 'RGBA':
                    pil_img = pil_img.convert("RGB")
                
                # 2. Kontrast
                if enhancements['contrast']:
                    enhancer = ImageEnhance.Contrast(pil_img)
                    pil_img = enhancer.enhance(1.5) # %50 artır
                
                # 3. Keskinleştirme
                if enhancements['sharpness']:
                    enhancer = ImageEnhance.Sharpness(pil_img)
                    pil_img = enhancer.enhance(2.0) # 2 kat keskinleştir
                
                # 4. Ultra Kalite (Upscaling)
                if kalite == "Ultra (Yazılımsal 2x)":
                    new_width = int(width * 2)
                    new_height = int(height * 2)
                    pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    width, height = new_width, new_height

                # PDF Sayfa Boyutunu Ayarla (High DPI için)
                # Görüntü piksel boyutunu scale_factor'e bölerek mantıksal (point) boyutunu buluyoruz.
                # Böylece PDF görüntüleyicisi bu sayfayı ekrandaki fiziksel boyutunda gösterecek,
                # ancak içerik yüksek çözünürlüklü (Retina) olacak.
                page_width = width / scale_factor
                page_height = height / scale_factor

                # PyMuPDF'e ekle
                if kalite == "Yüksek (Yavaş)" or kalite == "Ultra (Yazılımsal 2x)":
                    # Kayıpsız
                    rgb_pixels = pil_img.tobytes()
                    pix = fitz.Pixmap(fitz.csRGB, width, height, rgb_pixels, False)
                    page = doc.new_page(width=page_width, height=page_height)
                    page.insert_image(fitz.Rect(0, 0, page_width, page_height), pixmap=pix)
                else:
                    # Kayıplı (JPEG)
                    quality_setting = 75 if kalite == "Normal (Önerilen)" else 50
                    img_buffer = io.BytesIO()
                    pil_img.save(img_buffer, format="jpeg", quality=quality_setting)
                    img_buffer.seek(0)
                    
                    page = doc.new_page(width=page_width, height=page_height)
                    page.insert_image(fitz.Rect(0, 0, page_width, page_height), stream=img_buffer)

            # PDF'i kaydet
            doc.save(pdf_path, garbage=4, deflate=True)
            doc.close()
            
            messagebox.showinfo("Başarılı", f"PDF dosyası Masaüstü'ne kaydedildi!\n\nYol: {pdf_path}")
        except Exception as e:
            messagebox.showerror("PDF Oluşturma Hatası", f"PyMuPDF ile PDF oluşturulurken bir hata oluştu: {e}")

if __name__ == "__main__":
    app = Book2PdfApp()
    app.mainloop()
