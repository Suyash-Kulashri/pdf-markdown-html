import fitz  # PyMuPDF
import os
import pymupdf4llm
import re
from markdown import markdown
import camelot
import pandas as pd
import markdown

def extract_images(pdf_path, output_folder):
    """
    Extract images from a PDF and save them to the output folder.
    """
    try:
        os.makedirs(output_folder, exist_ok=True)
        pdf_document = fitz.open(pdf_path)
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            image_list = page.get_images(full=True)
            
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
                except Exception as e:
                    print(f"Error extracting image {image_index + 1} on page {page_num + 1}: {e}")
        
        pdf_document.close()
    except Exception as e:
        print(f"Error processing PDF {pdf_path}: {e}")
        raise
    
    
def replace_images_with_placeholders(pdf_path, output_pdf_path, image_positions):
    """
    Replace images in the PDF with text placeholders.
    """
    try:
        pdf_document = fitz.open(pdf_path)
        
        for page_number, images in image_positions.items():
            try:
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
            except Exception as e:
                print(f"Error processing page {page_number}: {e}")
        
        pdf_document.save(output_pdf_path, garbage=4, deflate=True)
        pdf_document.close()
    except Exception as e:
        print(f"Error saving modified PDF {output_pdf_path}: {e}")
        raise

def extract_tables(pdf_path, output_folder):
    """
    Extract tables from PDF using Camelot and save as HTML files.
    Returns a dictionary mapping page numbers to list of table HTML strings and their positions.
    """
    try:
        os.makedirs(output_folder, exist_ok=True)
        tables = camelot.read_pdf(pdf_path, flavor='lattice', pages='all')
        table_positions = {}
        
        print(f"Total tables extracted: {tables.n}")
        
        for table_idx, table in enumerate(tables, start=1):
            page_num = table.page - 1  # Camelot pages are 1-based, convert to 0-based
            table_html = table.df.to_html(index=False, header=True, classes="pdf-table")
            if table._bbox:
                rect = fitz.Rect(table._bbox)
            else:
                rect = fitz.Rect(50, 50, 550, 350)
            table_filename = f"table_{table_idx}_page_{table.page}.html"
            table_path = os.path.join(output_folder, table_filename)
            
            with open(table_path, "w", encoding="utf-8") as table_file:
                table_file.write(table_html)
            
            if page_num not in table_positions:
                table_positions[page_num] = []
            table_positions[page_num].append((rect, table_filename, table_html))
            
            print(f"Saved table {table_idx} to {table_path}")
        
        return table_positions
    except Exception as e:
        print(f"Error extracting tables from PDF: {e}")
        raise

def replace_tables_with_placeholders(pdf_path, output_pdf_path, table_positions):
    """
    Replace tables in the PDF with text placeholders.
    """
    try:
        pdf_document = fitz.open(pdf_path)
        
        for page_number, tables in table_positions.items():
            try:
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
            except Exception as e:
                print(f"Error processing page {page_number}: {e}")
        
        pdf_document.save(output_pdf_path, garbage=4, deflate=True)
        pdf_document.close()
    except Exception as e:
        print(f"Error saving modified PDF {output_pdf_path}: {e}")
        raise

def convert_pdf_to_markdown(pdf_path, image_folder, table_folder, table_positions):
    """
    Convert PDF to two Markdown files: one for the first page and one for the remaining pages.
    """
    try:
        first_page_md_path = "first_page.md"
        remaining_pages_md_path = "remaining_pages.md"
        
        # Open the PDF document
        pdf_document = fitz.open(pdf_path)
        num_pages = len(pdf_document)
        
        # Convert the first page to Markdown
        first_page_content = pymupdf4llm.to_markdown(
            pdf_path,
            pages=[0],  # Only process the first page (0-based index)
            write_images=True,
            image_path=image_folder
        )
        
        # Save the first page Markdown
        with open(first_page_md_path, "w", encoding="utf-8") as md_file:
            md_file.write(first_page_content or "# First Page\n\n(No content extracted)")
        
        # Convert the remaining pages to Markdown (if any)
        if num_pages > 1:
            remaining_pages_content = pymupdf4llm.to_markdown(
                pdf_path,
                pages=list(range(1, num_pages)),  # Process pages 2 to end
                write_images=True,
                image_path=image_folder
            )
            
            # Save the remaining pages Markdown
            with open(remaining_pages_md_path, "w", encoding="utf-8") as md_file:
                md_file.write(remaining_pages_content or "# Remaining Pages\n\n(No content extracted)")
        else:
            # If only one page exists, create an empty remaining pages file
            with open(remaining_pages_md_path, "w", encoding="utf-8") as md_file:
                md_file.write("# Remaining Pages\n\n(No additional pages)")
        
        pdf_document.close()
        return first_page_md_path, remaining_pages_md_path
    except Exception as e:
        print(f"Error converting PDF to Markdown: {e}")
        raise

def convert_into_markdownimages_and_tables(markdown_path, image_folder, table_folder):
    """
    Replace image and table placeholders in Markdown with proper syntax.
    """
    try:
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
    except Exception as e:
        print(f"Error processing Markdown file {markdown_path}: {e}")
        raise
    
    
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

def convert_markdown_to_html(first_page_md_path, remaining_pages_md_path, css_file_path, output_html_path, image_file_path):
    # Hardcoded footer content
    footer_content = """

Advanced Energy (AE) has devoted more than three decades to perfecting power for its global customers. AE designs and manufactures highly engineered, precision power conversion, measurement and control solutions for mission-critical applications and processes.

Our products enable customer innovation in complex applications for a wide range of industries including semiconductor equipment, industrial, manufacturing, telecommunications, data center computing, and medical. With deep applications know-how and responsive service and support across the globe, we build collaborative partnerships to meet rapid technological developments, propel growth for our customers, and innovate the future of power.

For international contact information, visit advancedenergy.com.

powersales@aei.com (Sales Support)  
productsupport.ep@aei.com (Technical Support)  +1 888 412 7832

Specifications are subject to change without notice. Not responsible for errors or omissions. ©2020 Advanced Energy Industries, Inc. All rights reserved. Advanced Energy®, and AE® are U.S. trademarks of Advanced Energy Industries, Inc."""
    
    # Read the first page Markdown file
    with open(first_page_md_path, 'r', encoding='utf-8') as md_file:
        first_page_content = md_file.read()
    # Remove "**TECHNICAL REFERENCE NOTE**" from the file if present
    first_page_content = re.sub(r'\*\*TECHNICAL REFERENCE NOTE\*\*\s*\n?', '', first_page_content, flags=re.IGNORECASE)

    # Read the remaining pages Markdown file
    with open(remaining_pages_md_path, 'r', encoding='utf-8') as md_file:
        remaining_pages_content = md_file.read()
    
    # Extract the first H1 heading from the first page content for the page title
    h1_match = re.search(r'^#\s+(.+)$', first_page_content, re.MULTILINE)
    page_title = h1_match.group(1).strip() if h1_match else "Markdown to HTML"
    
    # Remove the specified text from the bottom of both Markdown contents
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
    
        # Group images in rows before converting to HTML
    first_page_grouped = group_images_in_rows(first_page_cleaned)
    remaining_pages_grouped = group_images_in_rows(remaining_pages_cleaned)

    # Convert Markdown to HTML
    first_page_html = markdown.markdown(first_page_grouped, extensions=['extra', 'codehilite'])
    remaining_pages_html = markdown.markdown(remaining_pages_grouped, extensions=['extra', 'codehilite'])
    footer_html = markdown.markdown(footer_content, extensions=['extra', 'codehilite'])

    # Read the CSS file
    with open(css_file_path, 'r', encoding='utf-8') as css_file:
        css_content = css_file.read()
    
    # Create the complete HTML with CSS embedded, header, sections for content, and footer
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
        <img src="{image_file_path}" alt="Header Image" style="position: absolute; top: 0; right: 50px; max-width: 700px;">
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
    
    # Write the output to an HTML file
    with open(output_html_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_output)
        
        
if __name__ == "__main__":
    pdf_path = "LCM3000.pdf"
    image_folder = "images"
    table_folder = "tables_output"
    output_pdf_path = "modified.pdf"
    first_page_md = "first_page.md"
    remaining_pages_md = "remaining_pages.md"
    css_file = "pdf_styles.css"
    output_file = "output_with_css.html"
    image_file_path = "advance_energy.png"

    image_positions = {
        0: [(fitz.Rect(100, 100, 200, 200), "image_1_1.png")]
    }
    
    try:
        if not os.path.exists(pdf_path):
            print(f"Error: The file {pdf_path} does not exist.")
            exit(1)
            
            
        extract_images(pdf_path, image_folder)
        replace_images_with_placeholders(pdf_path, output_pdf_path, image_positions)
        table_positions = extract_tables(pdf_path, table_folder)
        replace_tables_with_placeholders(pdf_path, output_pdf_path, table_positions)
        first_page_md, remaining_pages_md = convert_pdf_to_markdown(pdf_path, image_folder, table_folder, table_positions)
        convert_into_markdownimages_and_tables(first_page_md, image_folder, table_folder)
        if not os.path.exists(first_page_md):
            print(f"Error: Markdown file '{first_page_md}' not found.")
        elif not os.path.exists(remaining_pages_md):
            print(f"Error: Markdown file '{remaining_pages_md}' not found.")
        elif not os.path.exists(css_file):
            print(f"Error: CSS file '{css_file}' not found.")
        elif not os.path.exists(image_file_path):
            print(f"Error: Image file '{image_file_path}' not found.")
        else:
            try:
                convert_markdown_to_html(first_page_md, remaining_pages_md, css_file, output_file, image_file_path)
                print(f"HTML file generated: {output_file}")
            except Exception as e:
                print(f"Error processing Markdown files: {str(e)}")
            print("Conversion completed successfully.")
            print(f"Markdown files saved: {first_page_md}, {remaining_pages_md}")
    except Exception as e:
        print(f"Pipeline failed: {e}")