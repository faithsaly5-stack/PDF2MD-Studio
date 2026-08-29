<div align="center">

# 📄 PDF2MD Studio
### 🚀 Unified Document Transformation Suite: PDF to High-Res Long Images & Clean Markdown from OCR

[![Farsi README](https://img.shields.io/badge/Language-Persian%20%2F%20%D9%81%D8%A7%D8%B1%D8%B3%DB%8C-emerald?style=for-the-badge&logo=translate&logoColor=white)](README.md)
[![English README](https://img.shields.io/badge/Language-English-blue?style=for-the-badge&logo=google-translate&logoColor=white)](README_en.md)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.9+" />
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-1f538d?style=for-the-badge&logo=pypi&logoColor=white" alt="CustomTkinter" />
  <img src="https://img.shields.io/badge/Engine-PyMuPDF-FF6F00?style=for-the-badge&logo=adobeacrobatreader&logoColor=white" alt="PyMuPDF" />
  <img src="https://img.shields.io/badge/DND-Drag%20%26%20Drop-6366F1?style=for-the-badge&logo=windows&logoColor=white" alt="Drag and Drop" />
  <img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" alt="License MIT" />
</p>

---

</div>

## 🌟 Overview

**PDF2MD Studio** is a unified, high-performance desktop application designed to solve two major digital document challenges:

1. **Stitching multi-page PDFs into continuous high-resolution long images** while strictly keeping file sizes under **2MB** without sacrificing text sharpness or resolution.
2. **Transforming messy DOCX files (from OCR tools or Google Docs) into immaculate Markdown**, with full native XML parsing, line-by-line validation, and automated Persian typography formatting (including ZWNJ / نیم‌فاصله).

Built with a sleek **CustomTkinter** interface, native **Drag & Drop** support, and responsive Dark/Light themes, PDF2MD Studio handles complex processing smoothly in background worker threads.

---

## ⚡ Key Features

### 🖼️ Step 1: PDF to Long Image Stitcher
* **Vertical Page Stitching:** Combines multi-page PDFs into vertically aligned, high-resolution continuous scrolls.
* **Smart Adaptive Compression:** Quality-first compression algorithm. Rather than physically downsampling image dimensions (which blurs text), it gradually optimizes JPEG encoding parameters and leverages Pillow internal compression to guarantee images stay under **2MB** with razor-sharp readability.
* **Segment / Page Chunking:** Easily configure chunk sizes (e.g., split long documents into 10, 20, or 30-page parts).
* **Multiple Quality Presets:** Standard (1.0x - 96 DPI), Balanced (1.15x - 110 DPI), High Quality (1.33x - 128 DPI), and Ultra Sharp (1.75x - 168 DPI).
* **Format Flexibility:** Export directly to JPG or lossless PNG.

### 📝 Step 2: OCR / DOCX to Clean Markdown Engine
* **Native WordprocessingML XML Parser:** Deep parsing directly from `word/document.xml` with zero reliance on cloud APIs or heavy third-party wrappers.
* **Soft Break & Tab Support (`<w:br>` and `<w:tab>`):** Accurately splits and parses multi-line OCR paragraphs line-by-line, preventing merged headings or clobbered lines.
* **Intelligent Hierarchy & Structure Detection:**
  - Automatically identifies main chapters (`# فصل`) and sub-sections (`## گفتار`, `### فعالیت`).
  - Converts bullet points (`-`) and nested numbered lists.
  - Extracts tables (`w:tbl`), text boxes, and drawings without data loss.
  - Preserves **Bold** and *Italic* text spans cleanly.
* **Persian Typography & ZWNJ Polisher:**
  - Auto-normalizes Zero-Width Non-Joiners (نیم‌فاصله) for prefixes and suffixes (e.g., «می‌شود», «یاخته‌ها»).
  - Standardizes Arabic characters (ي/ك) to native Persian glyphs.
  - Fixes punctuation spacing rules.

### 🖱️ Modern User Experience (UX/UI)
* **Universal Drag & Drop:** Drop individual `.pdf`, `.docx`, `.zip` files or entire directories directly into the app window.
* **Intuitive Empty State:** Clean drop-zone overlay when the queue is empty, automatically transitioning into the queue manager.
* **Multi-threaded Background Workers:** The interface stays 100% responsive during intensive rendering and extraction tasks.
* **Live Console & Progress Bar:** Real-time feedback showing file sizes, processed parts, and detailed logs.

---

## 📊 Comparison Matrix

| Feature | Conventional Online Tools | PDF2MD Studio |
| :--- | :---: | :---: |
| **Zoomed Text Sharpness** | ❌ Often blurry due to downscaling | ✅ Sharp & readable with adaptive DPI retention |
| **Strict 2MB Size Limit** | ❌ Exceeds size or destroys quality | ✅ Guaranteed < 2MB via smart compression |
| **OCR Multi-line Handling** | ❌ Merges lines & loses headings | ✅ Line-by-line XML parsing with soft-break support |
| **Persian Typography & ZWNJ** | ❌ Disorganized with broken characters | ✅ Full automatic normalization & polishing |
| **Privacy & Offline Security** | ❌ Uploads documents to cloud servers | ✅ 100% Offline, Local & Private |
| **Drag & Drop Workflow** | ⚠️ Limited | ✅ Full file, multi-selection & folder support |

---

## 🏗️ Architecture Pipeline

```mermaid
flowchart TD
    A[Input: PDF or DOCX Files] --> B{Drag & Drop or File Picker}
    B --> C[Multi-Threaded Queue Manager]
    
    subgraph Pipeline 1: PDF to Long Image
        C -->|PDF| D[PyMuPDF: Render Pages at Target Scale]
        D --> E[Stitch Pages Vertically]
        E --> F{Check Segment File Size}
        F -->|> 1.95 MB| G[Smart JPEG Quality Decay & Pillow Optimization]
        G --> F
        F -->|<= 1.95 MB| H[Save Output Image with Part Suffix]
    end
    
    subgraph Pipeline 2: DOCX to Markdown
        C -->|DOCX| I[Extract word/document.xml]
        I --> J[Parse w:p, w:r, w:br, w:tbl Nodes Line-by-Line]
        J --> K[Detect Hierarchy, Headings & Lists]
        K --> L[Persian Typography & ZWNJ Polishing]
        L --> M[Export Clean UTF-8 Markdown File]
    end
```

---

## 💻 Installation & Quick Start

### 1. Prerequisites
Ensure **Python 3.9+** is installed and accessible from your system PATH.

### 2. Clone & Setup Repository

```bash
# Clone the repository
git clone https://github.com/your-username/pdf2md-studio.git
cd pdf2md-studio

# Create & activate a virtual environment (optional but recommended)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run the Application

* **Option A (Recommended for Windows):** Double-click `run_app.bat`
* **Option B (Terminal):**
  ```bash
  python pdf_to_long_img_app.py
  ```
  or
  ```bash
  python ui.py
  ```

---

## 📂 Project Structure

```plaintext
├── config_manager.py        # Settings management & JSON preference storage
├── models.py                # Data classes for PDF & DOCX queue items
├── pdf_processing.py        # PDF rendering, stitching & adaptive compression engine
├── text_processing.py       # XML parsing, markdown extraction & typography polisher
├── ui.py                    # CustomTkinter GUI & Drag-and-Drop implementation
├── pdf_to_long_img_app.py   # Main application entry point
├── publish.py               # 1-Click safe GitHub publisher & release archiver
├── publish_github.bat       # Quick batch launcher for publishing
├── run_app.bat              # Silent background app launcher
├── requirements.txt         # Project dependencies
├── README.md                # Persian documentation (Default)
└── README_en.md             # English documentation
```

---

## 🚀 1-Click GitHub Publisher

For developers, running `publish_github.bat` executes the automated publisher:
1. Validates Git repository configuration and origin remote.
2. Safely excludes test assets (e.g. `biology/` folder) and local credentials.
3. Automatically commits with a custom or timestamped message and pushes to your active branch.
4. Generates a clean release archive (`PDF2MD_Studio_Release.zip`) ready for distribution.

---

> [!TIP]
> **Pro Tip:** For maximum clarity on textbook scans and fine print, set the resolution to **Ultra Sharp (1.75x)** in the sidebar. PDF2MD Studio will automatically optimize the image compression behind the scenes to keep the output under 2MB.

> [!NOTE]
> This application runs 100% locally on pure Python with no external AI or cloud API dependencies.

---

## 📜 License

This project is licensed under the **MIT License**. See the `LICENSE` file for more details.
