import os
import re
import pymupdf

class PDFFileItem:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.filesize = 0
        self.page_count = 0
        self.status = "Ready"  # Ready, Processing..., Completed, Error
        self.error_msg = ""
        self.output_files = []

        try:
            if os.path.exists(filepath):
                self.filesize = os.path.getsize(filepath)
            doc = pymupdf.open(filepath)
            self.page_count = len(doc)
            doc.close()
        except Exception as e:
            self.status = "Error"
            self.error_msg = str(e)

    def size_str(self):
        size_mb = self.filesize / (1024 * 1024)
        if size_mb < 1.0:
            return f"{self.filesize / 1024:.1f} KB"
        return f"{size_mb:.2f} MB"


class DocxGroupItem:
    def __init__(self, base_name):
        self.base_name = base_name
        self.filename = f"{base_name} (Group)"
        self.parts = []
        self.status = "Ready"
        self.error_msg = ""
    
    def add_part(self, filepath):
        if filepath not in self.parts:
            self.parts.append(filepath)
            self.parts.sort(key=self.natural_keys)

    @staticmethod
    def atoi(text):
        return int(text) if text.isdigit() else text

    @staticmethod
    def natural_keys(text):
        return [DocxGroupItem.atoi(c) for c in re.split(r'(\d+)', text)]

    def get_total_size(self):
        return sum(os.path.getsize(p) for p in self.parts if os.path.exists(p))

    def size_str(self):
        sz = self.get_total_size()
        size_mb = sz / (1024 * 1024)
        if size_mb < 1.0:
            return f"{sz / 1024:.1f} KB"
        return f"{size_mb:.2f} MB"
