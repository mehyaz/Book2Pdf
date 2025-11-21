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
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.bind("<Escape>", self.cancel)

    def on_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)

        if self.selection_type == 'rect':
            self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_drag(self, event):
        if self.selection_type == 'rect' and self.rect:
            cur_x = self.canvas.canvasx(event.x)
            cur_y = self.canvas.canvasy(event.y)
            self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_release(self, event):
        if self.selection_type == 'rect':
            end_x = self.canvas.canvasx(event.x)
            end_y = self.canvas.canvasy(event.y)
            
            # Koordinatları düzenle (sol-üst, sağ-alt)
            x1 = min(self.start_x, end_x)
            y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x)
            y2 = max(self.start_y, end_y)
            
            # Seçim çok küçükse iptal et
            if (x2 - x1) < 10 or (y2 - y1) < 10:
                self.cancel()
                return

            # Tkinter (mantıksal) koordinatlarını fiziksel koordinatlara çevir
            try:
                scale = self.winfo_tkscaling()
                # macOS'ta winfo_tkscaling genellikle 2.0 döner (Retina), ancak mss fiziksel piksel kullanır.
                # Tkinter koordinatları zaten mantıksal (points).
                # Eğer mss ile ekran görüntüsü alacaksak, ve mss fiziksel koordinat bekliyorsa:
                # Ancak SelectionWindow'da mss.grab ile aldığımız görüntü fiziksel boyutta.
                # Canvas'a koyarken ImageTk otomatik ölçeklemiş olabilir mi?
                # Basitlik adına: Tkinter koordinatlarını doğrudan kullanacağız, ancak
                # ana uygulamada bu koordinatları tekrar kontrol edeceğiz.
                
                # Düzeltme: SelectionWindow tam ekran açılıyor.
                # self.monitor_bbox fiziksel boyutlarda.
                # Canvas boyutu da fiziksel boyutlarda olmalı.
                
                self.result = {
                    "top": int(y1),
                    "left": int(x1),
                    "width": int(x2 - x1),
                    "height": int(y2 - y1)
                }
            except:
                 self.result = {
                    "top": int(y1),
                    "left": int(x1),
                    "width": int(x2 - x1),
                    "height": int(y2 - y1)
                }
            
        elif self.selection_type == 'point':
            self.result = (int(event.x_root), int(event.y_root))
        
        self.destroy()

    def cancel(self, event=None):
        self.result = None
        self.destroy()

class RoundedFrame(tk.Canvas):
    def __init__(self, master, color="#FFFFFF", radius=20, **kwargs):
        super().__init__(master, highlightthickness=0, **kwargs)
        self.color = color
        self.radius = radius
        self.bind("<Configure>", self.on_resize)

    def on_resize(self, event):
        self.delete("all")
        w = event.width
        h = event.height
        self.create_rounded_rect(0, 0, w, h, self.radius, fill=self.color, outline="")

    def create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = (x1+r, y1, x1+r, y1, x2-r, y1, x2-r, y1,
                  x2, y1, x2, y1+r, x2, y1+r, x2, y2-r, x2, y2-r,
                  x2, y2, x2-r, y2, x2-r, y2, x1+r, y2, x1+r, y2,
                  x1, y2, x1, y2-r, x1, y2-r, x1, y1+r, x1, y1+r,
                  x1, y1)
        return self.create_polygon(points, **kwargs, smooth=True)

class Book2PdfApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Book2Pdf (v1.0.2)")
        self.geometry("900x550") # Genişletilmiş modern tasarım
        self.configure(bg="#dcdad5") # Ana arka plan (Kullanıcının seçimi)

        self.mouse = Controller()
        self.sayfa_alani = None
        self.sonraki_buton = None
        self.full_pdf_path = None
        self.stop_event = threading.Event()

        # Stil Ayarları
        self.style = ttk.Style()
        self.style.theme_use('clam') # Özelleştirme için en uygun tema
        
        # Renkler
        self.bg_color = "#dcdad5"
        self.card_color = "#F2F2F7"
        
        # Başlık Stili (Kart rengiyle uyumlu)
        self.style.configure("Header.TLabel", background=self.card_color, foreground="#1D1D1F", font=("Segoe UI", 14, "bold"))
        self.style.configure("SubHeader.TLabel", background=self.card_color, foreground="#86868B", font=("Segoe UI", 10))
        self.style.configure("Normal.TLabel", background=self.card_color, foreground="#1D1D1F", font=("Segoe UI", 10))
        
        # Checkbutton Stili
        self.style.configure("TCheckbutton", background=self.card_color, foreground="#1D1D1F", font=("Segoe UI", 10))
        self.style.map("TCheckbutton", background=[('active', self.card_color)])

        # Buton Stili (Apple Mavisi)
        self.style.configure("Blue.TButton", 
                             background="#007AFF", 
                             foreground="white", 
                             font=("Segoe UI", 10, "bold"),
                             borderwidth=0,
                             focuscolor="none")
        self.style.map("Blue.TButton", 
                       background=[('active', '#0062C4'), ('pressed', '#004993')])

        # Büyük Buton Stili
        self.style.configure("Large.TButton", 
                             background="#007AFF", 
                             foreground="white", 
                             font=("Segoe UI", 14, "bold"),
                             padding=10,
                             borderwidth=0)
        self.style.map("Large.TButton", 
                       background=[('active', '#0062C4'), ('pressed', '#004993')])

        self.create_widgets()

    def create_widgets(self):
        # Ana Konteyner (Arka plan rengini ana pencereden almalı)
        main_container = tk.Frame(self, bg=self.bg_color)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # 3 Sütunlu Grid Yapısı
        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.columnconfigure(2, weight=1)
        main_container.rowconfigure(0, weight=1)

        # --- Sütun 1: Alanları Seç ---
        col1 = RoundedFrame(main_container, bg=self.bg_color, color=self.card_color)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        # İçerik için bir frame (Padding için)
        col1_inner = tk.Frame(col1, bg=self.card_color)
        col1_inner.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(col1_inner, text="1. Alanları Seç", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(col1_inner, text="Book to PDF dönüştürme işlemi için gerekli alanları belirleyin.", style="SubHeader.TLabel", wraplength=200).pack(anchor="w", pady=(0, 20))
        
        self.btn_alan_sec = ttk.Button(col1_inner, text="⛶ Sayfa Alanı Seç", style="Blue.TButton", command=self.sec_sayfa_alani)
        self.btn_alan_sec.pack(fill="x", pady=5, ipady=5)
        
        self.lbl_alan_durum = ttk.Label(col1_inner, text="Seçilmedi", style="SubHeader.TLabel", foreground="red")
        self.lbl_alan_durum.pack(anchor="w", pady=(0, 15))

        self.btn_buton_sec = ttk.Button(col1_inner, text="🖱 Sonraki Butonu Seç", style="Blue.TButton", command=self.sec_sonraki_buton)
        self.btn_buton_sec.pack(fill="x", pady=5, ipady=5)
        
        self.lbl_buton_durum = ttk.Label(col1_inner, text="Seçilmedi", style="SubHeader.TLabel", foreground="red")
        self.lbl_buton_durum.pack(anchor="w")

        # --- Sütun 2: Ayarlar ---
        col2 = RoundedFrame(main_container, bg=self.bg_color, color=self.card_color)
        col2.grid(row=0, column=1, sticky="nsew", padx=10)
        
        col2_inner = tk.Frame(col2, bg=self.card_color)
        col2_inner.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(col2_inner, text="2. Ayarlar", style="Header.TLabel").pack(anchor="w", pady=(0, 20))
        
        # Toplam Sayfa
        ttk.Label(col2_inner, text="Toplam Sayfa:", style="Normal.TLabel").pack(anchor="w")
        self.toplam_sayfa_var = tk.StringVar(value="300")
        self.entry_sayfa = ttk.Entry(col2_inner, textvariable=self.toplam_sayfa_var)
        self.entry_sayfa.pack(fill="x", pady=(5, 15))

        # Bekleme Süresi
        ttk.Label(col2_inner, text="Bekleme Süresi (sn):", style="Normal.TLabel").pack(anchor="w")
        self.bekleme_suresi_var = tk.StringVar(value="1.5")
        self.entry_sure = ttk.Entry(col2_inner, textvariable=self.bekleme_suresi_var)
        self.entry_sure.pack(fill="x", pady=(5, 15))

        # Dosya Adı
        ttk.Label(col2_inner, text="PDF Dosya Adı:", style="Normal.TLabel").pack(anchor="w")
        self.pdf_adi_var = tk.StringVar(value="Kitap.pdf")
        self.entry_isim = ttk.Entry(col2_inner, textvariable=self.pdf_adi_var)
        self.entry_isim.pack(fill="x", pady=(5, 15))

        # Kalite
        ttk.Label(col2_inner, text="PDF Kalitesi:", style="Normal.TLabel").pack(anchor="w")
        self.kalite_var = tk.StringVar(value="Normal (Önerilen)")
        self.combo_kalite = ttk.Combobox(col2_inner, textvariable=self.kalite_var, values=["Normal (Önerilen)", "Yüksek (Yavaş)", "Ultra (Yazılımsal 2x)"], state="readonly")
        self.combo_kalite.current(0) # Varsayılan Normal
        self.combo_kalite.pack(fill="x", pady=5)

        # --- Sütun 3: Görüntü İyileştirme ---
        col3 = RoundedFrame(main_container, bg=self.bg_color, color=self.card_color)
        col3.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        
        col3_inner = tk.Frame(col3, bg=self.card_color)
        col3_inner.pack(fill="both", expand=True, padx=20, pady=20)
        
        ttk.Label(col3_inner, text="3. Görüntü İyileştirme", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(col3_inner, text="Dönüştürülen PDF'in görüntü kalitesini artırın.", style="SubHeader.TLabel", wraplength=200).pack(anchor="w", pady=(0, 20))
        
        self.keskinlestirme_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(col3_inner, text="Keskinleştirme", variable=self.keskinlestirme_var, style="TCheckbutton").pack(anchor="w", pady=5)
        
        self.kontrast_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(col3_inner, text="Kontrast Artırma", variable=self.kontrast_var, style="TCheckbutton").pack(anchor="w", pady=5)
        
        self.siyah_beyaz_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(col3_inner, text="Siyah-Beyaz", variable=self.siyah_beyaz_var, style="TCheckbutton").pack(anchor="w", pady=5)



        # --- Alt Bölüm: Başlat Butonu ---
        bottom_frame = ttk.Frame(self, padding=20)
        bottom_frame.pack(fill="x")
        
        self.btn_baslat = ttk.Button(bottom_frame, text="▶ Otomasyonu Başlat", style="Large.TButton", command=self.baslat_otomasyon)
        self.btn_baslat.pack(fill="x", ipady=10)

        # --- Durum Çubuğu ---
        status_bar = ttk.Frame(self, relief="sunken", padding=(10, 5))
        status_bar.pack(fill="x", side="bottom")
        
        self.lbl_status = ttk.Label(status_bar, text="Durum: Hazır.", font=("Segoe UI", 9))
        self.lbl_status.pack(side="left")
        
        self.lbl_clock = ttk.Label(status_bar, text="", font=("Segoe UI", 9))
        self.lbl_clock.pack(side="right")
        self.update_clock()

    def update_clock(self):
        now = time.strftime("%H:%M:%S")
        self.lbl_clock.config(text=now)
        self.after(1000, self.update_clock)

    def update_status(self, message):
        self.lbl_status.config(text=f"Durum: {message}")
        self.update()
    
    def sec_sayfa_alani(self):
        self.withdraw()
        selector = SelectionWindow(self, 'rect')
        self.wait_window(selector)
        self.deiconify()
        
        if selector.result:
            self.sayfa_alani = selector.result
            x = self.sayfa_alani['left']
            y = self.sayfa_alani['top']
            w = self.sayfa_alani['width']
            h = self.sayfa_alani['height']
            
            self.lbl_alan_durum.config(text=f"Seçildi: (x:{x}, y:{y}, w:{w}, h:{h})", foreground="green")
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
            self.lbl_buton_durum.config(text=f"Seçildi: {self.sonraki_buton}", foreground="green")

            self.update_status("Sonraki sayfa butonu seçildi.")

    def update_status(self, mesaj):
        self.lbl_status.config(text=f"Durum: {mesaj}")
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
        win_w, win_h = 250, 250
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        countdown_win.geometry(f'{win_w}x{win_h}+{x}+{y}')
        countdown_win.overrideredirect(True) # Pencere çerçevesini kaldır
        
        # Modern Dark HUD Stili
        bg_color = "#2C2C2E" # Apple Dark Gray
        fg_color = "#FFFFFF"
        countdown_win.configure(bg=bg_color)
        
        # Yuvarlak köşe efekti veremiyoruz ama çerçeve ekleyebiliriz
        frame = tk.Frame(countdown_win, bg=bg_color, highlightbackground="#505050", highlightthickness=1)
        frame.pack(fill='both', expand=True)

        # Başlık
        tk.Label(frame, text="Başlıyor...", font=('Segoe UI', 16), bg=bg_color, fg="#B0B0B0").pack(pady=(40, 10))
        
        # Sayaç
        lbl_count = tk.Label(frame, text=str(count), font=('Segoe UI', 80, 'bold'), bg=bg_color, fg=fg_color)
        lbl_count.pack(expand=True)
        
        def update_label(c):
            if c > 0:
                lbl_count.config(text=str(c))
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

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = Book2PdfApp()
    app.mainloop()
