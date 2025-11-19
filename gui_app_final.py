import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import io
from PIL import Image, ImageTk
from mss import mss
import fitz  # PyMuPDF
from pynput.mouse import Button, Controller

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

        # Pencereyi tam ekran yap
        self.attributes('-fullscreen', True)
        self.grab_set() # Tüm olayları bu pencereye yönlendir

        # Tam ekran görüntüsü al
        with mss() as sct:
            sct_img = sct.grab(sct.monitors[0]) # Tüm ekranı yakala
            # PIL Image'e çevir
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
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        if not self.first_point:
            self.first_point = (x, y)
            self.canvas.create_oval(x-5, y-5, x+5, y+5, fill="blue", outline="white", tags="selection_marker")
            self.master.update_status(f"İlk köşe seçildi: ({int(x)}, {int(y)}). İkinci köşeyi seçin.")
        else:
            x1, y1 = self.first_point
            x2, y2 = x, y
            self.canvas.delete("selection_marker") # İlk işaretleyiciyi sil
            self.canvas.create_rectangle(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2), outline='red', width=2, tags="selection_rect")
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
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Tıklanan noktayı işaretle
        self.canvas.create_oval(x-5, y-5, x+5, y+5, fill="red", outline="white")
        
        self.result = (x, y)
        self.after(200, self.destroy)

class Book2PdfApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Book2Pdf Otomasyonu (v4.5 - Kayıt Yolu Düzeltmesi)")
        self.geometry("450x440")

        self.mouse = Controller()
        
        # Mantıksal (tkinter) ve Fiziksel (mss, pynput) koordinatlar için değişkenler
        self.sayfa_alani_logical = None
        self.sayfa_alani_physical = None
        self.sonraki_buton_logical = None
        self.sonraki_buton_physical = None

        # HiDPI/Retina ekranlar için ölçek faktörünü al
        with mss() as sct:
            # sct.monitors[0] tüm ekranların birleşimidir, [1] ise ana ekrandır.
            try:
                self.scale_factor = sct.monitors[1].get("scale", 1.0)
            except IndexError:
                self.scale_factor = 1.0 # Tek monitör durumu

            # tkinter'in kendi ölçek faktörünü de kontrol edelim
            try:
                tk_scale = self.winfo_tkscaling()
                if tk_scale > self.scale_factor:
                    self.scale_factor = tk_scale
            except AttributeError:
                pass # Eski tkinter versiyonları için

        # GUI elemanları...
        style = ttk.Style(self)
        style.configure('TLabel', font=('Helvetica', 10))
        style.configure('TButton', font=('Helvetica', 10, 'bold'))
        style.configure('Header.TLabel', font=('Helvetica', 12, 'bold'))
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill="both", expand=True)
        ttk.Label(main_frame, text="1. Alanları Seç", style="Header.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        self.sayfa_alani_label = ttk.Label(main_frame, text="Sayfa Alanı: (Seçilmedi)")
        self.sayfa_alani_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(main_frame, text="Sayfa Alanı Seç", command=self.sec_sayfa_alani).grid(row=2, column=0, sticky="ew", padx=(0, 5))
        self.sonraki_buton_label = ttk.Label(main_frame, text="Sonraki Buton: (Seçilmedi)")
        self.sonraki_buton_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Button(main_frame, text="Sonraki Butonu Seç", command=self.sec_sonraki_buton).grid(row=4, column=0, sticky="ew", padx=(0, 5))
        ttk.Label(main_frame, text=f"Ekran Ölçeği: {self.scale_factor}x", style='TLabel').grid(row=2, column=1, rowspan=2, sticky="w", padx=10)
        
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
        kalite_combo = ttk.Combobox(main_frame, textvariable=self.kalite_var, values=["Düşük (Hızlı)", "Normal (Önerilen)", "Yüksek (Yavaş)"], state="readonly", width=18)
        kalite_combo.grid(row=9, column=1, sticky="w")

        ttk.Button(main_frame, text="Otomasyonu Başlat", command=self.baslat_otomasyon, style="TButton").grid(row=10, column=0, columnspan=2, sticky="ew", pady=(20, 5))
        self.status_label = ttk.Label(main_frame, text="Durum: Hazır.")
        self.status_label.grid(row=11, column=0, columnspan=2, sticky="w", pady=(10, 0))

    def sec_sayfa_alani(self):
        self.withdraw()
        selector = SelectionWindow(self, 'rect')
        self.wait_window(selector)
        self.deiconify()
        
        if selector.result:
            x1, y1, x2, y2 = [int(p) for p in selector.result]
            
            # Mantıksal koordinatlar
            l_x1, l_y1, l_x2, l_y2 = min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)
            self.sayfa_alani_logical = {'top': l_y1, 'left': l_x1, 'width': l_x2 - l_x1, 'height': l_y2 - l_y1}
            self.sayfa_alani_label.config(text=f"Sayfa Alanı: (x:{l_x1}, y:{l_y1}, w:{l_x2 - l_x1}, h:{l_y2 - l_y1})")
            
            # Fiziksel piksel koordinatlarına çevir
            p_x1 = int(l_x1 * self.scale_factor)
            p_y1 = int(l_y1 * self.scale_factor)
            p_w = int((l_x2 - l_x1) * self.scale_factor)
            p_h = int((l_y2 - l_y1) * self.scale_factor)
            self.sayfa_alani_physical = {'top': p_y1, 'left': p_x1, 'width': p_w, 'height': p_h}

            self.update_status("Sayfa alanı başarıyla seçildi.")
    
    def sec_sonraki_buton(self):
        self.withdraw()
        selector = SelectionWindow(self, 'point')
        self.wait_window(selector)
        self.deiconify()
        
        if selector.result:
            # Mantıksal koordinatlar
            l_x, l_y = int(selector.result[0]), int(selector.result[1])
            self.sonraki_buton_logical = (l_x, l_y)
            self.sonraki_buton_label.config(text=f"Sonraki Buton: {self.sonraki_buton_logical}")

            # Fiziksel piksel koordinatlarına çevir
            p_x = int(l_x * self.scale_factor)
            p_y = int(l_y * self.scale_factor)
            self.sonraki_buton_physical = (p_x, p_y)

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
        if not self.sayfa_alani_physical or not self.sonraki_buton_physical:
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
        sayfa_alani = self.sayfa_alani_physical
        sonraki_buton = self.sonraki_buton_physical
        toplam_sayfa = self.toplam_sayfa
        bekleme_suresi = self.bekleme_suresi
        full_pdf_path = self.full_pdf_path
        kalite = self.kalite

        image_data_list = []
        try:
            with mss() as sct:
                for i in range(1, toplam_sayfa + 1):
                    # Durum etiketini ana UI thread'inde güncelle
                    self.after(0, self.update_status, f"Sayfa {i}/{toplam_sayfa} yakalanıyor...")
                    
                    sct_img = sct.grab(sayfa_alani)
                    
                    image_data_list.append({
                        "pixels": sct_img.bgra,
                        "width": sct_img.width,
                        "height": sct_img.height,
                    })
                    
                    self.mouse.position = sonraki_buton
                    self.mouse.click(Button.left)
                    time.sleep(bekleme_suresi)
            
            self.after(0, self.create_pdf_with_pymupdf, image_data_list, full_pdf_path, kalite)
        except Exception as e:
            self.after(0, messagebox.showerror, "Otomasyon Hatası", f"Bir hata oluştu: {e}")
        finally:
            self.after(0, self.deiconify)
            self.after(0, self.update_status, "İşlem tamamlandı veya durduruldu.")

    def create_pdf_with_pymupdf(self, image_data_list, pdf_path, kalite):
        if not image_data_list:
            messagebox.showwarning("PDF Hatası", "Hiç görüntü yakalanamadı.")
            return

        try:
            doc = fitz.open()  # Boş bir PDF dokümanı oluştur
            
            for image_data in image_data_list:
                width = image_data["width"]
                height = image_data["height"]
                pixels = image_data["pixels"]
                
                page = doc.new_page(width=width, height=height)
                
                if kalite == "Yüksek (Yavaş)":
                    # Yöntem 1: Kayıpsız - Doğrudan piksel verisi (BGRA -> RGB dönüşümü ile)
                    pil_img = Image.frombytes("RGBA", (width, height), pixels, "raw", "BGRA")
                    rgb_pixels = pil_img.convert("RGB").tobytes()
                    pix = fitz.Pixmap(fitz.csRGB, width, height, rgb_pixels, False)
                    page.insert_image(fitz.Rect(0, 0, width, height), pixmap=pix)
                else:
                    # Yöntem 2: Kayıplı - JPEG sıkıştırması
                    quality_setting = 75 if kalite == "Normal (Önerilen)" else 50
                    
                    pil_img = Image.frombytes("RGBA", (width, height), pixels, "raw", "BGRA").convert("RGB")
                    
                    # Görüntüyü hafızada bir JPEG'e dönüştür
                    img_buffer = io.BytesIO()
                    pil_img.save(img_buffer, format="jpeg", quality=quality_setting)
                    img_buffer.seek(0)
                    
                    # Sıkıştırılmış görüntüyü sayfaya ekle
                    page.insert_image(fitz.Rect(0, 0, width, height), stream=img_buffer)

            # PDF'i kaydet
            doc.save(pdf_path, garbage=4, deflate=True)
            doc.close()
            
            messagebox.showinfo("Başarılı", f"PDF dosyası Masaüstü'ne kaydedildi!\n\nYol: {pdf_path}")
        except Exception as e:
            messagebox.showerror("PDF Oluşturma Hatası", f"PyMuPDF ile PDF oluşturulurken bir hata oluştu: {e}")

if __name__ == "__main__":
    app = Book2PdfApp()
    app.mainloop()

