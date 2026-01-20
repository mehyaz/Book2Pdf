import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import os
import io
import sys
import subprocess
import multiprocessing
from PIL import Image, ImageTk, ImageEnhance, ImageOps
from mss import mss
import fitz  # PyMuPDF
from pynput.mouse import Button, Controller
from pynput import keyboard


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

        self.overrideredirect(True)
        self.wait_visibility(self)
        self.grab_set()

        with mss() as sct:
            self.monitor_bbox = sct.monitors[0]
            self.geometry(f"{self.monitor_bbox['width']}x{self.monitor_bbox['height']}+{self.monitor_bbox['left']}+{self.monitor_bbox['top']}")
            sct_img = sct.grab(self.monitor_bbox)
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
            x1 = min(self.start_x, end_x)
            y1 = min(self.start_y, end_y)
            x2 = max(self.start_x, end_x)
            y2 = max(self.start_y, end_y)
            
            if (x2 - x1) < 10 or (y2 - y1) < 10:
                self.cancel()
                return

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
        self.title("Book2Pdf (v1.1.0)")
        self.geometry("900x550")
        self.configure(bg="#dcdad5")

        self.mouse = Controller()
        self.sayfa_alani = None
        self.sonraki_buton = None
        self.full_pdf_path = None
        
        # Oturum Yönetimi (Pause/Continue)
        self.image_data_list = []  # Biriken görüntüler
        self.is_running = False    # Otomasyon çalışıyor mu?
        self.stop_event = threading.Event()  # Duraklatma sinyali
        self.scale_factor = 1.0
        self.enhancements = {}
        self.kalite = ""
        
        # Global Hotkey Listener (Escape tuşu ile duraklatma)
        self.hotkey_listener = keyboard.Listener(on_press=self._on_global_key)
        self.hotkey_listener.daemon = True
        self.hotkey_listener.start()

        # Stil Ayarları
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.bg_color = "#dcdad5"
        self.card_color = "#F2F2F7"
        
        self.style.configure("Header.TLabel", background=self.card_color, foreground="#1D1D1F", font=("Segoe UI", 14, "bold"))
        self.style.configure("SubHeader.TLabel", background=self.card_color, foreground="#86868B", font=("Segoe UI", 10))
        self.style.configure("Normal.TLabel", background=self.card_color, foreground="#1D1D1F", font=("Segoe UI", 10))
        
        self.style.configure("TCheckbutton", background=self.card_color, foreground="#1D1D1F", font=("Segoe UI", 10))
        self.style.map("TCheckbutton", background=[('active', self.card_color)])

        self.style.configure("Blue.TButton", background="#007AFF", foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0, focuscolor="none")
        self.style.map("Blue.TButton", background=[('active', '#0062C4'), ('pressed', '#004993')])

        self.style.configure("Green.TButton", background="#34C759", foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0, focuscolor="none")
        self.style.map("Green.TButton", background=[('active', '#2AA84A'), ('pressed', '#1F8C3A')])

        self.style.configure("Orange.TButton", background="#FF9500", foreground="white", font=("Segoe UI", 10, "bold"), borderwidth=0, focuscolor="none")
        self.style.map("Orange.TButton", background=[('active', '#E68600'), ('pressed', '#CC7700')])

        self.style.configure("Large.TButton", background="#007AFF", foreground="white", font=("Segoe UI", 14, "bold"), padding=10, borderwidth=0)
        self.style.map("Large.TButton", background=[('active', '#0062C4'), ('pressed', '#004993')])

        self.create_widgets()

    def create_widgets(self):
        main_container = tk.Frame(self, bg=self.bg_color)
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.columnconfigure(2, weight=1)
        main_container.rowconfigure(0, weight=1)

        # --- Sütun 1: Alanları Seç ---
        col1 = RoundedFrame(main_container, bg=self.bg_color, color=self.card_color)
        col1.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
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
        
        ttk.Label(col2_inner, text="Sayfa Sayısı (Bu Oturum):", style="Normal.TLabel").pack(anchor="w")
        self.toplam_sayfa_var = tk.StringVar(value="50")
        self.entry_sayfa = ttk.Entry(col2_inner, textvariable=self.toplam_sayfa_var)
        self.entry_sayfa.pack(fill="x", pady=(5, 15))

        ttk.Label(col2_inner, text="Bekleme Süresi (sn):", style="Normal.TLabel").pack(anchor="w")
        self.bekleme_suresi_var = tk.StringVar(value="1.5")
        self.entry_sure = ttk.Entry(col2_inner, textvariable=self.bekleme_suresi_var)
        self.entry_sure.pack(fill="x", pady=(5, 15))

        ttk.Label(col2_inner, text="PDF Dosya Adı:", style="Normal.TLabel").pack(anchor="w")
        self.pdf_adi_var = tk.StringVar(value="Kitap.pdf")
        self.entry_isim = ttk.Entry(col2_inner, textvariable=self.pdf_adi_var)
        self.entry_isim.pack(fill="x", pady=(5, 15))

        ttk.Label(col2_inner, text="PDF Kalitesi:", style="Normal.TLabel").pack(anchor="w")
        self.kalite_var = tk.StringVar(value="Normal (Önerilen)")
        self.combo_kalite = ttk.Combobox(col2_inner, textvariable=self.kalite_var, values=["Normal (Önerilen)", "Yüksek (Yavaş)", "Ultra (Yazılımsal 2x)"], state="readonly")
        self.combo_kalite.current(0)
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

        # Oturum Bilgisi (with Reset button)
        ttk.Separator(col3_inner, orient='horizontal').pack(fill='x', pady=15)
        
        session_frame = tk.Frame(col3_inner, bg=self.card_color)
        session_frame.pack(fill='x')
        
        self.lbl_session_info = ttk.Label(session_frame, text="📄 Toplam: 0 sayfa", style="Normal.TLabel")
        self.lbl_session_info.pack(side="left")
        
        # Sıfırla butonu (× işareti, sadece sayfa varken aktif)
        self.btn_sifirla = tk.Label(session_frame, text="×", font=("Segoe UI", 14, "bold"), 
                                     fg="#CCCCCC", bg=self.card_color, cursor="arrow")
        self.btn_sifirla.pack(side="right", padx=(10, 0))
        self.btn_sifirla.bind("<Button-1>", lambda e: self.reset_session() if self.image_data_list else None)
        self.btn_sifirla.bind("<Enter>", lambda e: self.btn_sifirla.config(fg="#FF3B30") if self.image_data_list else None)
        self.btn_sifirla.bind("<Leave>", lambda e: self.btn_sifirla.config(fg="#CCCCCC" if not self.image_data_list else "#888888"))

        # --- Alt Bölüm: Butonlar ---
        bottom_frame = ttk.Frame(self, padding=(20, 10, 20, 20))
        bottom_frame.pack(fill="x")
        
        # ESC İpucu (üstte, küçük)
        esc_hint = ttk.Label(bottom_frame, text="💡 Yakalama sırasında ESC ile duraklatın", 
                             font=("Segoe UI", 9), foreground="#888888")
        esc_hint.pack(pady=(0, 8))
        
        # Ana Buton Container (2 buton)
        btn_container = tk.Frame(bottom_frame, bg=self.bg_color)
        btn_container.pack(fill="x")
        btn_container.columnconfigure(0, weight=3)
        btn_container.columnconfigure(1, weight=2)

        self.btn_baslat = ttk.Button(btn_container, text="▶  Başlat / Devam Et", style="Large.TButton", command=self.baslat_otomasyon)
        self.btn_baslat.grid(row=0, column=0, sticky="ew", padx=(0, 8), ipady=12)

        self.btn_bitir = ttk.Button(btn_container, text="✓  PDF Oluştur", style="Green.TButton", command=self.finalize_pdf, state="disabled")
        self.btn_bitir.grid(row=0, column=1, sticky="ew", ipady=12)

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

    def update_session_info(self):
        count = len(self.image_data_list)
        self.lbl_session_info.config(text=f"📄 Toplam: {count} sayfa")
    
    def _on_global_key(self, key):
        """Global keyboard listener - Escape tuşu ile duraklatma."""
        try:
            if key == keyboard.Key.esc and self.is_running:
                self.stop_event.set()
        except AttributeError:
            pass
    
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
            self.lbl_alan_durum.config(text=f"Seçildi: ({w}x{h})", foreground="green")
            self.update_status("Sayfa alanı seçildi.")
    
    def sec_sonraki_buton(self):
        self.withdraw()
        selector = SelectionWindow(self, 'point')
        self.wait_window(selector)
        self.deiconify()
        
        if selector.result:
            p_x, p_y = int(selector.result[0]), int(selector.result[1])
            self.sonraki_buton = (p_x, p_y)
            self.lbl_buton_durum.config(text=f"Seçildi: ({p_x}, {p_y})", foreground="green")
            self.update_status("Sonraki sayfa butonu seçildi.")

    def baslat_otomasyon(self):
        try:
            self.toplam_sayfa = int(self.toplam_sayfa_var.get())
            self.bekleme_suresi = float(self.bekleme_suresi_var.get())
            pdf_adi = self.pdf_adi_var.get()
            self.kalite = self.kalite_var.get()
        except ValueError:
            messagebox.showerror("Hata", "Lütfen geçerli sayılar girin.")
            return
        
        if not self.sayfa_alani or not self.sonraki_buton:
            messagebox.showerror("Hata", "Lütfen önce her iki alanı da seçin.")
            return
        
        if not pdf_adi.lower().endswith(".pdf"):
            pdf_adi += ".pdf"

        desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
        self.full_pdf_path = os.path.join(desktop_path, pdf_adi)

        self.enhancements = {
            'sharpness': self.keskinlestirme_var.get(),
            'contrast': self.kontrast_var.get(),
            'grayscale': self.siyah_beyaz_var.get()
        }

        try:
            self.scale_factor = self.winfo_tkscaling()
        except Exception:
            self.scale_factor = 1.0

        # UI durumunu güncelle
        self.btn_baslat.config(state="disabled")
        self.btn_bitir.config(state="disabled")
        self.stop_event.clear()
        self.is_running = True

        self.withdraw()
        self.start_countdown(3)

    def pause_automation(self):
        """Otomasyonu duraklatır ve ana pencereyi geri getirir."""
        self.stop_event.set()
        self.update_status("Duraklatılıyor...")

    def finalize_pdf(self):
        """Biriken görüntülerden PDF oluşturur."""
        if not self.image_data_list:
            messagebox.showwarning("Uyarı", "Henüz yakalanan sayfa yok.")
            return
        
        self.create_pdf_with_pymupdf(
            self.image_data_list,
            self.full_pdf_path,
            self.kalite,
            self.enhancements,
            self.scale_factor
        )
        
        # Oturumu sıfırla
        self.image_data_list = []
        self.update_session_info()
        self.btn_bitir.config(state="disabled")
        self.btn_sifirla.config(fg="#CCCCCC", cursor="arrow")
        self.update_status("PDF oluşturuldu. Yeni oturum başlatılabilir.")

    def reset_session(self):
        """Biriken sayfaları sıfırla ve baştan başla."""
        if self.image_data_list:
            result = messagebox.askyesno(
                "Oturumu Sıfırla", 
                f"{len(self.image_data_list)} sayfa silinecek. Emin misiniz?"
            )
            if not result:
                return
        
        self.image_data_list = []
        self.update_session_info()
        self.btn_bitir.config(state="disabled")
        self.btn_sifirla.config(fg="#CCCCCC", cursor="arrow")
        self.update_status("Oturum sıfırlandı. Yeniden başlayabilirsiniz.")

    def start_countdown(self, count):
        countdown_win = tk.Toplevel(self)
        win_w, win_h = 250, 250
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (win_w // 2)
        y = (screen_h // 2) - (win_h // 2)
        countdown_win.geometry(f'{win_w}x{win_h}+{x}+{y}')
        countdown_win.overrideredirect(True)
        
        bg_color = "#2C2C2E"
        fg_color = "#FFFFFF"
        countdown_win.configure(bg=bg_color)
        
        frame = tk.Frame(countdown_win, bg=bg_color, highlightbackground="#505050", highlightthickness=1)
        frame.pack(fill='both', expand=True)

        tk.Label(frame, text="Başlıyor...", font=('Segoe UI', 16), bg=bg_color, fg="#B0B0B0").pack(pady=(40, 10))
        
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
        sayfa_alani = self.sayfa_alani
        sonraki_buton = self.sonraki_buton
        toplam_sayfa = self.toplam_sayfa
        bekleme_suresi = self.bekleme_suresi
        kalite = self.kalite
        scale_factor = self.scale_factor

        try:
            # İlk yakalamadan önce kısa bekleme (ortamın hazır olması için)
            time.sleep(0.5)
            
            with mss() as sct:
                for i in range(1, toplam_sayfa + 1):
                    # Duraklatma kontrolü
                    if self.stop_event.is_set():
                        self.after(0, self._on_paused)
                        return
                    
                    current_total = len(self.image_data_list) + 1
                    self.after(0, self.update_status, f"Sayfa {i}/{toplam_sayfa} yakalanıyor... (Toplam: {current_total})")
                    
                    # Görüntü yakala
                    if sys.platform == 'darwin' and kalite in ["Yüksek (Yavaş)", "Ultra (Yazılımsal 2x)"]:
                        l_x = sayfa_alani['left'] / scale_factor
                        l_y = sayfa_alani['top'] / scale_factor
                        l_w = sayfa_alani['width'] / scale_factor
                        l_h = sayfa_alani['height'] / scale_factor
                        
                        temp_filename = f"temp_capture_{time.time()}.png"
                        cmd = ["screencapture", "-x", "-R", f"{l_x},{l_y},{l_w},{l_h}", temp_filename]
                        subprocess.run(cmd, check=True)
                        
                        img = Image.open(temp_filename)
                        if img.mode != 'RGBA':
                            img = img.convert('RGBA')
                        bgra_data = img.tobytes("raw", "BGRA")
                        
                        self.image_data_list.append({
                            "pixels": bgra_data,
                            "width": img.width,
                            "height": img.height,
                        })
                        os.remove(temp_filename)
                    else:
                        sct_img = sct.grab(sayfa_alani)
                        self.image_data_list.append({
                            "pixels": sct_img.bgra,
                            "width": sct_img.width,
                            "height": sct_img.height,
                        })
                    
                    self.after(0, self.update_session_info)
                    
                    # Son sayfa değilse, sonraki sayfaya geç
                    if i < toplam_sayfa:
                        self.mouse.position = sonraki_buton
                        self.mouse.click(Button.left)
                        time.sleep(bekleme_suresi)
            
            # Tüm sayfalar tamamlandı
            self.after(0, self._on_completed)
            
        except Exception as e:
            self.after(0, messagebox.showerror, "Otomasyon Hatası", f"Bir hata oluştu: {e}")
            self.after(0, self._on_error)

    def _on_paused(self):
        """Duraklatma sonrası UI güncellemesi."""
        self.is_running = False
        self.deiconify()
        self.btn_baslat.config(state="normal")
        self.btn_bitir.config(state="normal")
        self.btn_sifirla.config(fg="#888888", cursor="hand2")
        self.update_status(f"Duraklatıldı. {len(self.image_data_list)} sayfa birikti.")

    def _on_completed(self):
        """Otomasyon tamamlandığında UI güncellemesi."""
        self.is_running = False
        self.deiconify()
        self.btn_baslat.config(state="normal")
        self.btn_bitir.config(state="normal")
        self.btn_sifirla.config(fg="#888888", cursor="hand2")
        self.update_status(f"Tamamlandı! {len(self.image_data_list)} sayfa birikti. PDF oluşturabilirsiniz.")

    def _on_error(self):
        """Hata durumunda UI güncellemesi."""
        self.is_running = False
        self.deiconify()
        self.btn_baslat.config(state="normal")
        if self.image_data_list:
            self.btn_bitir.config(state="normal")

    def create_pdf_with_pymupdf(self, image_data_list, pdf_path, kalite, enhancements, scale_factor=1.0):
        if not image_data_list:
            messagebox.showwarning("PDF Hatası", "Hiç görüntü yakalanamadı.")
            return

        try:
            doc = fitz.open()
            
            for image_data in image_data_list:
                width = image_data["width"]
                height = image_data["height"]
                pixels = image_data["pixels"]
                
                pil_img = Image.frombytes("RGBA", (width, height), pixels, "raw", "BGRA")
                
                if enhancements['grayscale']:
                    pil_img = ImageOps.grayscale(pil_img).convert("RGB")
                elif pil_img.mode == 'RGBA':
                    pil_img = pil_img.convert("RGB")
                
                if enhancements['contrast']:
                    enhancer = ImageEnhance.Contrast(pil_img)
                    pil_img = enhancer.enhance(1.5)
                
                if enhancements['sharpness']:
                    enhancer = ImageEnhance.Sharpness(pil_img)
                    pil_img = enhancer.enhance(2.0)
                
                if kalite == "Ultra (Yazılımsal 2x)":
                    new_width = int(width * 2)
                    new_height = int(height * 2)
                    pil_img = pil_img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    width, height = new_width, new_height

                page_width = width / scale_factor
                page_height = height / scale_factor

                if kalite in ["Yüksek (Yavaş)", "Ultra (Yazılımsal 2x)"]:
                    rgb_pixels = pil_img.tobytes()
                    pix = fitz.Pixmap(fitz.csRGB, width, height, rgb_pixels, False)
                    page = doc.new_page(width=page_width, height=page_height)
                    page.insert_image(fitz.Rect(0, 0, page_width, page_height), pixmap=pix)
                else:
                    quality_setting = 75 if kalite == "Normal (Önerilen)" else 50
                    img_buffer = io.BytesIO()
                    pil_img.save(img_buffer, format="jpeg", quality=quality_setting)
                    img_buffer.seek(0)
                    
                    page = doc.new_page(width=page_width, height=page_height)
                    page.insert_image(fitz.Rect(0, 0, page_width, page_height), stream=img_buffer)

            doc.save(pdf_path, garbage=4, deflate=True)
            doc.close()
            
            messagebox.showinfo("Başarılı", f"PDF dosyası Masaüstü'ne kaydedildi!\n\nToplam: {len(image_data_list)} sayfa\nYol: {pdf_path}")
        except Exception as e:
            messagebox.showerror("PDF Oluşturma Hatası", f"PyMuPDF ile PDF oluşturulurken bir hata oluştu: {e}")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = Book2PdfApp()
    app.mainloop()
