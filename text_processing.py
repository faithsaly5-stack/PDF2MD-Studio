import re
import zipfile
import xml.etree.ElementTree as ET

def polish_persian_typography(text):
    zwnj = '\u200c'
    # Prefix "می " and "نمی "
    text = re.sub(r'\b(ن?می)\s+([آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]+)', rf'\1{zwnj}\2', text)
    # Suffix "ها" and "های"
    text = re.sub(r'([آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]+)\s+(ها|های|هایی|هایم|هایت|هایش|هایمان|هایتان|هایشان)\b', rf'\1{zwnj}\2', text)
    # Suffix "تر" and "ترین"
    text = re.sub(r'([آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]+)\s+(تر|ترین|تری)\b', rf'\1{zwnj}\2', text)
    # Suffix "ای"
    text = re.sub(r'([آابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی]+)\s+(ای|ام|ات|اش|مان|تان|شان)\b', rf'\1{zwnj}\2', text)
    # Clean double spaces
    text = re.sub(r'[ \t]{2,}', ' ', text)
    return text

def is_page_number_or_junk(text):
    clean = text.strip()
    if re.match(r'^[\d\u0660-\u0669\u06F0-\u06F9\s\.\,\-\/\_\:\(\)\*]{1,10}$', clean):
        return True
    if clean in ['AS', 'Y', 'ء', '...', '---', '•••', 'ه']:
        return True
    return False

def extract_docx_text_xml(docx_path, log_callback=None):
    ns = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'v': 'urn:schemas-microsoft-com:vml',
        'mc': 'http://schemas.openxmlformats.org/markup-compatibility/2006'
    }
    
    try:
        with zipfile.ZipFile(docx_path) as docx:
            if 'word/document.xml' not in docx.namelist():
                return ""
            xml_content = docx.read('word/document.xml')
    except Exception as e:
        if log_callback:
            log_callback(f"  Error reading DOCX: {e}")
        return ""

    root = ET.fromstring(xml_content)

    def extract_node_blocks(node):
        blocks = []
        for child in node:
            # Handle mc:AlternateContent (avoid duplicates)
            if child.tag == f"{{{ns['mc']}}}AlternateContent":
                choice = child.find(f"{{{ns['mc']}}}Choice")
                if choice is not None:
                    tb_text = extract_node_blocks(choice)
                    if tb_text: blocks.extend(tb_text)
                else:
                    fallback = child.find(f"{{{ns['mc']}}}Fallback")
                    if fallback is not None:
                        tb_text = extract_node_blocks(fallback)
                        if tb_text: blocks.extend(tb_text)
                continue

            if child.tag == f"{{{ns['w']}}}p":
                is_word_list = False
                pPr = child.find(f"{{{ns['w']}}}pPr")
                if pPr is not None and pPr.find(f"{{{ns['w']}}}numPr") is not None:
                    is_word_list = True

                runs = []
                nested_drawings = []
                
                for c in child.iter():
                    if c.tag == f"{{{ns['w']}}}r":
                        bold = False
                        italic = False
                        rPr = c.find(f"{{{ns['w']}}}rPr")
                        if rPr is not None:
                            b = rPr.find(f"{{{ns['w']}}}b")
                            if b is not None and b.get(f"{{{ns['w']}}}val", "1") not in ["0", "false"]:
                                bold = True
                            i = rPr.find(f"{{{ns['w']}}}i")
                            if i is not None and i.get(f"{{{ns['w']}}}val", "1") not in ["0", "false"]:
                                italic = True
                        
                        text = ""
                        for el in c.iter():
                            if el.tag == f"{{{ns['w']}}}t" and el.text:
                                text += el.text
                            elif el.tag == f"{{{ns['w']}}}br":
                                text += "\n"
                            elif el.tag == f"{{{ns['w']}}}tab":
                                text += "\t"
                        if text:
                            runs.append({'text': text, 'bold': bold, 'italic': italic})
                            
                    elif c.tag in [f"{{{ns['w']}}}txbxContent", f"{{{ns['v']}}}textbox", f"{{{ns['w']}}}drawing"]:
                        nb = extract_node_blocks(c)
                        if nb: nested_drawings.extend(nb)
                
                # Consolidate adjacent runs with same formatting
                consolidated = []
                for r in runs:
                    if consolidated and consolidated[-1]['bold'] == r['bold'] and consolidated[-1]['italic'] == r['italic']:
                        consolidated[-1]['text'] += r['text']
                    else:
                        consolidated.append(r)
                
                # Split runs by lines
                lines_of_runs = [[]]
                for r in consolidated:
                    parts = r['text'].split('\n')
                    for i, part in enumerate(parts):
                        if i > 0:
                            lines_of_runs.append([])
                        if part:
                            lines_of_runs[-1].append({'text': part, 'bold': r['bold'], 'italic': r['italic']})

                for line_runs in lines_of_runs:
                    if not line_runs:
                        continue
                    
                    full_raw_text = "".join(r['text'] for r in line_runs).strip()
                    if not full_raw_text:
                        continue

                    # Filter standalone junk / page numbers
                    if is_page_number_or_junk(full_raw_text):
                        continue

                    all_bold = len(line_runs) > 0 and all(r['bold'] or not r['text'].strip() for r in line_runs)
                    full_clean_text = polish_persian_typography(full_raw_text)

                    # Hierarchical Headings
                    if re.match(r'^(?:فصل\s*[\d\u0660-\u0669\u06F0-\u06F9IVXLCDMیکدووسهچهارپنجشششهفتهشتنهدهمییازدهمدوازدهم]+|فصل\s+[\d\u0660-\u0669\u06F0-\u06F9]+)', full_clean_text) and len(full_clean_text) < 80:
                        p_text = f"# {full_clean_text}"
                    elif re.match(r'^(?:گفتار\s*[\d\u0660-\u0669\u06F0-\u06F9یکدووسهچهارپنجشششهفتهشتنهدهمییازدهمدوازدهم\.\-]+)', full_clean_text) and len(full_clean_text) < 100:
                        p_text = f"## {full_clean_text}"
                    elif re.match(r'^(?:فعالیت\s*[\d\u0660-\u0669\u06F0-\u06F9]*|واژه\s*شناسی|بیشتر\s*بدانید|آیا\s*می\s*دانید|آیا\s*میدانید|کارگاه\s*|آزمایش\s*|پژوهش\s*)', full_clean_text) and len(full_clean_text) < 100:
                        p_text = f"### {full_clean_text}"
                    elif all_bold and len(full_clean_text) < 60 and not re.search(r'[\.\,\:\;\!\؟\?]\s*$', full_clean_text) and not full_clean_text.endswith((' و', ' یا', ' به', ' در', ' که', ' از', ' با', ' را', ' است', ' شد', ' شد.', ' است.')):
                        p_text = f"### {full_clean_text}"
                    elif re.match(r'^\(?(?:شکل|جدول|نمودار|تصویر)\s*[\d\u0660-\u0669\u06F0-\u06F9]+', full_clean_text):
                        p_text = f"*{full_clean_text}*"
                    elif re.match(r'^(?:[\-\*•●▪▫♦]\s*|[۰-۹\d]+[\-\.\)]\s*|[الف-ی]\s*[\-\)])', full_clean_text) or is_word_list:
                        cleaned_bullet = re.sub(r'^[•●▪▫♦]\s*', '- ', full_clean_text)
                        if is_word_list and not cleaned_bullet.startswith('- ') and not re.match(r'^[۰-۹\d]+[\.\)]', cleaned_bullet):
                            cleaned_bullet = f"- {cleaned_bullet}"
                        p_text = cleaned_bullet
                    else:
                        p_text = ""
                        for r in line_runs:
                            t = polish_persian_typography(r['text'])
                            t = t.replace('*', '\\*').replace('_', '\\_')
                            if t.strip():
                                ls = t[:len(t) - len(t.lstrip())]
                                rs = t[len(t.rstrip()):]
                                it = t.strip()
                                if r['bold'] and r['italic']: t = f"{ls}***{it}***{rs}"
                                elif r['bold']: t = f"{ls}**{it}**{rs}"
                                elif r['italic']: t = f"{ls}*{it}*{rs}"
                            p_text += t
                    
                    p_text = p_text.strip()
                    if p_text:
                        blocks.append(p_text)
                
                if nested_drawings:
                    blocks.extend(nested_drawings)
                    
            elif child.tag == f"{{{ns['w']}}}tbl":
                rows = []
                for tr in child.findall(f".//{{{ns['w']}}}tr"):
                    row_cells = []
                    for tc in tr.findall(f".//{{{ns['w']}}}tc"):
                        cell_text = "\n".join(extract_node_blocks(tc))
                        cell_text = re.sub(r'\s+', ' ', cell_text).strip()
                        cell_text = cell_text.replace('|', '\\|')
                        row_cells.append(cell_text)
                    if any(c.strip() for c in row_cells):
                        rows.append(row_cells)
                if rows:
                    col_count = max(len(r) for r in rows)
                    md_table = []
                    for i, r in enumerate(rows):
                        r += [""] * (col_count - len(r))
                        md_table.append("| " + " | ".join(r) + " |")
                        if i == 0:
                            md_table.append("|" + "|".join(["---"] * col_count) + "|")
                    blocks.append("\n".join(md_table))
                    
            elif child.tag in [f"{{{ns['w']}}}txbxContent", f"{{{ns['v']}}}textbox", f"{{{ns['w']}}}drawing"]:
                tb_text = extract_node_blocks(child)
                if tb_text:
                    blocks.extend(tb_text)
            else:
                tb_text = extract_node_blocks(child)
                if tb_text:
                    blocks.extend(tb_text)
        return blocks

    raw_blocks = extract_node_blocks(root)
    
    final_lines = []
    for i, b in enumerate(raw_blocks):
        b = b.strip()
        if not b: continue
        if b.startswith('#'):
            final_lines.append("\n" + b + "\n")
        elif b.startswith('- ') or re.match(r'^[۰-۹\d]+[\.\)]', b) or re.match(r'^[الف-ی]\s*[\-\)]', b):
            final_lines.append(b)
        elif b.startswith('*') and b.endswith('*'):
            final_lines.append(b)
        else:
            final_lines.append(b)

    result_md = ""
    for i, line in enumerate(final_lines):
        line = line.strip()
        if not line: continue
        if not result_md:
            result_md = line
            continue
            
        prev_line = final_lines[i-1].strip()
        if (line.startswith('-') or re.match(r'^[۰-۹\d]+[\.\)]', line) or re.match(r'^[الف-ی]\s*[\-\)]', line)) and \
           (prev_line.startswith('-') or re.match(r'^[۰-۹\d]+[\.\)]', prev_line) or re.match(r'^[الف-ی]\s*[\-\)]', prev_line)):
            result_md += "\n" + line
        elif line.startswith('#') or prev_line.startswith('#'):
            result_md += "\n\n" + line
        elif len(line) < 50 and len(prev_line) < 50 and not line.endswith('.') and not prev_line.endswith('.'):
            result_md += "\n" + line
        else:
            result_md += "\n\n" + line
            
    result_md = re.sub(r'\n{3,}', '\n\n', result_md).strip()
    return result_md
