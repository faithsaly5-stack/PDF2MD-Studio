import os
import gc
from PIL import Image
import io

Image.MAX_IMAGE_PIXELS = None
MAX_JPEG_HEIGHT = 64000

def flush_and_save_segment(images, out_dir, base_name, ext, save_format, part_num, total_expected_parts, log_callback=None):
    if not images:
        return False

    max_width = max(img.width for img in images)
    total_height = sum(img.height for img in images)

    if log_callback:
        log_callback(f"  Stitching {len(images)} pages into {max_width}x{total_height} px...")
    long_img = Image.new("RGB", (max_width, total_height), (255, 255, 255))

    current_y = 0
    for img in images:
        offset_x = (max_width - img.width) // 2
        long_img.paste(img, (offset_x, current_y))
        current_y += img.height

    suffix = f"_part{part_num}" if total_expected_parts > 1 else ""
    out_filename = f"{base_name}{suffix}.{ext}"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, out_filename)

    max_size = 1.95 * 1024 * 1024 # Target max size
    current_img = long_img
    scale_ratio = 1.0
    jpeg_quality = 85
    
    while True:
        buffer = io.BytesIO()
        if save_format == "JPEG":
            current_img.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
        else:
            current_img.save(buffer, format="PNG", optimize=True)
            
        size = buffer.tell()
        if size <= max_size or scale_ratio < 0.3:
            with open(out_path, "wb") as f:
                f.write(buffer.getvalue())
            break
            
        if log_callback:
            log_callback(f"    [!] Size {size/(1024*1024):.2f}MB exceeds 2MB limit. Downscaling...")
            
        if save_format == "JPEG" and jpeg_quality > 55:
            jpeg_quality -= 5
        else:
            scale_ratio *= 0.85
            new_w = max(1, int(max_width * scale_ratio))
            new_h = max(1, int(total_height * scale_ratio))
            current_img = long_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
    out_size_mb = os.path.getsize(out_path) / (1024 * 1024)
    if log_callback:
        log_callback(f"  ✅ Saved: '{out_filename}' ({out_size_mb:.2f} MB)")

    # Aggressive memory cleanup
    if current_img is not long_img:
        del current_img
    del long_img
    gc.collect()
    return True
