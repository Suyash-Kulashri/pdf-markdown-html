import fitz  # PyMuPDF
import os
import pymupdf4llm
import re
from markdown import markdown
import camelot
import pandas as pd

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
    Convert PDF to two Markdown files: one for the first page and one for the remaining pages,
    excluding footer content.
    """
    try:
        first_page_md_path = "first_page.md"
        remaining_pages_md_path = "remaining_pages.md"
        
        # Open the PDF document
        pdf_document = fitz.open(pdf_path)
        num_pages = len(pdf_document)
        
        # Define footer exclusion logic
        def exclude_footer(page):
            page_height = page.rect.height
            footer_height = page_height * 0.1  # Assume footer is in the bottom 10% of the page
            footer_rect = fitz.Rect(0, page_height - footer_height, page.rect.width, page_height)
            return footer_rect

        # Function to filter out text blocks in the footer
        def filter_text_blocks(page, footer_rect):
            text_blocks = page.get_text("blocks")
            filtered_blocks = []
            for block in text_blocks:
                block_rect = fitz.Rect(block[:4])  # x0, y0, x1, y1
                if not footer_rect.intersects(block_rect):
                    filtered_blocks.append(block)
            return filtered_blocks

        # Convert the first page to Markdown, excluding footer
        first_page = pdf_document[0]
        footer_rect = exclude_footer(first_page)
        # Use pymupdf4llm to convert, but we'll handle footer exclusion manually
        first_page_content = pymupdf4llm.to_markdown(
            pdf_path,
            pages=[0],  # Only process the first page (0-based index)
            write_images=True,
            image_path=image_folder
        )
        
        # Filter out footer content
        filtered_blocks = filter_text_blocks(first_page, footer_rect)
        # Reconstruct text content from filtered blocks
        filtered_text = ""
        for block in filtered_blocks:
            if len(block) > 4:  # Ensure block has text content
                filtered_text += block[4] + "\n"
        # If pymupdf4llm extracted images correctly, retain them in the output
        first_page_content = filtered_text or "# First Page\n\n(No content extracted)"
        
        # Save the first page Markdown
        with open(first_page_md_path, "w", encoding="utf-8") as md_file:
            md_file.write(first_page_content)
        
        # Convert the remaining pages to Markdown (if any), excluding footer
        if num_pages > 1:
            remaining_pages_content = ""
            for page_num in range(1, num_pages):
                page = pdf_document[page_num]
                footer_rect = exclude_footer(page)
                page_content = pymupdf4llm.to_markdown(
                    pdf_path,
                    pages=[page_num],
                    write_images=True,
                    image_path=image_folder
                )
                # Filter out footer content
                filtered_blocks = filter_text_blocks(page, footer_rect)
                filtered_page_text = ""
                for block in filtered_blocks:
                    if len(block) > 4:  # Ensure block has text content
                        filtered_page_text += block[4] + "\n"
                page_content = filtered_page_text or f"# Page {page_num + 1}\n\n(No content extracted)"
                remaining_pages_content += page_content
                
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

def convert_markdown_to_html(markdown_path, html_output_path, table_folder, table_positions):
    """
    Convert Markdown file to HTML with proper HTML structure, CSS, and iframe for tables.
    """
    try:
        with open(markdown_path, "r", encoding="utf-8", errors="ignore") as md_file:
            markdown_content = md_file.read()
        
        html_content = markdown(markdown_content)
        
        table_pattern = re.compile(r'\[TABLE:([^\]]+\.html)\]')
        def replace_table(match):
            table_filename = match.group(1)
            table_path = os.path.join(table_folder, table_filename).replace("\\", "/")
            return f'<iframe src="{table_path}" width="100%" height="300px" style="border:none;"></iframe>'
        
        html_content = table_pattern.sub(replace_table, html_content)
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF to HTML Conversion</title>
    <link rel="stylesheet" href="pdf_styles.css">
</head>
<body>
    {html_content}
</body>
</html>"""
        
        with open(html_output_path, "w", encoding="utf-8") as html_file:
            html_file.write(html_template)
    except Exception as e:
        print(f"Error converting Markdown to HTML: {e}")
        raise

if __name__ == "__main__":
    pdf_path = "LCM3000.pdf"
    image_folder = "images"
    table_folder = "tables_output"
    output_pdf_path = "modified.pdf"
    html_output_path = "output.html"
    css_path = "pdf_styles.css"
    
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
        convert_into_markdownimages_and_tables(remaining_pages_md, image_folder, table_folder)
        convert_markdown_to_html(first_page_md, html_output_path, table_folder, table_positions)
        print("Conversion completed successfully.")
        print(f"Markdown files saved: {first_page_md}, {remaining_pages_md}")
    except Exception as e:
        print(f"Pipeline failed: {e}")