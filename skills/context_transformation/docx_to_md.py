import zipfile
import xml.etree.ElementTree as ET
import os
import argparse
import re
import shutil
import base64
import quopri

def handle_alt_chunk(docx, doc_path, abs_assets_dir, assets_dir_rel_to_md):
    """
    处理 DOCX 中的 altChunk (通常是 MHT 格式)。
    """
    # 1. 查找关系
    rels_xml_path = 'word/_rels/document.xml.rels'
    rels_content = docx.read(rels_xml_path)
    rels_root = ET.fromstring(rels_content)
    namespaces = {'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
    
    mht_target = None
    for rel in rels_root.findall('rel:Relationship', namespaces):
        if 'aFChunk' in rel.attrib['Type']:
            mht_target = rel.attrib['Target']
            break
            
    if not mht_target:
        return None

    # 2. 读取并解析 MHT
    try:
        mht_content = docx.read(f'word/{mht_target}').decode('utf-8', errors='ignore')
    except Exception:
        return None

    # 简单的 MHT 解析逻辑：提取 HTML 部分和图片部分
    parts = re.split(r'------=_NextPart_[a-f0-9]+', mht_content)
    html_content = ""
    images = {}

    for part in parts:
        if 'Content-Type: text/html' in part:
            # 提取 HTML 源码
            html_body = part.split('\r\n\r\n', 1)[1] if '\r\n\r\n' in part else part
            # 使用 bytes.fromhex 或者更安全的方式处理，但 MHT 里的 quoted-printable 经常有特殊字符
            # 先尝试简单处理
            try:
                html_content = quopri.decodestring(html_body.encode('ascii', errors='ignore')).decode('utf-8', errors='ignore')
            except Exception:
                html_content = html_body # 退而求其次
        elif 'Content-Type: image/' in part:
            # 提取图片
            if '\r\n\r\n' in part:
                headers, body = part.split('\r\n\r\n', 1)
                location_match = re.search(r'Content-Location: (.*)', headers)
                if location_match:
                    img_id = location_match.group(1).strip()
                    try:
                        img_data = base64.b64decode(body.strip())
                        img_filename = os.path.basename(img_id)
                        if not img_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                            img_filename += ".png"
                        
                        with open(os.path.join(abs_assets_dir, img_filename), 'wb') as f:
                            f.write(img_data)
                        images[img_id] = os.path.join(assets_dir_rel_to_md, img_filename)
                    except Exception as e:
                        print(f"Warning: Failed to decode image {img_id}: {e}")

    # 3. 将 HTML 转为 Markdown (非常基础的转换)
    # 提取标题
    html_content = re.sub(r'<h([1-6])[^>]*>(.*?)</h\1>', lambda m: f"\n{'#' * int(m.group(1))} {re.sub('<[^>]+>', '', m.group(2))}\n", html_content, flags=re.I|re.S)
    # 提取段落
    html_content = re.sub(r'<p[^>]*>(.*?)</p>', lambda m: f"\n{re.sub('<[^>]+>', '', m.group(1))}\n", html_content, flags=re.I|re.S)
    # 提取图片
    def replace_img(match):
        src = re.search(r'src=["\'](.*?)["\']', match.group(0))
        if src and src.group(1) in images:
            return f"\n\n![图片说明]({images[src.group(1)]})\n\n"
        return ""
    html_content = re.sub(r'<img[^>]+>', replace_img, html_content, flags=re.I)
    
    # 清理剩余标签
    markdown = re.sub(r'<[^>]+>', '', html_content)
    markdown = re.sub(r'\n\s*\n', '\n\n', markdown)
    
    return markdown.strip()

def move_source_file(docx_path):
    """
    如果文件位于 documents_all/to_be_converted 目录下，
    则在转换完成后将其移动到 documents_all/have_been_converted 目录。
    """
    abs_docx_path = os.path.abspath(docx_path)
    norm_docx_path = os.path.normpath(abs_docx_path)
    
    src_dir_marker = os.path.join("documents_all", "to_be_converted")
    dst_dir_marker = os.path.join("documents_all", "have_been_converted")
    
    if src_dir_marker in norm_docx_path:
        dst_path = norm_docx_path.replace(src_dir_marker, dst_dir_marker)
        dst_dir = os.path.dirname(dst_path)
        
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir)
            
        try:
            # 如果目标文件已存在，先删除（或者覆盖）
            if os.path.exists(dst_path):
                os.remove(dst_path)
            shutil.move(norm_docx_path, dst_path)
            print(f"Moved source file to: {dst_path}")
        except Exception as e:
            print(f"Warning: Failed to move file: {e}")

def extract_docx_to_markdown(docx_path, output_md_path, assets_dir_rel_to_md):
    """
    更加健壮的 docx 到 Markdown 转换逻辑，优化图片描述和标题识别。
    """
    document_xml_path = 'word/document.xml'
    rels_xml_path = 'word/_rels/document.xml.rels'
    
    abs_output_md_path = os.path.abspath(output_md_path)
    abs_md_dir = os.path.dirname(abs_output_md_path)
    abs_assets_dir = os.path.abspath(os.path.join(abs_md_dir, assets_dir_rel_to_md))
    
    if not os.path.exists(abs_assets_dir):
        os.makedirs(abs_assets_dir)

    with zipfile.ZipFile(docx_path, 'r') as docx:
        # 0. 检查是否为 altChunk (MHT) 格式
        markdown_content = handle_alt_chunk(docx, docx_path, abs_assets_dir, assets_dir_rel_to_md)
        if markdown_content:
            doc_title = os.path.splitext(os.path.basename(docx_path))[0]
            with open(abs_output_md_path, 'w', encoding='utf-8') as f:
                f.write(f"# {doc_title}\n\n" + markdown_content)
            return

        # 1. 获取图片关系映射
        rels_content = docx.read(rels_xml_path)
        rels_root = ET.fromstring(rels_content)
        namespaces = {
            'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'
        }
        image_rels = {}
        for rel in rels_root.findall('rel:Relationship', namespaces):
            if 'image' in rel.attrib['Type']:
                image_rels[rel.attrib['Id']] = rel.attrib['Target']

        # 2. 提取图片
        image_local_paths = {}
        for rel_id, target in image_rels.items():
            image_filename = os.path.basename(target)
            try:
                image_data = docx.read(f'word/{target}')
                with open(os.path.join(abs_assets_dir, image_filename), 'wb') as f:
                    f.write(image_data)
                image_local_paths[rel_id] = os.path.join(assets_dir_rel_to_md, image_filename)
            except KeyError:
                pass

        # 3. 解析文档内容
        doc_content = docx.read(document_xml_path)
        root = ET.fromstring(doc_content)
        
        ns = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
            'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
            'v': 'urn:schemas-microsoft-com:vml',
            'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
            'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
            'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'
        }

        elements = []
        for para in root.iter(f'{{{ns["w"]}}}p'):
            para_items = []
            para_style = ""
            
            pPr = para.find(f'{{{ns["w"]}}}pPr')
            if pPr is not None:
                pStyle = pPr.find(f'{{{ns["w"]}}}pStyle')
                if pStyle is not None:
                    para_style = pStyle.get(f'{{{ns["w"]}}}val', "")

            for node in para.iter():
                if node.tag == f'{{{ns["w"]}}}t':
                    if node.text:
                        para_items.append({'type': 'text', 'content': node.text})
                
                if node.tag == f'{{{ns["a"]}}}blip':
                    embed_id = node.get(f'{{{ns["r"]}}}embed')
                    if embed_id in image_local_paths:
                        para_items.append({'type': 'image', 'path': image_local_paths[embed_id]})
                
                if node.tag == f'{{{ns["v"]}}}imagedata':
                    rel_id = node.get(f'{{{ns["r"]}}}id')
                    if rel_id in image_local_paths:
                        para_items.append({'type': 'image', 'path': image_local_paths[rel_id]})

            if para_items:
                elements.append({'type': 'para', 'style': para_style, 'items': para_items})

        # 4. 生成 Markdown
        markdown_lines = []
        doc_title = os.path.splitext(os.path.basename(docx_path))[0]
        markdown_lines.append(f"# {doc_title}\n")
        
        for i, elem in enumerate(elements):
            # 只有 1-5 级的 style 才识别为标题，6 及以上通常是普通段落
            is_heading = elem['style'].isdigit() and 1 <= int(elem['style']) <= 5
            heading_level = int(elem['style']) if is_heading else 0
            
            current_para_content = []
            
            for j, item in enumerate(elem['items']):
                if item['type'] == 'text':
                    current_para_content.append(item['content'])
                elif item['type'] == 'image':
                    description = "图片说明"
                    
                    # 查找描述
                    # 1. 优先检查当前段落中图片前的文本 (可能是 "图1：xxx")
                    text_before = "".join([it['content'] for it in elem['items'][:j] if it['type'] == 'text']).strip()
                    if text_before and 2 < len(text_before) < 100:
                        description = text_before
                    
                    # 2. 检查上一个段落
                    elif i > 0:
                        prev_text = "".join([it['content'] for it in elements[i-1]['items'] if it['type'] == 'text']).strip()
                        if prev_text and 2 < len(prev_text) < 100:
                            description = prev_text
                        
                    # 3. 检查当前段落中图片后的文本
                    if description == "图片说明":
                        text_after = "".join([it['content'] for it in elem['items'][j+1:] if it['type'] == 'text']).strip()
                        if text_after and 2 < len(text_after) < 100:
                            description = text_after

                    # 4. 检查下一个段落
                    if description == "图片说明" and i < len(elements) - 1:
                        next_text = "".join([it['content'] for it in elements[i+1]['items'] if it['type'] == 'text']).strip()
                        if next_text and 2 < len(next_text) < 100:
                            description = next_text

                    description = re.sub(r'[\r\n\t]', ' ', description).strip()
                    if len(description) > 80:
                        description = description[:77] + "..."
                    
                    current_para_content.append(f"\n\n![{description}]({item['path']})\n\n")

            content_str = "".join(current_para_content).strip()
            if content_str:
                if is_heading:
                    markdown_lines.append(f"{'#' * (heading_level + 1)} {content_str}\n")
                elif any(content_str.startswith(f"{k}、") or content_str.startswith(f"{k}.") for k in range(1, 100)):
                    markdown_lines.append(f"- {content_str}\n")
                else:
                    markdown_lines.append(f"{content_str}\n")

        with open(abs_output_md_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(markdown_lines))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert DOCX to Markdown with robust image extraction.")
    parser.add_argument("input", help="Path to the input .docx file")
    parser.add_argument("output", help="Path to the output .md file")
    parser.add_argument("--assets", default="../assets", help="Relative path for assets (default: ../assets)")
    
    args = parser.parse_args()
    
    if os.path.exists(args.input):
        try:
            extract_docx_to_markdown(args.input, args.output, args.assets)
            print(f"Successfully converted {args.input}")
            # 转换成功后移动源文件
            move_source_file(args.input)
        except Exception as e:
            print(f"Error: {e}")
