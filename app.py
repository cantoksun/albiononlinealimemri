import json
import math
import os
import random
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import cv2
import mss
import numpy as np
import pyautogui
from pynput import keyboard

pyautogui.FAILSAFE = True

dizin = os.path.dirname(os.path.abspath(__file__))
config_yolu = os.path.join(dizin, "items_config.json")
koordinat_yolu = os.path.join(dizin, "screen_coords.json")
durum_yolu = os.path.join(dizin, "bot_state.json")
sablon_dizin = os.path.join(dizin, "templates")

os.makedirs(sablon_dizin, exist_ok=True)

def fare_hareketi(hedef_x, hedef_y, durdurma_sinyali, sure=None):
    baslangic_x, baslangic_y = pyautogui.position()
    mesafe = math.hypot(hedef_x - baslangic_x, hedef_y - baslangic_y)
    if mesafe < 15:
        pyautogui.moveTo(hedef_x, hedef_y)
        return

    if sure is None:
        sure = random.uniform(0.14, 0.28) + (mesafe / 4200.0)

    nokta1_x = baslangic_x + (hedef_x - baslangic_x) * random.uniform(0.15, 0.45) + random.randint(-30, 30)
    nokta1_y = baslangic_y + (hedef_y - baslangic_y) * random.uniform(0.15, 0.45) + random.randint(-30, 30)
    nokta2_x = baslangic_x + (hedef_x - baslangic_x) * random.uniform(0.55, 0.85) + random.randint(-20, 20)
    nokta2_y = baslangic_y + (hedef_y - baslangic_y) * random.uniform(0.55, 0.85) + random.randint(-20, 20)

    adimlar = max(10, int(sure * 60))
    for i in range(1, adimlar + 1):
        if durdurma_sinyali.is_set():
            break
        t = i / adimlar
        t_yavas = t * t * (3.0 - 2.0 * t)
        
        mevcut_x = int((1 - t_yavas)**3 * baslangic_x + 3 * (1 - t_yavas)**2 * t_yavas * nokta1_x + 3 * (1 - t_yavas) * t_yavas**2 * nokta2_x + t_yavas**3 * hedef_x)
        mevcut_y = int((1 - t_yavas)**3 * baslangic_y + 3 * (1 - t_yavas)**2 * t_yavas * nokta1_y + 3 * (1 - t_yavas) * t_yavas**2 * nokta2_y + t_yavas**3 * hedef_y)
        
        pyautogui.moveTo(mevcut_x, mevcut_y)
        time.sleep(sure / adimlar)

class PazarBotu:
    def __init__(self, pencere):
        self.pencere = pencere
        self.pencere.title("albion pazar aracı")
        self.pencere.geometry("1100x720")
        self.pencere.minsize(920, 580)

        stil = ttk.Style()
        try:
            stil.theme_use("vista")
        except Exception:
            stil.theme_use("default")

        self.ekran_alici = mss.mss()
        self.ayarlar = self.ayar_oku()
        self.koordinatlar = self.koordinat_oku()
        self.aktif_sira = self.durum_oku()
        self.durdurma = threading.Event()
        self.arka_is = None

        self.arayuz_olustur()
        self.listeyi_doldur()
        self.kisayol_dinleyici()
        self.buton_metnini_guncelle()

    def kisayol_dinleyici(self):
        def basildi(tus):
            try:
                if tus == keyboard.Key.f12 or tus == keyboard.Key.f10:
                    if not self.durdurma.is_set() and self.arka_is and self.arka_is.is_alive():
                        self.pencere.after(0, self.acil_durdur)
            except Exception:
                pass

        dinleyici = keyboard.Listener(on_press=basildi)
        dinleyici.daemon = True
        dinleyici.start()

    def acil_durdur(self):
        self.durdur()
        self.yaz("f12 tuşlandı, işlem durduruldu.")

    def ayar_oku(self):
        if os.path.exists(config_yolu):
            try:
                with open(config_yolu, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"defaults": {}, "items": {}}

    def ayar_kaydet(self):
        try:
            with open(config_yolu, "w", encoding="utf-8") as f:
                json.dump(self.ayarlar, f, indent=2, ensure_ascii=False)
            self.yaz("ayarlar kaydedildi.")
        except Exception as e:
            messagebox.showerror("hata", f"kaydedilemedi: {e}")

    def koordinat_oku(self):
        varsayilan = {
            "search_box": None,
            "first_item": None,
            "buy_order_tab": None,
            "price_input": None,
            "amount_input": None,
            "confirm_button": None,
            "popup_yes_button": None
        }
        if os.path.exists(koordinat_yolu):
            try:
                with open(koordinat_yolu, "r", encoding="utf-8") as f:
                    veri = json.load(f)
                    varsayilan.update(veri)
                    return varsayilan
            except Exception:
                pass
        return varsayilan

    def koordinat_kaydet(self):
        try:
            with open(koordinat_yolu, "w", encoding="utf-8") as f:
                json.dump(self.koordinatlar, f, indent=2)
            self.yaz("koordinatlar kaydedildi.")
        except Exception:
            pass

    def durum_oku(self):
        if os.path.exists(durum_yolu):
            try:
                with open(durum_yolu, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    return st.get("last_index", 0)
            except Exception:
                pass
        return 0

    def durum_kaydet(self, sira):
        try:
            with open(durum_yolu, "w", encoding="utf-8") as f:
                json.dump({"last_index": sira, "updated_at": time.strftime("%Y-%m-%d %H:%M:%S")}, f)
        except Exception:
            pass

    def secili_itemler(self):
        items = self.ayarlar.get("items", {})
        return [(k, v) for k, v in items.items() if v.get("enabled", True)]

    def sira_belirle(self, yeni_sira):
        liste = self.secili_itemler()
        toplam = len(liste)
        if toplam == 0:
            return
        yeni_sira = max(0, min(yeni_sira, toplam - 1))
        self.aktif_sira = yeni_sira
        self.durum_kaydet(yeni_sira)
        self.buton_metnini_guncelle()
        ad = liste[yeni_sira][1].get("name", liste[yeni_sira][0])
        self.yaz(f"sıra: {yeni_sira + 1}/{toplam} ({ad.lower()})")

    def girdiden_siraya_git(self):
        try:
            hedef = int(self.giris_sira.get().strip()) - 1
            self.sira_belirle(hedef)
        except ValueError:
            pass

    def seciliden_basla(self):
        if not hasattr(self, "secilen_anahtar"):
            return
        liste = self.secili_itemler()
        for i, (k, v) in enumerate(liste):
            if k == self.secilen_anahtar:
                self.sira_belirle(i)
                break

    def sifirla(self):
        self.sira_belirle(0)
        self.yaz("sıralama sıfırlandı.")

    def buton_metnini_guncelle(self):
        liste = self.secili_itemler()
        toplam = len(liste)
        if self.aktif_sira > 0 and self.aktif_sira < toplam:
            ad = liste[self.aktif_sira][1].get("name", "")[:18].lower()
            self.btn_baslat.config(text=f"devam et ({self.aktif_sira + 1}. item: {ad})")
        else:
            self.btn_baslat.config(text="başlat (1. item)")
        self.lbl_durum.config(text=f"sıra: {self.aktif_sira + 1 if toplam > 0 else 0} / {toplam}")

    def arayuz_olustur(self):
        ust_serit = ttk.Frame(self.pencere, padding=6)
        ust_serit.pack(fill=tk.X)

        ttk.Label(ust_serit, text="arama:").pack(side=tk.LEFT, padx=(0, 2))
        self.arama_metni = tk.StringVar()
        self.arama_metni.trace_add("write", lambda *args: self.listeyi_doldur())
        ttk.Entry(ust_serit, textvariable=self.arama_metni, width=16).pack(side=tk.LEFT, padx=3)

        ttk.Label(ust_serit, text="tier:").pack(side=tk.LEFT, padx=(8, 2))
        self.tier_secimi = ttk.Combobox(ust_serit, values=["hepsi", "t1", "t2", "t3", "t4", "t5", "t6", "t7", "t8"], state="readonly", width=6)
        self.tier_secimi.set("hepsi")
        self.tier_secimi.bind("<<ComboboxSelected>>", lambda e: self.listeyi_doldur())
        self.tier_secimi.pack(side=tk.LEFT, padx=2)

        ttk.Label(ust_serit, text="kategori:").pack(side=tk.LEFT, padx=(8, 2))
        kategoriler = ["hepsi", "weapon", "armor", "resources", "bag", "cape", "food", "potion", "mount", "tool", "material", "furniture", "other"]
        self.kat_secimi = ttk.Combobox(ust_serit, values=kategoriler, state="readonly", width=9)
        self.kat_secimi.set("hepsi")
        self.kat_secimi.bind("<<ComboboxSelected>>", lambda e: self.listeyi_doldur())
        self.kat_secimi.pack(side=tk.LEFT, padx=2)

        self.limit_metni = tk.StringVar(value="300")
        ttk.Label(ust_serit, text="göster:").pack(side=tk.LEFT, padx=(8, 2))
        self.limit_kutusu = ttk.Combobox(ust_serit, textvariable=self.limit_metni, values=["100", "300", "1000", "tümü"], state="readonly", width=6)
        self.limit_kutusu.bind("<<ComboboxSelected>>", lambda e: self.listeyi_doldur())
        self.limit_kutusu.pack(side=tk.LEFT, padx=2)

        ttk.Button(ust_serit, text="tümünü seç", command=lambda: self.toplu_secim(True)).pack(side=tk.RIGHT, padx=2)
        ttk.Button(ust_serit, text="tümünü kaldır", command=lambda: self.toplu_secim(False)).pack(side=tk.RIGHT, padx=2)

        bolucu = ttk.PanedWindow(self.pencere, orient=tk.HORIZONTAL)
        bolucu.pack(fill=tk.BOTH, expand=True, padx=6, pady=2)

        sol_kutu = ttk.Frame(bolucu)
        bolucu.add(sol_kutu, weight=3)

        sutunlar = ("enabled", "tier", "category", "name", "price", "amount")
        self.tablo = ttk.Treeview(sol_kutu, columns=sutunlar, show="headings", selectmode="browse")
        self.tablo.heading("enabled", text="aktif")
        self.tablo.heading("tier", text="tier")
        self.tablo.heading("category", text="kategori")
        self.tablo.heading("name", text="item")
        self.tablo.heading("price", text="fiyat")
        self.tablo.heading("amount", text="adet")

        self.tablo.column("enabled", width=42, anchor=tk.CENTER)
        self.tablo.column("tier", width=40, anchor=tk.CENTER)
        self.tablo.column("category", width=75)
        self.tablo.column("name", width=250)
        self.tablo.column("price", width=70, anchor=tk.E)
        self.tablo.column("amount", width=45, anchor=tk.E)

        kaydirma = ttk.Scrollbar(sol_kutu, orient=tk.VERTICAL, command=self.tablo.yview)
        self.tablo.configure(yscrollcommand=kaydirma.set)
        self.tablo.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        kaydirma.pack(side=tk.RIGHT, fill=tk.Y)
        self.tablo.bind("<<TreeviewSelect>>", self.item_secildi)

        sag_kutu = ttk.Frame(bolucu, padding=4)
        bolucu.add(sag_kutu, weight=2)

        grup_item = ttk.LabelFrame(sag_kutu, text="seçili item", padding=6)
        grup_item.pack(fill=tk.X, pady=2)

        ttk.Label(grup_item, text="isim:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.lbl_secili_ad = ttk.Label(grup_item, text="seçim yok", font=("Segoe UI", 9, "bold"))
        self.lbl_secili_ad.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(grup_item, text="fiyat:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.giris_fiyat = ttk.Entry(grup_item, width=12)
        self.giris_fiyat.grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(grup_item, text="adet:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.giris_adet = ttk.Entry(grup_item, width=12)
        self.giris_adet.grid(row=2, column=1, sticky=tk.W, pady=2)

        self.var_aktif = tk.BooleanVar(value=True)
        ttk.Checkbutton(grup_item, text="alım emri verilsin", variable=self.var_aktif).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=2)

        satir_btn = ttk.Frame(grup_item)
        satir_btn.grid(row=4, column=0, columnspan=2, sticky=tk.EW, pady=2)
        ttk.Button(satir_btn, text="kaydet", command=self.secili_kaydet).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        ttk.Button(satir_btn, text="buradan başla", command=self.seciliden_basla).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=1)

        grup_sira = ttk.LabelFrame(sag_kutu, text="sıra yönetimi", padding=6)
        grup_sira.pack(fill=tk.X, pady=2)

        sira_satir1 = ttk.Frame(grup_sira)
        sira_satir1.pack(fill=tk.X, pady=1)
        ttk.Button(sira_satir1, text="-10", width=4, command=lambda: self.sira_belirle(self.aktif_sira - 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        ttk.Button(sira_satir1, text="-1", width=4, command=lambda: self.sira_belirle(self.aktif_sira - 1)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        ttk.Button(sira_satir1, text="+1", width=4, command=lambda: self.sira_belirle(self.aktif_sira + 1)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        ttk.Button(sira_satir1, text="+10", width=4, command=lambda: self.sira_belirle(self.aktif_sira + 10)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        sira_satir2 = ttk.Frame(grup_sira)
        sira_satir2.pack(fill=tk.X, pady=2)
        ttk.Label(sira_satir2, text="sıraya git:").pack(side=tk.LEFT, padx=2)
        self.giris_sira = ttk.Entry(sira_satir2, width=6)
        self.giris_sira.insert(0, "1")
        self.giris_sira.pack(side=tk.LEFT, padx=2)
        ttk.Button(sira_satir2, text="git", width=4, command=self.girdiden_siraya_git).pack(side=tk.LEFT, padx=1)

        grup_toplu = ttk.LabelFrame(sag_kutu, text="toplu fiyat", padding=6)
        grup_toplu.pack(fill=tk.X, pady=2)

        satir_toplu = ttk.Frame(grup_toplu)
        satir_toplu.pack(fill=tk.X)
        ttk.Label(satir_toplu, text="tutar:").pack(side=tk.LEFT, padx=2)
        self.giris_toplu_fiyat = ttk.Entry(satir_toplu, width=8)
        self.giris_toplu_fiyat.insert(0, "5")
        self.giris_toplu_fiyat.pack(side=tk.LEFT, padx=2)
        ttk.Button(satir_toplu, text="filtrelenenlere uygula", command=self.toplu_fiyat_uygula).pack(side=tk.LEFT, padx=2)

        grup_kalib = ttk.LabelFrame(sag_kutu, text="kalibrasyon", padding=6)
        grup_kalib.pack(fill=tk.X, pady=2)

        kalib_grid = ttk.Frame(grup_kalib)
        kalib_grid.pack(fill=tk.X)
        ttk.Button(kalib_grid, text="1. arama kutusu", command=lambda: self.kalibre_et("search_box", "arama kutusuna getirin")).grid(row=0, column=0, sticky=tk.EW, padx=1, pady=1)
        ttk.Button(kalib_grid, text="2. ilk item", command=lambda: self.kalibre_et("first_item", "ilk iteme getirin")).grid(row=0, column=1, sticky=tk.EW, padx=1, pady=1)
        ttk.Button(kalib_grid, text="3. alım emri sekmesi", command=lambda: self.kalibre_et("buy_order_tab", "sekmenin üzerine getirin")).grid(row=1, column=0, sticky=tk.EW, padx=1, pady=1)
        ttk.Button(kalib_grid, text="4. fiyat kutusu", command=lambda: self.kalibre_et("price_input", "fiyat kutusuna getirin")).grid(row=1, column=1, sticky=tk.EW, padx=1, pady=1)
        ttk.Button(kalib_grid, text="5. miktar kutusu", command=lambda: self.kalibre_et("amount_input", "miktar kutusuna getirin")).grid(row=2, column=0, sticky=tk.EW, padx=1, pady=1)
        ttk.Button(kalib_grid, text="6. onay butonu", command=lambda: self.kalibre_et("confirm_button", "onay butonuna getirin")).grid(row=2, column=1, sticky=tk.EW, padx=1, pady=1)
        kalib_grid.columnconfigure(0, weight=1)
        kalib_grid.columnconfigure(1, weight=1)

        ttk.Button(grup_kalib, text="7. açılan uyarıdaki 'yes' butonu", command=self.kalibre_popup).pack(fill=tk.X, pady=2)

        grup_hareket = ttk.LabelFrame(sag_kutu, text="gecikme ve hareket", padding=6)
        grup_hareket.pack(fill=tk.X, pady=2)

        self.var_insansi = tk.BooleanVar(value=True)
        ttk.Checkbutton(grup_hareket, text="insansı fare ve tuşlama modu", variable=self.var_insansi).pack(anchor=tk.W)

        satir_h = ttk.Frame(grup_hareket)
        satir_h.pack(fill=tk.X, pady=1)
        ttk.Label(satir_h, text="gecikme (sn):").pack(side=tk.LEFT)
        self.spin_min = ttk.Spinbox(satir_h, from_=0.2, to=5.0, increment=0.2, width=4)
        self.spin_min.set(0.6)
        self.spin_min.pack(side=tk.LEFT, padx=2)
        ttk.Label(satir_h, text="-").pack(side=tk.LEFT)
        self.spin_max = ttk.Spinbox(satir_h, from_=0.5, to=10.0, increment=0.2, width=4)
        self.spin_max.set(1.6)
        self.spin_max.pack(side=tk.LEFT, padx=2)

        self.var_kavis = tk.BooleanVar(value=True)
        self.var_sapma = tk.BooleanVar(value=True)
        self.var_mola = tk.BooleanVar(value=False)

        kutucuklar = ttk.Frame(grup_hareket)
        kutucuklar.pack(fill=tk.X)
        ttk.Checkbutton(kutucuklar, text="kavisli fare", variable=self.var_kavis).pack(side=tk.LEFT)
        ttk.Checkbutton(kutucuklar, text="piksel sapması", variable=self.var_sapma).pack(side=tk.LEFT, padx=4)
        ttk.Checkbutton(kutucuklar, text="ara mola", variable=self.var_mola).pack(side=tk.LEFT)

        alan_calis = ttk.Frame(sag_kutu, padding=4)
        alan_calis.pack(fill=tk.X, pady=2)

        self.lbl_durum = ttk.Label(alan_calis, text="sıra: 0 / 0", font=("Segoe UI", 9, "bold"))
        self.lbl_durum.pack(fill=tk.X, pady=1)

        satir_calis = ttk.Frame(alan_calis)
        satir_calis.pack(fill=tk.X, pady=2)

        self.btn_baslat = ttk.Button(satir_calis, text="başlat", command=self.baslat)
        self.btn_baslat.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        self.btn_durdur = ttk.Button(satir_calis, text="durdur (f12)", command=self.durdur, state=tk.DISABLED)
        self.btn_durdur.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        self.btn_sifirla = ttk.Button(satir_calis, text="sıfırla", width=6, command=self.sifirla)
        self.btn_sifirla.pack(side=tk.RIGHT, padx=1)

        ttk.Label(alan_calis, text="acil durdurmak için f12 tuşuna basabilirsiniz", font=("Segoe UI", 8)).pack(fill=tk.X, pady=1)

        log_kutusu = ttk.LabelFrame(self.pencere, text="günlük", padding=4)
        log_kutusu.pack(fill=tk.BOTH, expand=False, padx=6, pady=(2, 6))

        self.yazi_alani = tk.Text(log_kutusu, height=4, relief="solid", bd=1, font=("Consolas", 9))
        self.yazi_alani.pack(fill=tk.BOTH, expand=True)

        toplam = len(self.ayarlar.get("items", {}))
        self.yaz(f"hazır. {toplam:,} item yüklendi. (durdurma: f12)")

    def yaz(self, metin):
        zaman = time.strftime("[%H:%M:%S] ")
        self.yazi_alani.insert(tk.END, zaman + metin.lower() + "\n")
        self.yazi_alani.see(tk.END)

    def listeyi_doldur(self):
        for satir in self.tablo.get_children():
            self.tablo.delete(satir)

        aranan = self.arama_metni.get().strip().lower()
        tier_s = self.tier_secimi.get().lower()
        kat_s = self.kat_secimi.get().lower()
        lim_s = self.limit_metni.get().lower()
        limit = 99999 if "tümü" in lim_s else int(lim_s)

        sayac = 0
        for anahtar, item in self.ayarlar.get("items", {}).items():
            ad = item.get("name", anahtar).lower()
            tier = item.get("tier", "").lower()
            kat = item.get("category", "").lower()
            fiyat = item.get("price", 5)
            adet = item.get("amount", 1)
            aktif = "+" if item.get("enabled", True) else "-"

            if aranan and (aranan not in ad and aranan not in anahtar.lower()):
                continue
            if tier_s != "hepsi" and tier != tier_s:
                continue
            if kat_s != "hepsi" and kat != kat_s:
                continue

            self.tablo.insert("", tk.END, iid=anahtar, values=(aktif, tier, kat, ad, f"{fiyat:,}", adet))
            sayac += 1
            if sayac >= limit:
                break

    def item_secildi(self, olay):
        secilen = self.tablo.selection()
        if not secilen:
            return
        anahtar = secilen[0]
        item = self.ayarlar["items"].get(anahtar, {})
        self.secilen_anahtar = anahtar
        self.lbl_secili_ad.config(text=f"{item.get('name', anahtar)[:22].lower()} ({anahtar.lower()})")
        self.giris_fiyat.delete(0, tk.END)
        self.giris_fiyat.insert(0, str(item.get("price", 5)))
        self.giris_adet.delete(0, tk.END)
        self.giris_adet.insert(0, str(item.get("amount", 1)))
        self.var_aktif.set(item.get("enabled", True))

    def secili_kaydet(self):
        if not hasattr(self, "secilen_anahtar"):
            return
        anahtar = self.secilen_anahtar
        try:
            yeni_fiyat = int(self.giris_fiyat.get().replace(",", "").strip())
            yeni_adet = int(self.giris_adet.get().strip())
            yeni_aktif = self.var_aktif.get()
            
            self.ayarlar["items"][anahtar]["price"] = yeni_fiyat
            self.ayarlar["items"][anahtar]["amount"] = yeni_adet
            self.ayarlar["items"][anahtar]["enabled"] = yeni_aktif

            self.ayar_kaydet()
            self.listeyi_doldur()
            self.buton_metnini_guncelle()
        except ValueError:
            pass

    def toplu_fiyat_uygula(self):
        try:
            toplu_fiyat = int(self.giris_toplu_fiyat.get().replace(",", "").strip())
        except ValueError:
            return

        gorunenler = self.tablo.get_children()
        if not gorunenler:
            return

        for k in gorunenler:
            if k in self.ayarlar.get("items", {}):
                self.ayarlar["items"][k]["price"] = toplu_fiyat

        self.ayar_kaydet()
        self.listeyi_doldur()
        self.yaz(f"{len(gorunenler)} item için fiyat {toplu_fiyat} silver yapıldı.")

    def toplu_secim(self, durum):
        gorunenler = self.tablo.get_children()
        for k in gorunenler:
            if k in self.ayarlar.get("items", {}):
                self.ayarlar["items"][k]["enabled"] = durum
        self.ayar_kaydet()
        self.listeyi_doldur()
        self.buton_metnini_guncelle()
        self.yaz(f"{len(gorunenler)} item {'açıldı' if durum else 'kapatıldı'}.")

    def kalibre_et(self, alan, aciklama):
        def calis():
            for i in range(3, 0, -1):
                self.yaz(f"{aciklama} ({i} sn...)")
                time.sleep(1)
            konum = pyautogui.position()
            self.koordinatlar[alan] = [konum.x, konum.y]
            self.koordinat_kaydet()
            self.yaz(f"{alan} koordinatı: {konum.x}, {konum.y}")

        threading.Thread(target=calis, daemon=True).start()

    def kalibre_popup(self):
        def calis():
            for i in range(3, 0, -1):
                self.yaz(f"fareyi 'yes' butonuna getirin ({i} sn)...")
                time.sleep(1)
            konum = pyautogui.position()
            self.koordinatlar["popup_yes_button"] = [konum.x, konum.y]
            self.koordinat_kaydet()

            try:
                bolge = {"top": max(0, konum.y - 18), "left": max(0, konum.x - 35), "width": 70, "height": 36}
                goruntu = np.array(self.ekran_alici.grab(bolge))
                gri = cv2.cvtColor(goruntu, cv2.COLOR_BGRA2GRAY)
                sablon_yol = os.path.join(sablon_dizin, "popup_yes.png")
                cv2.imwrite(sablon_yol, gri)
                self.yaz("şablon kaydedildi.")
            except Exception:
                pass

            self.yaz(f"yes butonu: {konum.x}, {konum.y}")

        threading.Thread(target=calis, daemon=True).start()

    def tikla(self, x, y):
        if self.durdurma.is_set():
            return
        hedef_x, hedef_y = x, y

        if self.var_insansi.get():
            if self.var_sapma.get():
                hedef_x += random.randint(-5, 5)
                hedef_y += random.randint(-3, 3)

            if self.var_kavis.get():
                fare_hareketi(hedef_x, hedef_y, self.durdurma)
            else:
                pyautogui.moveTo(hedef_x, hedef_y, duration=random.uniform(0.1, 0.2))

            if self.durdurma.is_set():
                return
            time.sleep(random.uniform(0.04, 0.08))
            pyautogui.click()
            time.sleep(random.uniform(0.03, 0.06))
        else:
            pyautogui.click(target_x, target_y)

    def yaz_klavye(self, yazi):
        if self.durdurma.is_set():
            return
        if self.var_insansi.get():
            for harf in str(yazi):
                if self.durdurma.is_set():
                    break
                pyautogui.write(harf)
                time.sleep(random.uniform(0.02, 0.05))
        else:
            pyautogui.write(str(yazi), interval=0.01)

    def popup_kontrol(self):
        if self.durdurma.is_set():
            return False
        sablon_yol = os.path.join(sablon_dizin, "popup_yes.png")
        
        if os.path.exists(sablon_yol) and self.koordinatlar.get("popup_yes_button"):
            hedef_x, hedef_y = self.koordinatlar["popup_yes_button"]
            bolge = {
                "top": max(0, hedef_y - 80),
                "left": max(0, hedef_x - 100),
                "width": 200,
                "height": 160
            }
            try:
                ekran = np.array(self.ekran_alici.grab(bolge))
                ekran_gri = cv2.cvtColor(ekran, cv2.COLOR_BGRA2GRAY)
                sablon = cv2.imread(sablon_yol, cv2.IMREAD_GRAYSCALE)
                
                sonuc = cv2.matchTemplate(ekran_gri, sablon, cv2.TM_CCOEFF_NORMED)
                _, en_iyi_deger, _, en_iyi_konum = cv2.minMaxLoc(sonuc)

                if en_iyi_deger >= 0.70:
                    tik_x = bolge["left"] + en_iyi_konum[0] + sablon.shape[1] // 2
                    tik_y = bolge["top"] + en_iyi_konum[1] + sablon.shape[0] // 2
                    self.tikla(tik_x, tik_y)
                    self.yaz("onay penceresi geçildi.")
                    time.sleep(random.uniform(0.06, 0.12))
                    return True
            except Exception:
                pass

        if self.koordinatlar.get("popup_yes_button"):
            self.tikla(*self.koordinatlar["popup_yes_button"])
            time.sleep(0.04)
            return True

        return False

    def baslat(self):
        eksik = [k for k, v in self.koordinatlar.items() if not v and k != "popup_yes_button"]
        if eksik:
            if not messagebox.askyesno("eksik koordinat", f"kalibre edilmeyen butonlar var: {', '.join(eksik)}\ndevam edilsin mi?"):
                return

        self.durdurma.clear()
        self.btn_baslat.config(state=tk.DISABLED)
        self.btn_durdur.config(state=tk.NORMAL)
        self.btn_sifirla.config(state=tk.DISABLED)
        
        self.arka_is = threading.Thread(target=self.bot_dongusu, daemon=True)
        self.arka_is.start()
        self.yaz(f"başlatıldı. {self.aktif_sira + 1}. sıradan devam ediliyor.")

    def durdur(self):
        self.durdurma.set()
        self.btn_baslat.config(state=tk.NORMAL)
        self.btn_durdur.config(state=tk.DISABLED)
        self.btn_sifirla.config(state=tk.NORMAL)
        self.buton_metnini_guncelle()
        self.yaz("durduruldu, sıra kaydedildi.")

    def bot_dongusu(self):
        liste = self.secili_itemler()
        toplam = len(liste)

        if not liste:
            self.pencere.after(0, self.durdur)
            return

        if self.aktif_sira >= toplam:
            self.aktif_sira = 0
            self.durum_kaydet(0)

        sayac = 0
        esik = random.randint(12, 22)

        for i in range(self.aktif_sira, toplam):
            if self.durdurma.is_set():
                break

            anahtar, item = liste[i]
            ad = item.get("name", anahtar).lower()
            fiyat = item.get("price", 5)
            adet = item.get("amount", 1)

            self.yaz(f"[{i + 1}/{toplam}] {ad} | {fiyat} silver")

            try:
                # 1. arama kutusu
                if self.koordinatlar.get("search_box"):
                    self.tikla(*self.koordinatlar["search_box"])
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.04, 0.08))
                    pyautogui.hotkey('ctrl', 'a')
                    pyautogui.press('backspace')
                    kelime = ad.split("(")[0].strip()[:16]
                    self.yaz_klavye(kelime)
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.2, 0.35))

                # 2. ilk item
                if self.koordinatlar.get("first_item"):
                    self.tikla(*self.koordinatlar["first_item"])
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.12, 0.22))

                # 3. alım emri sekmesi
                if self.koordinatlar.get("buy_order_tab"):
                    self.tikla(*self.koordinatlar["buy_order_tab"])
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.12, 0.22))

                # 4. fiyat
                if self.koordinatlar.get("price_input"):
                    self.tikla(*self.koordinatlar["price_input"])
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.04, 0.07))
                    pyautogui.hotkey('ctrl', 'a')
                    pyautogui.press('backspace')
                    self.yaz_klavye(str(fiyat))
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.05, 0.08))

                # 5. miktar
                if self.koordinatlar.get("amount_input"):
                    self.tikla(*self.koordinatlar["amount_input"])
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.04, 0.07))
                    pyautogui.hotkey('ctrl', 'a')
                    pyautogui.press('backspace')
                    self.yaz_klavye(str(adet))
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.05, 0.08))

                # 6. onay
                if self.koordinatlar.get("confirm_button"):
                    self.tikla(*self.koordinatlar["confirm_button"])
                    if self.durdurma.is_set(): break
                    time.sleep(random.uniform(0.1, 0.18))

                # 7. uyarı kontrolü
                self.popup_kontrol()
                if self.durdurma.is_set(): break

                self.aktif_sira = i + 1
                self.durum_kaydet(self.aktif_sira)
                self.pencere.after(0, self.buton_metnini_guncelle)

                self.yaz(f"alındı: {ad} ({adet} adet, {fiyat} silver)")

                if self.var_insansi.get():
                    min_s = float(self.spin_min.get())
                    max_s = float(self.spin_max.get())
                    if max_s < min_s:
                        max_s = min_s + 0.5
                    bekleme = random.uniform(min_s, max_s)
                    
                    gecen = 0
                    while gecen < bekleme:
                        if self.durdurma.is_set():
                            break
                        time.sleep(0.05)
                        gecen += 0.05

                    sayac += 1
                    if self.var_mola.get() and sayac >= esik:
                        mola = random.uniform(2.5, 5.0)
                        self.yaz(f"kısa mola ({mola:.1f} sn)...")
                        gecen_mola = 0
                        while gecen_mola < mola:
                            if self.durdurma.is_set():
                                break
                            time.sleep(0.05)
                            gecen_mola += 0.05
                        sayac = 0
                        esik = random.randint(12, 22)
                else:
                    time.sleep(0.15)

            except Exception as e:
                self.yaz(f"hata: {e}")
                time.sleep(0.2)

        if self.aktif_sira >= toplam:
            self.yaz("tüm liste tamamlandı.")
            self.aktif_sira = 0
            self.durum_kaydet(0)
            
        self.pencere.after(0, self.durdur)

if __name__ == "__main__":
    pencere = tk.Tk()
    uygulama = PazarBotu(pencere)
    pencere.mainloop()
