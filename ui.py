import os
import sys
import glob
import time
import json
import gc
import threading
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import re
import zipfile
import xml.etree.ElementTree as ET
import pymupdf  # fitz
from PIL import Image

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
except ImportError:
    TkinterDnD = None
    DND_FILES = None

# Disable PIL decompression bomb check for long composite images
Image.MAX_IMAGE_PIXELS = None

from config_manager import ConfigManager
from models import PDFFileItem, DocxGroupItem
from text_processing import extract_docx_text_xml
from pdf_processing import flush_and_save_segment, MAX_JPEG_HEIGHT

# Create a DnD Wrapper class for CustomTkinter
class TkDnDApp(ctk.CTk, TkinterDnD.DnDWrapper if TkinterDnD else object):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if TkinterDnD:
            self.TkdndVersion = TkinterDnD._require(self)

class PDFLongImageApp(TkDnDApp):
    def __init__(self):
        super().__init__()

        # Load persisted config
        self.config = ConfigManager.load()
        self.theme_mode = self.config.get("theme", "Light")
        ctk.set_appearance_mode(self.theme_mode)
        ctk.set_default_color_theme("blue")

        # Window Configuration
        self.title("PDF & DOCX Conversion Studio")
        self.geometry("1080x720")
        self.minsize(940, 640)

        # State Variables
        self.queue = []
        self.is_converting = False
        self.cancel_requested = False
        self.custom_output_dir = self.config.get("custom_out_dir", "")
        self.last_output_dir = os.path.abspath(os.getcwd())

        # Palette colors (Light / Dark responsive tuples)
        self.c_bg_card = ("#FFFFFF", "#1E293B")
        self.c_border = ("#E2E8F0", "#334155")
        self.c_text_main = ("#0F172A", "#F8FAFC")
        self.c_text_sub = ("#64748B", "#94A3B8")
        self.c_accent = ("#4F46E5", "#6366F1")
        self.c_accent_hover = ("#4338CA", "#4F46E5")
        self.c_success = ("#10B981", "#059669")
        self.c_success_hover = ("#059669", "#047857")

        # Build UI layout
        self.setup_ui()
        self.load_preferences_to_ui()

        # Auto-discover local PDFs on launch
        self.auto_discover_local_pdfs()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # =================================================================
        # LEFT SIDEBAR - Clean, Intuitive Settings & Actions
        # =================================================================
        self.sidebar = ctk.CTkFrame(
            self,
            width=330,
            corner_radius=0,
            fg_color=("#F8FAFC", "#0F172A"),
            border_color=self.c_border,
            border_width=1
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)

        # App Brand Header
        self.header_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")

        self.brand_title = ctk.CTkLabel(
            self.header_frame,
            text="📄 PDF2MD Studio",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=self.c_text_main
        )
        self.brand_title.pack(anchor="w")

        self.brand_sub = ctk.CTkLabel(
            self.header_frame,
            text="Convert PDFs to images & clean DOCX text",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_sub
        )
        self.brand_sub.pack(anchor="w", pady=(2, 0))

        # Add Files / Import Section (Hero Buttons)
        self.import_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=self.c_bg_card,
            border_color=self.c_border,
            border_width=1,
            corner_radius=10
        )
        self.import_card.grid(row=1, column=0, padx=16, pady=(5, 12), sticky="ew")

        self.btn_add_files = ctk.CTkButton(
            self.import_card,
            text="➕  Add Files (PDF/DOCX)...",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=self.c_accent,
            hover_color=self.c_accent_hover,
            height=38,
            corner_radius=8,
            command=self.add_pdf_files
        )
        self.btn_add_files.pack(fill="x", padx=12, pady=(12, 6))

        self.btn_add_folder = ctk.CTkButton(
            self.import_card,
            text="📁  Add Folder (PDF/DOCX)...",
            font=ctk.CTkFont(size=12),
            fg_color=("#E2E8F0", "#334155"),
            hover_color=("#CBD5E1", "#475569"),
            text_color=self.c_text_main,
            height=32,
            corner_radius=8,
            command=self.add_pdf_folder
        )
        self.btn_add_folder.pack(fill="x", padx=12, pady=(0, 12))

        # Settings Card
        self.settings_card = ctk.CTkFrame(
            self.sidebar,
            fg_color=self.c_bg_card,
            border_color=self.c_border,
            border_width=1,
            corner_radius=10
        )
        self.settings_card.grid(row=2, column=0, padx=16, pady=0, sticky="nsew")

        # Section Title: Options
        self.lbl_settings = ctk.CTkLabel(
            self.settings_card,
            text="⚙️  Conversion Options",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=self.c_text_main
        )
        self.lbl_settings.pack(anchor="w", padx=14, pady=(12, 8))

        # 1. Page Splitting Option
        self.lbl_split = ctk.CTkLabel(
            self.settings_card,
            text="Pages per Image Segment:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.c_text_main
        )
        self.lbl_split.pack(anchor="w", padx=14, pady=(2, 2))

        # Quick preset buttons for split
        self.split_preset_frame = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        self.split_preset_frame.pack(fill="x", padx=14, pady=(0, 6))

        self.split_presets = ctk.CTkSegmentedButton(
            self.split_preset_frame,
            values=["10", "20 (Best)", "30", "No Split"],
            command=self.on_split_preset_selected,
            font=ctk.CTkFont(size=11),
            height=28
        )
        self.split_presets.pack(fill="x")

        # Custom Split Entry Row
        self.custom_split_frame = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        self.custom_split_frame.pack(fill="x", padx=14, pady=(0, 10))

        self.lbl_custom_split = ctk.CTkLabel(
            self.custom_split_frame,
            text="Custom page count:",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_sub
        )
        self.lbl_custom_split.pack(side="left")

        self.entry_split = ctk.CTkEntry(
            self.custom_split_frame,
            width=65,
            height=26,
            font=ctk.CTkFont(size=11),
            placeholder_text="20"
        )
        self.entry_split.pack(side="right")
        self.entry_split.bind("<KeyRelease>", lambda e: self.on_custom_split_typed())

        # 2. Rendering Quality
        self.lbl_quality = ctk.CTkLabel(
            self.settings_card,
            text="Image Resolution / Quality:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.c_text_main
        )
        self.lbl_quality.pack(anchor="w", padx=14, pady=(4, 2))

        self.quality_combo = ctk.CTkOptionMenu(
            self.settings_card,
            values=[
                "Ultra Sharp (1.75x - 168 DPI)",
                "High Quality (1.33x - 128 DPI)",
                "Balanced (1.15x - 110 DPI)",
                "Standard (1.0x - 96 DPI)"
            ],
            font=ctk.CTkFont(size=11),
            height=30,
            command=lambda v: self.save_preferences()
        )
        self.quality_combo.pack(fill="x", padx=14, pady=(0, 10))

        # 3. Output Format
        self.lbl_format = ctk.CTkLabel(
            self.settings_card,
            text="Output Format:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=self.c_text_main
        )
        self.lbl_format.pack(anchor="w", padx=14, pady=(4, 2))

        self.format_segmented = ctk.CTkSegmentedButton(
            self.settings_card,
            values=["JPG (Recommended)", "PNG (Lossless)"],
            font=ctk.CTkFont(size=11),
            height=28,
            command=lambda v: self.save_preferences()
        )
        self.format_segmented.pack(fill="x", padx=14, pady=(0, 12))

        # 4. Output Location & Automation
        self.switch_open_folder = ctk.CTkSwitch(
            self.settings_card,
            text="Auto-open folder when done",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_main,
            command=self.save_preferences
        )
        self.switch_open_folder.pack(anchor="w", padx=14, pady=4)

        self.switch_custom_out = ctk.CTkSwitch(
            self.settings_card,
            text="Save to custom folder",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_main,
            command=self.toggle_custom_output
        )
        self.switch_custom_out.pack(anchor="w", padx=14, pady=(4, 6))

        self.btn_select_out = ctk.CTkButton(
            self.settings_card,
            text="📁  Browse Output...",
            font=ctk.CTkFont(size=11),
            fg_color=("#E2E8F0", "#334155"),
            hover_color=("#CBD5E1", "#475569"),
            text_color=self.c_text_main,
            height=26,
            command=self.select_output_folder
        )
        self.btn_select_out.pack(fill="x", padx=14, pady=(0, 14))

        # Bottom Bar: Theme switcher & footer
        self.footer_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.footer_frame.grid(row=9, column=0, padx=16, pady=(10, 16), sticky="sew")

        self.lbl_theme = ctk.CTkLabel(
            self.footer_frame,
            text="Theme Mode:",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_sub
        )
        self.lbl_theme.pack(side="left", padx=(4, 8))

        self.theme_segmented = ctk.CTkSegmentedButton(
            self.footer_frame,
            values=["Light", "Dark", "System"],
            font=ctk.CTkFont(size=11),
            height=24,
            command=self.on_theme_changed
        )
        self.theme_segmented.pack(side="right", fill="x", expand=True)

        # =================================================================
        # RIGHT MAIN PANEL - Queue, Live Progress, Console, Action Bar
        # =================================================================
        self.main_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.main_panel.grid(row=0, column=1, sticky="nsew", padx=18, pady=18)
        self.main_panel.grid_rowconfigure(1, weight=1)
        self.main_panel.grid_columnconfigure(0, weight=1)

        # Top Bar of Main Area
        self.queue_bar = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.queue_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.queue_title = ctk.CTkLabel(
            self.queue_bar,
            text="Conversion Queue",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=self.c_text_main
        )
        self.queue_title.pack(side="left")

        self.badge_count = ctk.CTkLabel(
            self.queue_bar,
            text="0 files",
            fg_color=("#E2E8F0", "#334155"),
            text_color=self.c_text_main,
            corner_radius=12,
            font=ctk.CTkFont(size=11, weight="bold"),
            padx=10,
            pady=3
        )
        self.badge_count.pack(side="left", padx=10)

        self.btn_clear = ctk.CTkButton(
            self.queue_bar,
            text="🗑️ Clear Queue",
            font=ctk.CTkFont(size=11),
            fg_color=("#FEE2E2", "#7F1D1D"),
            hover_color=("#FECACA", "#991B1B"),
            text_color=("#B91C1C", "#FCA5A5"),
            height=28,
            width=90,
            corner_radius=6,
            command=self.clear_queue
        )
        self.btn_clear.pack(side="right", padx=(6, 0))

        self.btn_scan = ctk.CTkButton(
            self.queue_bar,
            text="🔄 Discover Local",
            font=ctk.CTkFont(size=11),
            fg_color=("#E2E8F0", "#334155"),
            hover_color=("#CBD5E1", "#475569"),
            text_color=self.c_text_main,
            height=28,
            width=110,
            corner_radius=6,
            command=self.auto_discover_local_pdfs
        )
        self.btn_scan.pack(side="right")

        # Tabview for 2-step workflow
        self.tabview = ctk.CTkTabview(self.main_panel, command=self.update_queue_ui)
        self.tabview.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
        
        self.tab_pdf = self.tabview.add("Step 1: PDF to Images")
        self.tab_docx = self.tabview.add("Step 2: DOCX to Markdown")
        
        # Setup Tab 1 (PDF)
        self.tab_pdf.grid_columnconfigure(0, weight=1)
        self.tab_pdf.grid_rowconfigure(1, weight=1)
        lbl_inst_pdf = ctk.CTkLabel(
            self.tab_pdf, 
            text="Step 1: Convert your PDF into high-quality images. Add PDF files here.",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text_main
        )
        lbl_inst_pdf.grid(row=0, column=0, pady=(0, 10))
        self.scroll_queue_pdf = ctk.CTkScrollableFrame(
            self.tab_pdf, fg_color=self.c_bg_card, border_color=self.c_border,
            border_width=1, corner_radius=10
        )
        self.scroll_queue_pdf.grid(row=1, column=0, sticky="nsew")
        self.scroll_queue_pdf.grid_columnconfigure(0, weight=1)

        # Setup Tab 2 (DOCX)
        self.tab_docx.grid_columnconfigure(0, weight=1)
        self.tab_docx.grid_rowconfigure(1, weight=1)
        lbl_inst_docx = ctk.CTkLabel(
            self.tab_docx, 
            text="Step 2: Clean Google Docs OCR files into Markdown. Add DOCX files here.",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=self.c_text_main
        )
        lbl_inst_docx.grid(row=0, column=0, pady=(0, 10))
        self.scroll_queue_docx = ctk.CTkScrollableFrame(
            self.tab_docx, fg_color=self.c_bg_card, border_color=self.c_border,
            border_width=1, corner_radius=10
        )
        self.scroll_queue_docx.grid(row=1, column=0, sticky="nsew")
        self.scroll_queue_docx.grid_columnconfigure(0, weight=1)

        # Drag and Drop Zone (Empty State)
        self.drop_zone_frame = ctk.CTkFrame(
            self.main_panel, 
            fg_color="transparent", 
            border_color=self.c_accent[0], 
            border_width=2, 
            corner_radius=15
        )
        # Configure a dashed-like or distinct look via colors
        
        self.lbl_drop = ctk.CTkLabel(
            self.drop_zone_frame,
            text="📥\n\nDrag & Drop PDF or DOCX files here",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=self.c_text_sub
        )
        self.lbl_drop.place(relx=0.5, rely=0.5, anchor="center")

        if TkinterDnD:
            self.drop_target_register(DND_FILES)
            self.dnd_bind('<<Drop>>', self.on_drop_files)

        # Progress Card
        self.progress_panel = ctk.CTkFrame(
            self.main_panel,
            fg_color=self.c_bg_card,
            border_color=self.c_border,
            border_width=1,
            corner_radius=10
        )
        self.progress_panel.grid(row=2, column=0, sticky="ew", pady=(0, 10))
        self.progress_panel.grid_columnconfigure(1, weight=1)

        self.lbl_progress_title = ctk.CTkLabel(
            self.progress_panel,
            text="Overall Progress:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=self.c_text_main
        )
        self.lbl_progress_title.grid(row=0, column=0, padx=(16, 12), pady=(12, 4), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_panel,
            height=12,
            corner_radius=6,
            progress_color=self.c_success[0]
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, padx=(0, 16), pady=(12, 4), sticky="ew")

        self.lbl_status_detail = ctk.CTkLabel(
            self.progress_panel,
            text="Ready • Add PDF documents and click 'Start Conversion'",
            font=ctk.CTkFont(size=11),
            text_color=self.c_text_sub
        )
        self.lbl_status_detail.grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w")

        # Activity Log (Collapsible Console)
        self.log_box = ctk.CTkTextbox(
            self.main_panel,
            height=95,
            font=ctk.CTkFont(family="Consolas", size=10),
            fg_color=("#F8FAFC", "#0B0F19"),
            text_color=("#1E293B", "#E2E8F0"),
            border_color=self.c_border,
            border_width=1,
            corner_radius=8
        )
        self.log_box.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        self.log("⚡ PDF Long Image Studio initialized. Ready.")

        # Bottom Master Action Bar
        self.bottom_bar = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self.bottom_bar.grid(row=4, column=0, sticky="ew")

        self.btn_start = ctk.CTkButton(
            self.bottom_bar,
            text="🚀  Start Conversion",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color=self.c_success,
            hover_color=self.c_success_hover,
            height=46,
            corner_radius=10,
            command=self.start_conversion_thread
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            self.bottom_bar,
            text="⏹️  Cancel",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#EF4444", "#DC2626"),
            hover_color=("#DC2626", "#B91C1C"),
            height=46,
            width=100,
            corner_radius=10,
            command=self.request_cancel,
            state="disabled"
        )
        self.btn_cancel.pack(side="left", padx=(0, 10))

        self.btn_open_out = ctk.CTkButton(
            self.bottom_bar,
            text="📂  Open Output Folder",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=("#E2E8F0", "#334155"),
            hover_color=("#CBD5E1", "#475569"),
            text_color=self.c_text_main,
            height=46,
            corner_radius=10,
            command=self.open_output_folder
        )
        self.btn_open_out.pack(side="left")

    # =================================================================
    # PREFERENCE / SETTING SYNCING
    # =================================================================
    def load_preferences_to_ui(self):
        theme = self.config.get("theme", "Light")
        self.theme_segmented.set(theme)

        chunk_val = str(self.config.get("chunk_size", "20"))
        self.entry_split.delete(0, "end")
        self.entry_split.insert(0, chunk_val)

        if chunk_val in ["10", "20", "30"]:
            self.split_presets.set(f"{chunk_val} (Best)" if chunk_val == "20" else chunk_val)
        elif chunk_val == "0":
            self.split_presets.set("No Split")
        else:
            self.split_presets.set("")

        self.quality_combo.set(self.config.get("quality", "Balanced (1.15x - 110 DPI)"))
        self.format_segmented.set(self.config.get("format", "JPG (Recommended)"))

        if self.config.get("auto_open", True):
            self.switch_open_folder.select()
        else:
            self.switch_open_folder.deselect()

        if self.config.get("use_custom_out", False):
            self.switch_custom_out.select()
            self.btn_select_out.configure(state="normal")
            if self.custom_output_dir:
                self.btn_select_out.configure(text=f"📁 {os.path.basename(self.custom_output_dir)[:15]}...")
        else:
            self.switch_custom_out.deselect()
            self.btn_select_out.configure(state="disabled")

    def save_preferences(self):
        self.config["theme"] = self.theme_segmented.get()
        self.config["chunk_size"] = self.entry_split.get().strip()
        self.config["quality"] = self.quality_combo.get()
        self.config["format"] = self.format_segmented.get()
        self.config["auto_open"] = bool(self.switch_open_folder.get())
        self.config["use_custom_out"] = bool(self.switch_custom_out.get())
        self.config["custom_out_dir"] = self.custom_output_dir or ""
        ConfigManager.save(self.config)

    def on_theme_changed(self, mode):
        ctk.set_appearance_mode(mode)
        self.save_preferences()

    def on_split_preset_selected(self, value):
        if "10" in value:
            self.entry_split.delete(0, "end")
            self.entry_split.insert(0, "10")
        elif "20" in value:
            self.entry_split.delete(0, "end")
            self.entry_split.insert(0, "20")
        elif "30" in value:
            self.entry_split.delete(0, "end")
            self.entry_split.insert(0, "30")
        elif "No Split" in value:
            self.entry_split.delete(0, "end")
            self.entry_split.insert(0, "0")

        self.update_queue_ui()
        self.save_preferences()

    def on_custom_split_typed(self):
        val = self.entry_split.get().strip()
        if val == "10":
            self.split_presets.set("10")
        elif val == "20":
            self.split_presets.set("20 (Best)")
        elif val == "30":
            self.split_presets.set("30")
        elif val == "0":
            self.split_presets.set("No Split")
        else:
            self.split_presets.set("")
        self.update_queue_ui()
        self.save_preferences()

    def get_chunk_size(self):
        val = self.entry_split.get().strip()
        if not val or val == "0" or val.lower() == "no split":
            return 0
        try:
            return max(1, int(val))
        except ValueError:
            return 20

    def get_scale_factor(self):
        val = self.quality_combo.get()
        if "1.75x" in val:
            return 1.75
        elif "1.33x" in val:
            return 1.33333333
        elif "1.15x" in val:
            return 1.15
        elif "1.0x" in val:
            return 1.0
        return 1.15

    def toggle_custom_output(self):
        if self.switch_custom_out.get():
            self.btn_select_out.configure(state="normal")
            if not self.custom_output_dir:
                self.select_output_folder()
        else:
            self.btn_select_out.configure(state="disabled")
        self.save_preferences()

    def select_output_folder(self):
        chosen = filedialog.askdirectory(title="Select Custom Output Directory")
        if chosen:
            self.custom_output_dir = chosen
            self.btn_select_out.configure(text=f"📁 {os.path.basename(chosen)[:15]}...")
            self.save_preferences()

    def open_output_folder(self):
        target = self.custom_output_dir if (self.switch_custom_out.get() and self.custom_output_dir) else self.last_output_dir
        if os.path.exists(target):
            if sys.platform == "win32":
                os.startfile(target)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])

    # =================================================================
    # LOGGING & QUEUE UI
    # =================================================================
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{timestamp}] {message}\n")
        self.log_box.see("end")

    def update_queue_ui(self):
        if not hasattr(self, 'tabview'): return
        
        if len(self.queue) == 0:
            if hasattr(self, 'tabview'): self.tabview.grid_remove()
            if hasattr(self, 'drop_zone_frame'): self.drop_zone_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
            self.badge_count.configure(text="0 files")
            return
        else:
            if hasattr(self, 'drop_zone_frame'): self.drop_zone_frame.grid_remove()
            if hasattr(self, 'tabview'): self.tabview.grid(row=1, column=0, sticky="nsew", pady=(0, 12))
            
        active_tab = self.tabview.get()
        target_scroll = self.scroll_queue_pdf if "Step 1" in active_tab else self.scroll_queue_docx
        is_pdf_tab = "Step 1" in active_tab
        
        for widget in self.scroll_queue_pdf.winfo_children(): widget.destroy()
        for widget in self.scroll_queue_docx.winfo_children(): widget.destroy()

        visible_items = [item for item in self.queue if (isinstance(item, PDFFileItem) if is_pdf_tab else isinstance(item, DocxGroupItem))]
        self.badge_count.configure(text=f"{len(visible_items)} files in Step")

        if not visible_items:
            empty_lbl = ctk.CTkLabel(
                target_scroll,
                text="No files queued for this step.\nDrop files here or click 'Add Files'.",
                font=ctk.CTkFont(size=13), text_color=self.c_text_sub
            )
            empty_lbl.pack(pady=45)
            return

        chunk_setting = self.get_chunk_size()

        for idx, item in enumerate(self.queue):
            if (isinstance(item, PDFFileItem) and not is_pdf_tab) or (isinstance(item, DocxGroupItem) and is_pdf_tab):
                continue
            card = ctk.CTkFrame(
                target_scroll,
                fg_color=("#F8FAFC", "#0F172A"),
                border_color=self.c_border,
                border_width=1,
                corner_radius=8
            )
            card.pack(fill="x", padx=4, pady=4)
            card.grid_columnconfigure(1, weight=1)

            # Red PDF Icon
            icon_lbl = ctk.CTkLabel(card, text="📕", font=ctk.CTkFont(size=18))
            icon_lbl.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=8)

            # Title
            title_lbl = ctk.CTkLabel(
                card,
                text=item.filename,
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=self.c_text_main,
                anchor="w"
            )
            title_lbl.grid(row=0, column=1, sticky="w", pady=(6, 0))

            if isinstance(item, PDFFileItem):
                icon_lbl.configure(text="📕")
                if item.page_count > 0:
                    if chunk_setting == 0:
                        segments_str = "1 Continuous Image"
                    else:
                        total_chunks = (item.page_count + chunk_setting - 1) // chunk_setting
                        segments_str = f"{total_chunks} Part(s)"
                    sub_text = f"PDF • {item.page_count} Pages • {item.size_str()} • Out: {segments_str}"
                else:
                    sub_text = f"Error: {item.error_msg}"
            else:
                icon_lbl.configure(text="📝")
                sub_text = f"DOCX Group • {len(item.parts)} part(s) • {item.size_str()} • Out: {item.base_name}.md"

            info_lbl = ctk.CTkLabel(
                card,
                text=sub_text,
                font=ctk.CTkFont(size=11),
                text_color=self.c_text_sub,
                anchor="w"
            )
            info_lbl.grid(row=1, column=1, sticky="w", pady=(0, 6))

            # Status Badge with light/dark adaptive pills
            status_styles = {
                "Ready": (("#E2E8F0", "#334155"), ("#475569", "#E2E8F0")),
                "Processing...": (("#DBEAFE", "#1E3A8A"), ("#1D4ED8", "#93C5FD")),
                "Completed": (("#D1FAE5", "#064E3B"), ("#047857", "#6EE7B7")),
                "Error": (("#FEE2E2", "#7F1D1D"), ("#B91C1C", "#FCA5A5"))
            }
            bg_c, fg_c = status_styles.get(item.status, (("#E2E8F0", "#334155"), ("#475569", "#E2E8F0")))

            status_badge = ctk.CTkLabel(
                card,
                text=item.status,
                fg_color=bg_c,
                text_color=fg_c,
                corner_radius=6,
                font=ctk.CTkFont(size=11, weight="bold"),
                padx=9,
                pady=2
            )
            status_badge.grid(row=0, column=2, rowspan=2, padx=10, pady=8)

            # Individual remove button
            if not self.is_converting:
                btn_del = ctk.CTkButton(
                    card,
                    text="✕",
                    width=26,
                    height=26,
                    fg_color=("#E2E8F0", "#334155"),
                    hover_color=("#FEE2E2", "#7F1D1D"),
                    text_color=self.c_text_main,
                    corner_radius=6,
                    command=lambda i=idx: self.remove_queue_item(i)
                )
                btn_del.grid(row=0, column=3, rowspan=2, padx=(0, 10), pady=8)

    # =================================================================
    # FILE ACTIONS
    # =================================================================
    def _add_paths_to_queue(self, paths):
        import zipfile
        import tempfile
        added = 0
        for p in paths:
            abs_p = os.path.abspath(p)
            ext = os.path.splitext(abs_p)[1].lower()
            if ext == ".zip":
                try:
                    temp_dir = tempfile.mkdtemp(prefix="pdf_long_img_")
                    with zipfile.ZipFile(abs_p, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    extracted_paths = []
                    for root, dirs, files in os.walk(temp_dir):
                        for f in files:
                            extracted_paths.append(os.path.join(root, f))
                    self._add_paths_to_queue(extracted_paths)
                except Exception as e:
                    self.log(f"Error extracting ZIP: {e}")
            elif ext == ".pdf":
                if not any(isinstance(i, PDFFileItem) and i.filepath == abs_p for i in self.queue):
                    self.queue.append(PDFFileItem(abs_p))
                    added += 1
            elif ext == ".docx":
                filename = os.path.basename(abs_p)
                base_name = re.sub(r'[_ \-]*part\s*\d+$', '', os.path.splitext(filename)[0], flags=re.IGNORECASE).strip()
                
                existing_group = next((i for i in self.queue if isinstance(i, DocxGroupItem) and i.base_name == base_name), None)
                if not existing_group:
                    existing_group = DocxGroupItem(base_name)
                    self.queue.append(existing_group)
                
                if abs_p not in existing_group.parts:
                    existing_group.add_part(abs_p)
                    added += 1
        if added > 0:
            self.update_queue_ui()
            self.log(f"Added/Updated {added} file(s) in queue.")

    def add_pdf_files(self):
        paths = filedialog.askopenfilenames(
            title="Select PDF/DOCX/ZIP Documents",
            filetypes=[("Supported Files", "*.pdf *.docx *.zip")]
        )
        if paths:
            self._add_paths_to_queue(paths)

    def add_pdf_folder(self):
        folder = filedialog.askdirectory(title="Select Folder")
        if folder:
            paths = glob.glob(os.path.join(folder, "*.pdf")) + glob.glob(os.path.join(folder, "*.docx"))
            self._add_paths_to_queue(paths)

    def auto_discover_local_pdfs(self):
        paths = glob.glob("*.pdf") + glob.glob("*.docx")
        self._add_paths_to_queue(paths)

    def on_drop_files(self, event):
        files = self.tk.splitlist(event.data)
        paths = []
        for f in files:
            if os.path.isdir(f):
                paths.extend(glob.glob(os.path.join(f, "*.pdf")) + glob.glob(os.path.join(f, "*.docx")))
            else:
                if f.lower().endswith('.pdf') or f.lower().endswith('.docx') or f.lower().endswith('.zip'):
                    paths.append(f)
        self._add_paths_to_queue(paths)

    def remove_queue_item(self, index):
        if 0 <= index < len(self.queue):
            removed = self.queue.pop(index)
            self.log(f"Removed '{removed.filename}'.")
            self.update_queue_ui()

    def clear_queue(self):
        if self.is_converting:
            messagebox.showwarning("Busy", "Cannot clear queue while conversion is running.")
            return
        self.queue.clear()
        self.update_queue_ui()
        self.log("Queue cleared.")

    # =================================================================
    # THREAD-SAFE CONVERSION PIPELINE
    # =================================================================
    def start_conversion_thread(self):
        active_tab = self.tabview.get()
        is_pdf_batch = "Step 1" in active_tab
        items_to_process = [item for item in self.queue if (isinstance(item, PDFFileItem) if is_pdf_batch else isinstance(item, DocxGroupItem))]
        if not items_to_process:
            messagebox.showinfo("Queue Empty", "Please add at least one file to convert for this step.")
            return
        if self.is_converting:
            return

        self.save_preferences()
        self.is_converting = True
        self.cancel_requested = False

        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.btn_add_files.configure(state="disabled")
        self.btn_add_folder.configure(state="disabled")
        self.btn_clear.configure(state="disabled")

        threading.Thread(target=self.run_conversion_worker, daemon=True).start()

    def request_cancel(self):
        if self.is_converting:
            self.cancel_requested = True
            self.log("⚠️ Cancellation requested. Finishing current step...")
            self.btn_cancel.configure(state="disabled")


    def run_conversion_worker(self):
        active_tab = self.tabview.get()
        is_pdf_batch = "Step 1" in active_tab
        items_to_process = [item for item in self.queue if (isinstance(item, PDFFileItem) if is_pdf_batch else isinstance(item, DocxGroupItem))]
        
        total_files = len(items_to_process)
        if total_files == 0: return

        chunk_setting = self.get_chunk_size()
        scale = self.get_scale_factor()
        is_png = "PNG" in self.format_segmented.get()
        ext = "png" if is_png else "jpg"
        save_format = "PNG" if is_png else "JPEG"

        self.log(f"\n=======================================================")
        self.log(f"🚀 {'PDF' if is_pdf_batch else 'DOCX'} BATCH CONVERSION STARTED ({total_files} file(s))")
        self.log(f"=======================================================")

        start_time = time.time()
        completed_count = 0

        for proc_idx, item in enumerate(items_to_process):
            if self.cancel_requested:
                break

            if item.status == "Completed":
                continue

            item.status = "Processing..."
            self.after(0, self.update_queue_ui)
            self.after(0, lambda p=proc_idx, n=item.filename: self.lbl_status_detail.configure(
                text=f"Processing [{p+1}/{total_files}]: {n}"
            ))
            self.after(0, lambda p=proc_idx: self.progress_bar.set(p / total_files))

            try:
                if isinstance(item, PDFFileItem):
                    out_dir = self.custom_output_dir if (self.switch_custom_out.get() and self.custom_output_dir) else os.path.dirname(os.path.abspath(item.filepath))
                    os.makedirs(out_dir, exist_ok=True)
                    self.last_output_dir = out_dir
                    base_name = os.path.splitext(item.filename)[0]
                    doc = pymupdf.open(item.filepath)
                    total_pages = len(doc)
                    matrix = pymupdf.Matrix(scale, scale)

                    step = chunk_setting if chunk_setting > 0 else total_pages
                    est_parts = (total_pages + step - 1) // step

                    item.output_files = []
                    current_images = []
                    current_height = 0
                    part_num = 1
                    pages_in_chunk = 0

                    for p_num in range(total_pages):
                        if self.cancel_requested: break
                        page = doc.load_page(p_num)
                        pix = page.get_pixmap(matrix=matrix, alpha=False)
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                        if (save_format == "JPEG" and current_height + img.height > MAX_JPEG_HEIGHT) or \
                           (chunk_setting > 0 and pages_in_chunk >= chunk_setting):
                            self.log(f"[{item.filename}] Saving Part {part_num}...")
                            flush_and_save_segment(current_images, out_dir, base_name, ext, save_format, part_num, est_parts, log_callback=self.log)
                            current_images.clear(); current_height = 0; pages_in_chunk = 0; part_num += 1

                        current_images.append(img)
                        current_height += img.height
                        pages_in_chunk += 1

                    if current_images and not self.cancel_requested:
                        self.log(f"[{item.filename}] Saving Final Part {part_num}...")
                        flush_and_save_segment(current_images, out_dir, base_name, ext, save_format, part_num, est_parts, log_callback=self.log)
                        current_images.clear()

                    doc.close()
                    gc.collect()

                elif isinstance(item, DocxGroupItem):
                    if not item.parts:
                        continue
                    out_dir = self.custom_output_dir if (self.switch_custom_out.get() and self.custom_output_dir) else os.path.dirname(os.path.abspath(item.parts[0]))
                    os.makedirs(out_dir, exist_ok=True)
                    self.last_output_dir = out_dir
                    
                    md_text = ""
                    for part_path in item.parts:
                        self.log(f"  Parsing '{os.path.basename(part_path)}'...")
                        md = extract_docx_text_xml(part_path, log_callback=self.log)
                        if md:
                            md_text += md + "\n\n"
                        
                    out_path = os.path.join(out_dir, f"{item.base_name}.md")
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(md_text.strip())
                    
                    self.log(f"  ✅ Saved local markdown to: {item.base_name}.md")

                if not self.cancel_requested:
                    item.status = "Completed"
                    completed_count += 1
                else:
                    item.status = "Ready"

            except Exception as exc:
                item.status = "Error"
                item.error_msg = str(exc)
                self.log(f"❌ Error with '{item.filename}': {exc}")

            self.after(0, self.update_queue_ui)
            self.after(0, lambda p=proc_idx: self.progress_bar.set((p + 1) / total_files))

        elapsed = time.time() - start_time
        self.is_converting = False

        self.after(0, lambda: self.progress_bar.set(1.0))
        self.after(0, lambda: self.lbl_status_detail.configure(
            text=f"Batch complete: {completed_count}/{total_files} converted in {elapsed:.1f}s"
        ))
        self.after(0, lambda: self.btn_start.configure(state="normal"))
        self.after(0, lambda: self.btn_cancel.configure(state="disabled"))
        self.after(0, lambda: self.btn_add_files.configure(state="normal"))
        self.after(0, lambda: self.btn_add_folder.configure(state="normal"))
        self.after(0, lambda: self.btn_clear.configure(state="normal"))

        self.log(f"\n🎉 Conversion completed in {elapsed:.1f} seconds.")

        if not self.cancel_requested and completed_count > 0:
            if self.switch_open_folder.get():
                self.after(0, self.open_output_folder)
            target_desc = "PDF document(s) into long images" if is_pdf_batch else "DOCX document(s) into Markdown"
            self.after(0, lambda: messagebox.showinfo(
                "Conversion Finished",
                f"Successfully converted {completed_count} {target_desc}!"
            ))
            
            def clear_completed():
                self.queue = [item for item in self.queue if item.status != "Completed"]
                self.update_queue_ui()
                
            self.after(0, clear_completed)


if __name__ == "__main__":
    app = PDFLongImageApp()
    app.mainloop()
