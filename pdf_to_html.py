import fitz  # PyMuPDF
import os
import re
import markdown
import pymupdf4llm
import camelot
import uuid
import tempfile

def extract_images(pdf_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    pdf_document = fitz.open(pdf_path)
    image_positions = {}
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)
        image_positions[page_num] = []
        
        for image_index, img in enumerate(image_list):
            try:
                xref = img[0]
                base_image = pdf_document.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                image_filename = f"image_{page_num + 1}_{image_index + 1}.{image_ext}"
                image_path = os.path.join(output_folder, image_filename)
                
                with open(image_path, "wb") as image_file:
                    image_file.write(image_bytes)
                
                # Get the image rectangle for placeholder replacement
                image_rect = page.get_image_rects(xref)[0]
                image_positions[page_num].append((image_rect, image_filename))
            except Exception as e:
                print(f"Error extracting image {image_index + 1} on page {page_num + 1}: {e}")
    
    pdf_document.close()
    return image_positions

def replace_images_with_placeholders(pdf_path, output_pdf_path, image_positions):
    pdf_document = fitz.open(pdf_path)
    
    for page_number, images in image_positions.items():
        page = pdf_document[page_number]
        images.sort(key=lambda x: (x[0].y0, x[0].x0))
        
        for rect, image_filename in images:
            placeholder_text = f"[{image_filename}]"
            page.insert_textbox(
                rect,
                placeholder_text,
                fontsize=12,
                color=(0, 0, 0),
                align=0
            )
    
    pdf_document.save(output_pdf_path, garbage=4, deflate=True)
    pdf_document.close()

def extract_tables(pdf_path, output_folder):
    os.makedirs(output_folder, exist_ok=True)
    try:
        tables = camelot.read_pdf(pdf_path, flavor='lattice', pages='all')
        table_positions = {}
        
        for table_idx, table in enumerate(tables, start=1):
            page_num = table.page - 1
            table_html = table.df.to_html(index=False, header=True, classes="pdf-table")
            rect = fitz.Rect(table._bbox) if table._bbox else fitz.Rect(50, 50, 550, 350)
            table_filename = f"table_{table_idx}_page_{table.page}.html"
            table_path = os.path.join(output_folder, table_filename)
            
            with open(table_path, "w", encoding="utf-8") as table_file:
                table_file.write(table_html)
            
            if page_num not in table_positions:
                table_positions[page_num] = []
            table_positions[page_num].append((rect, table_filename, table_html))
        
        return table_positions
    except Exception as e:
        print(f"Error extracting tables from PDF: {e}")
        return {}

def replace_tables_with_placeholders(pdf_path, output_pdf_path, table_positions):
    pdf_document = fitz.open(pdf_path)
    
    for page_number, tables in table_positions.items():
        page = pdf_document[page_number]
        tables.sort(key=lambda x: (x[0].y0, x[0].x0))
        
        for rect, table_filename, _ in tables:
            placeholder_text = f"[TABLE:{table_filename}]"
            page.insert_textbox(
                rect,
                placeholder_text,
                fontsize=12,
                color=(0, 0, 0),
                align=0
            )
    
    pdf_document.save(output_pdf_path, garbage=4, deflate=True)
    pdf_document.close()

def convert_pdf_to_markdown(pdf_path, image_folder, table_folder):
    pdf_document = fitz.open(pdf_path)
    num_pages = len(pdf_document)
    first_page_md_path = "first_page.md"
    remaining_pages_md_path = "remaining_pages.md"
    
    # Convert the first page to Markdown
    try:
        first_page_content = pymupdf4llm.to_markdown(
            pdf_path,
            pages=[0],
            write_images=True,
            image_path=image_folder
        )
    except Exception as e:
        print(f"Error converting first page to Markdown: {e}")
        first_page_content = "# First Page\n\n(No content extracted)"
    
    with open(first_page_md_path, "w", encoding="utf-8") as md_file:
        md_file.write(first_page_content)
    
    # Convert the remaining pages to Markdown
    if num_pages > 1:
        try:
            remaining_pages_content = pymupdf4llm.to_markdown(
                pdf_path,
                pages=list(range(1, num_pages)),
                write_images=True,
                image_path=image_folder
            )
        except Exception as e:
            print(f"Error converting remaining pages to Markdown: {e}")
            remaining_pages_content = "# Remaining Pages\n\n(No additional pages)"
    else:
        remaining_pages_content = "# Remaining Pages\n\n(No additional pages)"
    
    with open(remaining_pages_md_path, "w", encoding="utf-8") as md_file:
        md_file.write(remaining_pages_content)
    
    pdf_document.close()
    return first_page_md_path, remaining_pages_md_path

def convert_into_markdownimages_and_tables(markdown_path, image_folder, table_folder):
    with open(markdown_path, "r", encoding="utf-8") as md_file:
        lines = md_file.readlines()

    image_pattern = re.compile(r'\[([^\]]+\.(?:png|jpg|jpeg|gif))\]')
    table_pattern = re.compile(r'\[TABLE:([^\]]+\.html)\]')
    new_lines = []

    for line in lines:
        image_matches = image_pattern.findall(line)
        for image_filename in image_matches:
            image_path = os.path.join(image_folder, image_filename)
            if os.path.exists(image_path):
                image_markdown = f"![{image_filename}]({image_path})"
                line = line.replace(f'[{image_filename}]', image_markdown)
            else:
                print(f"Warning: Image {image_path} not found.")
        
        table_matches = table_pattern.findall(line)
        for table_filename in table_matches:
            table_path = os.path.join(table_folder, table_filename)
            if not os.path.exists(table_path):
                print(f"Warning: Table {table_path} not found.")
        
        new_lines.append(line)

    with open(markdown_path, "w", encoding="utf-8") as md_file:
        md_file.writelines(new_lines)

def group_images_in_rows(md_content):
    img_pattern = r'!\[.*?\]\((.*?)\)'
    lines = md_content.split('\n')
    new_lines = []
    buffer = []

    for line in lines:
        match = re.match(img_pattern, line.strip())
        if match:
            img_src = match.group(1)
            buffer.append(f'<img src="{img_src}" alt="" />')
            if len(buffer) == 3:
                new_lines.append('<div class="image-row">\n' + '\n'.join(buffer) + '\n</div>')
                buffer = []
        else:
            if buffer:
                new_lines.append('<div class="image-row">\n' + '\n'.join(buffer) + '\n</div>')
                buffer = []
            new_lines.append(line)
    if buffer:
        new_lines.append('<div class="image-row">\n' + '\n'.join(buffer) + '\n</div>')
    return '\n'.join(new_lines)

def convert_pdf_to_html(pdf_path, image_folder, table_folder, css_file_path, output_html_path, header_image_path):
    footer_content = """
Advanced Energy (AE) has devoted more than three decades to perfecting power for its global customers. AE designs and manufactures highly engineered, precision power conversion, measurement and control solutions for mission-critical applications and processes.

Our products enable customer innovation in complex applications for a wide range of industries including semiconductor equipment, industrial, manufacturing, telecommunications, data center computing, and medical. With deep applications know-how and responsive service and support across the globe, we build collaborative partnerships to meet rapid technological developments, propel growth for our customers, and innovate the future of power.

For international contact information, visit advancedenergy.com.

powersales@aei.com (Sales Support)  
productsupport.ep@aei.com (Technical Support)  +1 888 412 7832

Specifications are subject to change without notice. Not responsible for errors or omissions. ©2020 Advanced Energy Industries, Inc. All rights reserved. Advanced Energy®, and AE® are U.S. trademarks of Advanced Energy Industries, Inc."""
    
    # Step 1: Extract images and tables
    image_positions = extract_images(pdf_path, image_folder)
    table_positions = extract_tables(pdf_path, table_folder)
    
    # Step 2: Replace images and tables with placeholders in PDF
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_pdf_path1 = temp_file.name
    replace_images_with_placeholders(pdf_path, temp_pdf_path1, image_positions)
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_pdf_path2 = temp_file.name
    replace_tables_with_placeholders(temp_pdf_path1, temp_pdf_path2, table_positions)
    
    # Step 3: Convert PDF to Markdown
    first_page_md, remaining_pages_md = convert_pdf_to_markdown(temp_pdf_path2, image_folder, table_folder)
    
    # Step 4: Replace placeholders in Markdown
    convert_into_markdownimages_and_tables(first_page_md, image_folder, table_folder)
    convert_into_markdownimages_and_tables(remaining_pages_md, image_folder, table_folder)
    
    # Step 5: Read and clean Markdown content
    with open(first_page_md, 'r', encoding='utf-8') as md_file:
        first_page_content = md_file.read()
    first_page_content = re.sub(r'\*\*TECHNICAL REFERENCE NOTE\*\*\s*\n?', '', first_page_content, flags=re.IGNORECASE)
    
    with open(remaining_pages_md, 'r', encoding='utf-8') as md_file:
        remaining_pages_content = md_file.read()
    
    text_to_remove = r"""For international contact information,.*?\bAdvanced Energy Industries, Inc\.""".strip()
    first_page_cleaned = re.sub(
        rf'{text_to_remove}\s*$',
        '',
        first_page_content,
        flags=re.DOTALL | re.MULTILINE
    ).strip()
    
    remaining_pages_cleaned = re.sub(
        rf'{text_to_remove}\s*$',
        '',
        remaining_pages_content,
        flags=re.DOTALL | re.MULTILINE
    ).strip()
    
    # Step 6: Group images in rows
    first_page_grouped = group_images_in_rows(first_page_cleaned)
    remaining_pages_grouped = group_images_in_rows(remaining_pages_cleaned)
    
    # Step 7: Convert Markdown to HTML
    first_page_html = markdown.markdown(first_page_grouped, extensions=['extra', 'codehilite'])
    remaining_pages_html = markdown.markdown(remaining_pages_grouped, extensions=['extra', 'codehilite'])
    footer_html = markdown.markdown(footer_content, extensions=['extra', 'codehilite'])
    
    # Step 8: Replace table placeholders with iframes
    table_pattern = re.compile(r'\[TABLE:([^\]]+\.html)\]')
    def replace_table(match):
        table_filename = match.group(1)
        table_path = os.path.join(table_folder, table_filename).replace("\\", "/")
        return f'<iframe src="{table_path}" width="100%" height="300px" style="border:none;"></iframe>'
    
    first_page_html = table_pattern.sub(replace_table, first_page_html)
    remaining_pages_html = table_pattern.sub(replace_table, remaining_pages_html)
    
    # Step 9: Read CSS file
    with open(css_file_path, 'r', encoding='utf-8') as css_file:
        css_content = css_file.read()
    
    # Step 10: Extract page title
    h1_match = re.search(r'^#\s+(.+)$', first_page_content, re.MULTILINE)
    page_title = h1_match.group(1).strip() if h1_match else "PDF to HTML"
    
    # Step 11: Create final HTML
    html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
{css_content}
    </style>
</head>
<body>
<div class="section">
    <header style="position: relative; min-height: 80px;" class="header">
        <span style="position: absolute; left: 30px; top: 50px; color: #004080; font-weight: bold; font-size: 1.2em;">TECHNICAL REFERENCE NOTE</span>
        <img src="{header_image_path}" alt="Header Image" style="position: absolute; top: 0; right: 50px; max-width: 700px;">
    </header>
    <main>
        {first_page_html}
    </main>
</div>
<div class="section">
    <main>
        {remaining_pages_html}
    </main>
</div>
<div class="section">
    <h2 align="center"> ABOUT ADVANCED ENERGY</h2>
    <footer class="footer">
        {footer_html}
    </footer>
</div>
</body>
</html>"""
    
    # Step 12: Write the output HTML
    with open(output_html_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_output)
    
    # Clean up temporary files
    if os.path.exists(temp_pdf_path1):
        os.remove(temp_pdf_path1)
    if os.path.exists(temp_pdf_path2):
        os.remove(temp_pdf_path2)

if __name__ == "__main__":
    pdf_path = "LCM3000.pdf"
    image_folder = "images"
    table_folder = "tables_output"
    css_file = "pdf_styles.css"
    output_html = "output.html"
    header_image = "advance_energy.png"
    
    try:
        if not os.path.exists(pdf_path):
            print(f"Error: PDF file '{pdf_path}' not found.")
        elif not os.path.exists(css_file):
            print(f"Error: CSS file '{css_file}' not found.")
        elif not os.path.exists(header_image):
            print(f"Error: Header image file '{header_image}' not found.")
        else:
            convert_pdf_to_html(pdf_path, image_folder, table_folder, css_file, output_html, header_image)
            print(f"Conversion completed successfully. HTML file saved: {output_html}")
            print("Markdown files saved: first_page.md, remaining_pages.md")
    except Exception as e:
        print(f"Pipeline failed: {e}")