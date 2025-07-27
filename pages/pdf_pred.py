import streamlit as st
from dotenv import load_dotenv
import os
import PyPDF2
from pdf2image import convert_from_bytes
import pytesseract
import io
import re
import traceback
import google.generativeai as genai
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image as RLImage
from reportlab.lib import colors
from xml.sax.saxutils import escape
from docx import Document
import zipfile
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from pdf2docx import Converter # Ensure this is installed: pip install pdf2docx
import tempfile
import openai
import base64
import json

# Load environment variables from .env file
load_dotenv()

# --- API Configuration ---
google_api_key = os.getenv("GOOGLE_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not google_api_key:
    st.error("Google API key is missing. Please add it to your .env file (e.g., GOOGLE_API_KEY='your_key_here').")
    st.stop()

if not openai_api_key:
    st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    st.stop()

try:
    genai.configure(api_key=google_api_key)
    openai_client = openai.OpenAI(api_key=openai_api_key)
except Exception as e:
    st.error(f"Failed to configure APIs: {e}")
    st.stop()

# --- System Prompt for Image Analysis ---
SYSTEM_PROMPT = """
You are an expert image and document analysis assistant tasked with labeling images extracted from a PDF file. Your goal is to provide accurate, concise, and contextually relevant labels for each image based on the document's content.

**Input**:
- Document text from the PDF file for context.
- The image encoded in base64 format for analysis.
- The image dimensions (width x height in pixels) will be provided separately.

**Task**:
Analyze the image and document text to generate a label with the following fields:
{
  "description": "string",
  "purpose": "string",
  "pinpoint_size": "width x height"
}

**Output**:
Return a JSON object with the above fields.

**Guidelines**:
- Prioritize the document text to ground your analysis.
- If the image content is ambiguous, make an educated guess based on the document text.
- Ensure the description is specific (e.g., "Pie chart of market share" instead of "Chart").
- Do not include irrelevant or speculative information.
- The output MUST be a valid JSON object.
"""

# --- Streamlit Page Setup ---
st.set_page_config(layout="wide", page_title="Enhanced PDF Specification Generator", page_icon="📄")

# --- Custom CSS for Styling ---
st.markdown("""
    <style>
    .stApp {
        background-color: #000000; /* Light background */
    }
    .image-preview {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        margin: 5px;
    }
    .st-emotion-cache-16txt4v { /* Targeted adjustment for wider columns in main content */
        gap: 2rem;
    }
    .st-emotion-cache-z5fcl4 { /* Sidebar width adjustment */
        width: 20rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- Main App Interface ---
st.title("📄 Enhanced PDF Specification Generator with Image Extraction")
st.markdown("""
    <div style="color: #475569; margin-bottom: 24px; font-size: 1.1rem;">
    Upload a product datasheet PDF to:
    1. Extract and analyze images with AI-powered labeling
    2. Generate specifications for other models in the series
    3. Create professional PDFs with extracted images included
    </div>
""", unsafe_allow_html=True)

# --- Session State Initialization ---
if "conversation" not in st.session_state:
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    model = genai.GenerativeModel('gemini-1.5-flash-latest', safety_settings=safety_settings)
    st.session_state.conversation = model.start_chat(history=[])
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pdf_text" not in st.session_state:
    st.session_state.pdf_text = ""
if "extracted_images" not in st.session_state:
    st.session_state.extracted_images = []
if "temp_image_dir" not in st.session_state:
    st.session_state.temp_image_dir = None
if "uploaded_file_object" not in st.session_state: # To persist the uploaded file
    st.session_state.uploaded_file_object = None

# --- Core Functions ---

def extract_pdf_text(uploaded_file):
    """Extract text from PDF using PyPDF2 with OCR fallback"""
    try:
        # For PyPDF2, it's better to pass a BytesIO object or file path
        # Re-seek to 0 in case it was read elsewhere
        uploaded_file.seek(0) 
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = "".join(page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text())
        
        if len(text.strip()) < 100 and len(pdf_reader.pages) > 0: # Only try OCR if initial extraction is very small
            st.warning("Initial text extraction was minimal. Attempting OCR fallback (may take time)...")
            uploaded_file.seek(0) # Re-seek for pdf2image
            images = convert_from_bytes(uploaded_file.getvalue())
            ocr_text = "".join(pytesseract.image_to_string(image) + "\n" for image in images)
            if len(ocr_text.strip()) > len(text.strip()):
                st.info("OCR provided more text. Using OCR result.")
                text = ocr_text

        if not text.strip():
            st.error("No text could be extracted from the PDF.")
            return ""
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {e}")
        return ""

def extract_images_from_pdf(uploaded_file_bytes, min_width=150, min_height=150, min_kb=15):
    """Extract images from PDF by converting to DOCX first, then label with OpenAI"""
    extracted_images = []
    
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Save uploaded PDF to temporary file
            pdf_path = os.path.join(temp_dir, "temp.pdf")
            with open(pdf_path, "wb") as f:
                f.write(uploaded_file_bytes)
            
            # Convert PDF to DOCX
            docx_path = os.path.join(temp_dir, "temp.docx")
            cv = Converter(pdf_path)
            cv.convert(docx_path)
            cv.close()
            
            # Extract images from DOCX
            doc = Document(docx_path)
            doc_text = "\n".join([para.text for para in doc.paragraphs])
            
            saved_image_count = 0
            
            # Iterate through all relationships in the document part
            for rel in doc.part._rels.values():
                if "image" in rel.target_ref:
                    image_data = rel.target_part.blob
                    file_size_kb = len(image_data) / 1024

                    # Filter by file size
                    if file_size_kb >= min_kb:
                        try:
                            img_stream = BytesIO(image_data)
                            image = Image.open(img_stream)
                            width, height = image.size

                            # Filter by dimensions
                            if width >= min_width and height >= min_height:
                                saved_image_count += 1
                                # Ensure image format is suitable for base64 (e.g., PNG, JPEG)
                                image_format = image.format if image.format else 'PNG'
                                if image_format.upper() == 'BMP': # Convert BMP to PNG as BMP might not be supported well
                                    img_byte_arr_png = BytesIO()
                                    image.save(img_byte_arr_png, format='PNG')
                                    image_data = img_byte_arr_png.getvalue()
                                    image_ext = 'png'
                                else:
                                    image_ext = image_format.lower()
                                
                                image_filename = f"extracted_image_{saved_image_count}.{image_ext}"

                                # Encode image to base64 for LLM
                                base64_image = base64.b64encode(image_data).decode('utf-8')

                                # Call OpenAI API for labeling
                                try:
                                    response = openai_client.chat.completions.create(
                                        model="gpt-4o",
                                        messages=[
                                            {"role": "system", "content": SYSTEM_PROMPT},
                                            {
                                                "role": "user",
                                                "content": [
                                                    {"type": "text", "text": f"Document text: {doc_text[:2000]}...\nImage dimensions: {width} x {height}"},
                                                    {
                                                        "type": "image_url",
                                                        "image_url": {"url": f"data:image/{image_ext};base64,{base64_image}"}
                                                    }
                                                ]
                                            }
                                        ],
                                        max_tokens=300,
                                        response_format={ "type": "json_object" } # Request JSON output
                                    )
                                    label_content = response.choices[0].message.content
                                    try:
                                        label = json.loads(label_content)
                                        label["pinpoint_size"] = f"{width} x {height}" # Ensure size is correct
                                    except json.JSONDecodeError:
                                        st.warning(f"AI returned invalid JSON for image {saved_image_count}. Raw response: {label_content}")
                                        label = {
                                            "description": "Technical diagram or chart (AI JSON error)",
                                            "pinpoint_size": f"{width} x {height}",
                                            "purpose": "Supporting technical documentation"
                                        }
                                except Exception as e:
                                    st.warning(f"OpenAI API call failed for image {saved_image_count}: {e}")
                                    label = {
                                        "description": "Technical diagram or chart (AI API error)",
                                        "pinpoint_size": f"{width} x {height}",
                                        "purpose": "Supporting technical documentation"
                                    }

                                # Annotate the image with the label
                                # Re-open image from original data for annotation to avoid format issues
                                original_pil_image = Image.open(BytesIO(image_data))
                                annotated_image = annotate_image(original_pil_image, label)
                                
                                img_byte_arr_annotated = BytesIO()
                                annotated_image.save(img_byte_arr_annotated, format=image_format) # Save in original format
                                annotated_image_data = img_byte_arr_annotated.getvalue()

                                extracted_images.append({
                                    'filename': image_filename,
                                    'data': annotated_image_data, # Annotated image data for display
                                    'original_data': image_data,  # Original image data for PDF embedding
                                    'label': label,
                                    'width': width,
                                    'height': height
                                })
                        
                        except Exception as e:
                            st.warning(f"Could not process an individual image during extraction: {e}")
                            
        except Exception as e:
            st.error(f"Error extracting images from PDF: {e}")
            st.error(traceback.format_exc()) # Print full traceback for debugging
            return []

    return extracted_images

def annotate_image(image, label):
    """Annotate image with label information using a clean bottom banner approach"""
    img_copy = image.copy()
    width, height = img_copy.size
    
    banner_height = max(80, int(height * 0.15))
    
    new_height = height + banner_height
    new_img = Image.new('RGB', (width, new_height), color=(245, 245, 245))
    
    new_img.paste(img_copy, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", max(14, min(20, width // 25)))
        detail_font = ImageFont.truetype("arial.ttf", max(10, min(14, width // 35)))
    except IOError: # Fallback if font not found
        title_font = ImageFont.load_default()
        detail_font = ImageFont.load_default()
    
    banner_y = height
    draw.rectangle([0, banner_y, width, new_height], fill=(240, 240, 240))
    draw.line([(0, banner_y), (width, banner_y)], fill=(70, 130, 180), width=2) # Blue top line

    description = label.get('description', 'Technical Diagram')
    purpose = label.get('purpose', 'Supporting Documentation')
    size_info = label.get('pinpoint_size', f"{width} x {height}")
    
    max_desc_length = int(width / (title_font.size * 0.6)) # Estimate chars based on font size and width
    max_purpose_length = int(width / (detail_font.size * 0.6))

    if len(description) > max_desc_length and max_desc_length > 3:
        description = description[:max_desc_length-3] + "..."
    if len(purpose) > max_purpose_length and max_purpose_length > 3:
        purpose = purpose[:max_purpose_length-3] + "..."
    
    text_margin = 10
    line_spacing = max(20, banner_height // 3)
    
    draw.text((text_margin, banner_y + text_margin), f"📊 {description}", 
              fill=(60, 60, 60), font=title_font)
    
    draw.text((text_margin, banner_y + text_margin + line_spacing), f"🎯 {purpose}", 
              fill=(80, 80, 80), font=detail_font)
    
    size_text = f"📐 {size_info}"
    try:
        if detail_font:
            size_bbox = draw.textbbox((0, 0), size_text, font=detail_font)
            size_width = size_bbox[2] - size_bbox[0]
        else: # Fallback for default font
            size_width = len(size_text) * 8
        size_x = width - size_width - text_margin
        draw.text((size_x, banner_y + text_margin), size_text, fill=(100, 100, 100), font=detail_font)
    except Exception as e:
        # Fallback if textbbox fails for some reason
        st.warning(f"Could not use textbbox for size info: {e}. Using fallback position.")
        draw.text((width - 120, banner_y + text_margin), size_text, 
                  fill=(100, 100, 100), font=detail_font)
    
    return new_img

def save_images_to_temp_dir(extracted_images):
    """Save original extracted images to a temporary directory for PDF generation"""
    if not extracted_images:
        return None
        
    temp_dir = tempfile.mkdtemp()
    for img_info in extracted_images:
        img_path = os.path.join(temp_dir, img_info['filename'])
        # Use original_data here, not annotated data
        with open(img_path, 'wb') as f:
            f.write(img_info['original_data'])
    
    return temp_dir

def fix_markdown_tables(markdown_text):
    """Fix markdown table formatting issues, primarily by ensuring consistent column counts
       and removing malformed separator lines.
       This is a heuristic and might not catch all edge cases from LLM output.
    """
    lines = markdown_text.split('\n')
    corrected_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Detect a potential header line (starts and ends with '|', has content)
        if line.startswith('|') and line.endswith('|') and not re.match(r'^\|[-=\s]+\|([-=\s]+\|)*$', line):
            header_parts = [p.strip() for p in line.split('|') if p.strip()]
            if not header_parts: # Skip if no actual header content
                corrected_lines.append(lines[i])
                i += 1
                continue
            
            num_columns = len(header_parts)
            corrected_lines.append(line) # Add the header line as is
            
            # Look for the separator line immediately after
            if i + 1 < len(lines):
                separator_line = lines[i+1].strip()
                if re.match(r'^\|[-=\s]+\|([-=\s]+\|)*$', separator_line):
                    # Reconstruct a valid separator line with correct column count
                    corrected_separator = '|' + '|'.join(['-' * 3 for _ in range(num_columns)]) + '|'
                    corrected_lines.append(corrected_separator)
                    i += 2 # Skip original separator
                else:
                    # No separator or malformed, proceed to next line, assume header might be first row of data
                    i += 1
            else:
                i += 1 # End of lines after header
            
            # Now, process data rows until a non-table line is found
            while i < len(lines):
                data_line = lines[i].strip()
                if data_line.startswith('|') and data_line.endswith('|') and not re.match(r'^\|[-=\s]+\|([-=\s]+\|)*$', data_line):
                    data_parts = [p.strip() for p in data_line.split('|') if p.strip()]
                    
                    # Pad or truncate data parts to match header column count
                    if len(data_parts) < num_columns:
                        data_parts.extend([''] * (num_columns - len(data_parts)))
                    elif len(data_parts) > num_columns:
                        data_parts = data_parts[:num_columns]
                    
                    corrected_lines.append('|' + '|'.join(data_parts) + '|')
                    i += 1
                else:
                    # End of table, or a non-table line
                    if data_line: # If it's a non-empty line, add it
                        corrected_lines.append(lines[i])
                    i += 1
                    break # Exit table processing loop
        else:
            # Not a table line, add as is
            corrected_lines.append(lines[i])
            i += 1
            
    return '\n'.join(corrected_lines)


def sanitize_for_reportlab(text):
    """Sanitize text for ReportLab PDF generation, handling basic HTML tags and converting
       explicit HTML bold/italic tags to ReportLab's expected format.
    """
    text = str(text)
    
    # Step 1: Handle line breaks first, as they are part of markdown structure
    text = re.sub(r'\n', '<br/>', text)
    
    # Step 2: Convert literal HTML bold/italic tags to ReportLab's expected format
    # This must happen BEFORE the general escape, otherwise '<' and '>' will become &lt; &gt;
    text = re.sub(r'<b>(.*?)</b>', r'<b>\1</b>', text, flags=re.IGNORECASE) # Replaces <b> with <b> (noop for now, but conceptual)
    text = re.sub(r'<strong>(.*?)</strong>', r'<b>\1</b>', text, flags=re.IGNORECASE)
    text = re.sub(r'<i>(.*?)</i>', r'<i>\1</i>', text, flags=re.IGNORECASE)
    text = re.sub(r'<em>(.*?)</em>', r'<i>\1</i>', text, flags=re.IGNORECASE)

    # Step 3: Escape other XML/HTML special characters
    # This prevents any *other* user-entered '<' or '>' from being interpreted as tags
    text = escape(text) 

    # Step 4: Convert markdown bold/italic syntax to ReportLab's expected format
    # This must happen *after* escape() for ReportLab to interpret them if the markdown itself was escaped
    # However, if markdown came raw, and not via LLM output that preserves markdown, this applies.
    # Given the previous step converts HTML tags, this one handles markdown that wasn't converted to HTML by LLM
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text) # Markdown bold **text**
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text) # Markdown bold __text__
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text) # Markdown italic *text*
    text = re.sub(r'_(.*?)_', r'<i>\1</i>', text) # Markdown italic _text_

    return text

def generate_pdf_from_markdown(content, temp_image_dir=None):
    """Generate PDF from markdown content with optional images"""
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.7*inch, rightMargin=0.7*inch, topMargin=0.7*inch, bottomMargin=0.7*inch)
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(name='DocTitle', parent=styles['h1'], fontSize=20, leading=26, fontName='Helvetica-Bold', spaceAfter=14, textColor=colors.darkblue)
        section_style = ParagraphStyle(name='Section', parent=styles['h2'], fontSize=11, leading=14, fontName='Helvetica-Bold', textColor=colors.darkblue, spaceBefore=12, spaceAfter=8)
        subsection_style = ParagraphStyle(name='SubSection', parent=styles['h3'], fontSize=10, leading=12, fontName='Helvetica-Bold', textColor=colors.black, spaceBefore=10, spaceAfter=4)
        normal_style = ParagraphStyle(name='Normal', parent=styles['Normal'], fontSize=9, leading=12, fontName='Helvetica', spaceAfter=6)
        list_style = ParagraphStyle(name='List', parent=normal_style, leftIndent=18)
        
        # Enhanced Table Style for better visibility and structure
        table_style_config = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.1, 0.4, 0.6)), # Darker blue header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10), # Increased padding
            ('TOPPADDING', (0, 0), (-1, 0), 10),    # Increased padding
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.Color(0.95, 0.95, 0.95), colors.white]), # Subtle alternating rows
            ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)), # Lighter grid lines
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ])

        lines = content.split('\n')
        if lines and lines[0].startswith('# '):
            doc_title = lines.pop(0)[2:].strip()
            elements.append(Paragraph(sanitize_for_reportlab(doc_title), title_style))
            elements.append(Spacer(1, 18))

        in_table = False
        table_data = []
        current_num_columns = 0 # Track column count for the current table

        def build_table(data, num_cols):
            if not data or num_cols == 0: return None
            try:
                # Ensure all rows have the same number of columns
                cleaned_data = []
                for row in data:
                    if len(row) < num_cols:
                        cleaned_data.append(row + [''] * (num_cols - len(row)))
                    else:
                        cleaned_data.append(row[:num_cols]) # Trim if too many columns

                page_width = A4[0] - (doc.leftMargin + doc.rightMargin)
                
                # Calculate column widths more robustly, ensuring total width
                # Use a simple equal distribution if header lengths are not reliable for proportional sizing
                col_widths = [page_width / num_cols] * num_cols

                wrapped_data = [[Paragraph(sanitize_for_reportlab(cell), normal_style) for cell in row] for row in cleaned_data]
                
                table = Table(wrapped_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(table_style_config)
                return KeepTogether(table)
            except Exception as e:
                st.warning(f"Could not build table. Error: {e}")
                st.warning(f"Table data that caused error: {data}") # Log the problematic data
                return None

        for line_idx, line in enumerate(lines):
            stripped_line = line.strip()

            # Check for image references in markdown
            if temp_image_dir and stripped_line.startswith('![') and '](' in stripped_line and ')' in stripped_line:
                if in_table: # If an image breaks a table, render the current table first
                    table_obj = build_table(table_data, current_num_columns)
                    if table_obj: elements.append(table_obj)
                    in_table = False
                    table_data = []
                    current_num_columns = 0
                    
                img_match = re.search(r'!\[.*?\]\((.*?)\)', stripped_line)
                if img_match:
                    img_filename = img_match.group(1)
                    img_path = os.path.join(temp_image_dir, img_filename)
                    if os.path.exists(img_path):
                        try:
                            image_info = next((img for img in st.session_state.extracted_images if img['filename'] == img_filename), None)
                            if image_info:
                                original_width = image_info['width']
                                original_height = image_info['height']
                            else: # Fallback if image_info not found
                                with Image.open(img_path) as temp_img:
                                    original_width, original_height = temp_img.size

                            max_width_pdf = 5*inch
                            max_height_pdf = 4*inch
                            
                            width_scale = max_width_pdf / original_width
                            height_scale = max_height_pdf / original_height
                            scale_factor = min(width_scale, height_scale, 1.0)
                            
                            final_width = original_width * scale_factor
                            final_height = original_height * scale_factor

                            img = RLImage(img_path, width=final_width, height=final_height)
                            elements.append(img)
                            elements.append(Spacer(1, 12))
                            continue # Move to next line in source
                        except Exception as e:
                            st.warning(f"Could not add image {img_filename} to PDF: {e}")

            # Check if line looks like a table separator, e.g., |---|---|
            is_separator_line = re.match(r'^\|[-=\s]+\|([-=\s]+\|)*$', stripped_line)

            # Table parsing logic
            if stripped_line.startswith('|') and stripped_line.endswith('|'):
                if is_separator_line:
                    # If we encounter a separator line within a table, it signifies the end of the header
                    # or the end of a section within a table. For simplicity, we'll treat it as
                    # a potential end of the current table block or just ignore if already in data rows.
                    if in_table and len(table_data) > 0: # Only if we have actual data before it
                         # We've processed the header and now the separator. Don't add separator data.
                         # Just continue to process data rows.
                        pass
                    elif not in_table: # If not in table yet, this is likely part of a malformed table.
                        # Try to infer columns from the separator itself if no header was found yet.
                        parts = [p.strip() for p in stripped_line.split('|') if p.strip()]
                        if parts and current_num_columns == 0:
                            current_num_columns = len(parts)
                        in_table = True # Indicate we are now parsing a table
                    continue # Skip adding the separator line itself as a paragraph

                # This is a potential data/header row
                row_cells = [cell.strip() for cell in stripped_line.split('|') if cell.strip() != '']
                
                if row_cells: # Only add if there are actual cells
                    if not in_table:
                        in_table = True
                        table_data = [] # Start new table data
                        current_num_columns = len(row_cells) # Set column count from first data row
                    
                    # Ensure consistency: if a row has different column count, force new table
                    if current_num_columns != len(row_cells) and len(table_data) > 0:
                        # Staggered column count, finalize previous table and start new one
                        table_obj = build_table(table_data, current_num_columns)
                        if table_obj: elements.append(table_obj)
                        elements.append(Spacer(1, 6)) # Small space between tables

                        table_data = []
                        current_num_columns = len(row_cells) # Reset column count for new table
                        in_table = True
                    
                    table_data.append(row_cells)
                continue # Processed as table row, move to next line

            # If we were in a table and current line is not a table line
            if in_table:
                table_obj = build_table(table_data, current_num_columns)
                if table_obj: elements.append(table_obj)
                elements.append(Spacer(1, 6)) # Add a small spacer after table
                in_table = False
                table_data = []
                current_num_columns = 0
            
            # Process other markdown elements
            if stripped_line.startswith('## '):
                elements.append(Paragraph(sanitize_for_reportlab(stripped_line[3:].strip().upper()), section_style))
            elif stripped_line.startswith('### '):
                elements.append(Paragraph(sanitize_for_reportlab(stripped_line[4:].strip()), subsection_style))
            elif stripped_line.startswith(('* ', '- ')): # Handles simple list items
                # Check for indentation for nested lists
                indent_level = len(line) - len(line.lstrip()) # original line to get leading spaces
                if indent_level > 0 and len(stripped_line) > 2:
                    # Create a specific style for indented lists
                    nested_list_style = ParagraphStyle(name=f'NestedList{indent_level}', parent=list_style, leftIndent=list_style.leftIndent + indent_level * 12)
                    elements.append(Paragraph(f"• {sanitize_for_reportlab(stripped_line[2:])}", nested_list_style))
                else:
                    elements.append(Paragraph(f"• {sanitize_for_reportlab(stripped_line[2:])}", list_style))
            elif stripped_line: # Any other non-empty line becomes a normal paragraph
                elements.append(Paragraph(sanitize_for_reportlab(stripped_line), normal_style))
        
        # If the document ends with a table, ensure it's built
        if in_table:
            table_obj = build_table(table_data, current_num_columns)
            if table_obj: elements.append(table_obj)

        # Add images at the end if not referenced explicitly in markdown above or not all were
        if temp_image_dir and st.session_state.extracted_images:
            elements.append(Spacer(1, 24))
            elements.append(Paragraph("TECHNICAL DIAGRAMS AND IMAGES", section_style))
            elements.append(Spacer(1, 12))
            
            for i, img_info in enumerate(st.session_state.extracted_images):
                # Check if this image was already added via markdown reference
                # This simple check assumes unique filenames; more robust would be to track added images
                # For now, just add all images at the end if not already processed in-line.
                # A better approach would be to track if an image was inserted and only insert un-inserted ones here.
                # For this example, we'll just add them all here if the temp_image_dir is set,
                # as the markdown image processing `continue` skips this for those images.
                
                img_path = os.path.join(temp_image_dir, img_info['filename'])
                if os.path.exists(img_path):
                    try:
                        img_table_data = []
                        desc_header = f"Figure {i+1}: {img_info['label']['description']}"
                        img_table_data.append([Paragraph(f"<b>{sanitize_for_reportlab(desc_header)}</b>", subsection_style)])
                        
                        original_width = img_info['width']
                        original_height = img_info['height']
                        
                        max_width = 5*inch
                        max_height = 4*inch
                        
                        width_scale = max_width / original_width
                        height_scale = max_height / original_height
                        scale_factor = min(width_scale, height_scale, 1.0)
                        
                        final_width = original_width * scale_factor
                        final_height = original_height * scale_factor
                        
                        img = RLImage(img_path, width=final_width, height=final_height)
                        img_table_data.append([img])
                        
                        details_text = f"<b>Purpose:</b> {sanitize_for_reportlab(img_info['label']['purpose'])}<br/><b>Original Size:</b> {sanitize_for_reportlab(img_info['label']['pinpoint_size'])}"
                        img_table_data.append([Paragraph(details_text, normal_style)])
                        
                        img_table = Table(img_table_data, colWidths=[6*inch]) # Fixed width for image table
                        img_table.setStyle(TableStyle([
                            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                            ('TOPPADDING', (0, 0), (-1, -1), 8),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                            ('LEFTPADDING', (0, 0), (-1, -1), 12),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
                            ('BOX', (0, 0), (-1, -1), 1, colors.lightgrey),
                            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.95, 0.95, 0.95)),
                            ('BACKGROUND', (0, 2), (-1, 2), colors.Color(0.98, 0.98, 0.98)),
                        ]))
                        
                        elements.append(KeepTogether(img_table))
                        elements.append(Spacer(1, 18))
                        
                    except Exception as e:
                        st.warning(f"Could not add image {img_info['filename']} to PDF: {e}")
                        placeholder_text = f"[Image: {sanitize_for_reportlab(img_info['label']['description'])} - {sanitize_for_reportlab(img_info['label']['pinpoint_size'])}]"
                        elements.append(Paragraph(placeholder_text, normal_style))
                        elements.append(Spacer(1, 12))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        st.error(traceback.format_exc())
        return None

def get_gemini_response(user_input, pdf_text):
    """Get response from Gemini API for specification generation"""
    prompt = f"""
    You are an expert engineering assistant. Your task is to generate a new, complete datasheet for a different product model based on the user's request, using the provided PDF text as a reference.

    **CRITICAL Instructions:**
    1.  **Analyze Source:** Read the "Source PDF Text" to understand its structure, formatting, and technical parameters.
    2.  **Identify Target:** Determine the new product model from the "User Query".
    3.  **Scale ALL Parameters Logically:**
        * **Electrical:** Intelligently extrapolate specifications. If the source is a 300W power supply and the target is 700W, proportionally scale power, current, etc. Keep constant parameters like input voltage range. For ranges (e.g., 187 to 264 VAC), keep them unless specific scaling is implied.
        * **Physical:** You **MUST** logically scale physical properties. A higher power unit should be larger and heavier. Estimate new dimensions (Length, Width, Height) and Weight, and state your reasoning in parentheses, e.g., "(Dimensions scaled proportionally to the ~133% increase in power)". **Do not assume physical properties are identical.** If a value is a single number, scale it; if it's a range, scale the upper and lower bounds if logical, or keep as is if it's a fixed standard range.

    4.  **Maintain Structure:** Replicate the *exact* section structure of the source. Generate content for every single section.
    
    5.  **CRITICAL RULE: NO PLACEHOLDERS OR SUMMARIES.** This is a non-negotiable rule. Your output **MUST** be a complete, standalone document. You are **strictly forbidden** from using summary phrases like 'This section remains the same as the source document,' 'Details are as per the original,' or '(Identical to source, no changes needed)'. You **MUST** generate the full content for every section by either scaling the data or copying the original content verbatim if it is identical.
    
    6.  **Format as Markdown:** The entire output must be clean markdown. Use '#', '##', '###' for titles and headers.
    
    7.  **Table Formatting Rule:** It is critical that **every row in a single markdown table block has the exact same number of columns**. If you need to present data with different column structures, you **MUST** start a new, separate table. Ensure the header line separator (e.g., `|---|---|`) is correctly formed with `|` at the start and end and matching the number of columns.
    
    8.  **Image References:** If there were technical diagrams, charts, or images in the original document, reference them appropriately in your generated content. Use markdown image syntax `![Description](image_filename.png)` where `image_filename.png` should match an extracted image's filename (e.g., `extracted_image_1.png`). If the document has multiple images, try to reference them contextually.

    ---
    **Source PDF Text:**
    ```
    {pdf_text}
    ```
    ---
    **User Query:**
    "{user_input}"
    ---
    **Generated Markdown Datasheet for the Target Product:**
    """
    try:
        response = st.session_state.conversation.send_message(prompt)
        return response.text
    except Exception as e:
        st.error(f"An error occurred with the Gemini API: {e}")
        return f"Error: Could not get a response from the model. Details: {e}"

# --- Sidebar ---
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    
    # Image extraction controls
    st.markdown("### Image Extraction Settings")
    min_width = st.slider("Minimum Image Width (pixels)", 50, 1000, 150)
    min_height = st.slider("Minimum Image Height (pixels)", 50, 1000, 150)
    min_kb = st.slider("Minimum File Size (KB)", 1, 100, 15)
    
    if st.button("🔄 Clear All & Reset", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key != "conversation": # Keep conversation model initialized
                del st.session_state[key]
        st.rerun()

    st.markdown("---")
    st.markdown("### About This App")
    st.markdown("This enhanced tool combines image extraction with AI-powered specification generation using Google's API and OpenAI's GPT-4 Vision.")
    st.markdown("For bug reports or feature requests, contact [Your Name/Org].")


# --- Main Application Logic ---

# Step 1: Upload PDF
with st.expander("Step 1: Upload a Source PDF", expanded=not st.session_state.pdf_text):
    uploaded_file = st.file_uploader("Upload a product PDF", type=["pdf"], label_visibility="collapsed")
    
    if uploaded_file:
        # Check if a new file is uploaded or if it's the same file but not processed yet
        if st.session_state.uploaded_file_object is None or \
           st.session_state.uploaded_file_object.name != uploaded_file.name or \
           st.session_state.uploaded_file_object.size != uploaded_file.size:
            
            st.session_state.uploaded_file_object = uploaded_file # Store the file object

            with st.spinner("Analyzing PDF and extracting images... This may take a moment."):
                pdf_bytes = uploaded_file.getvalue()
                
                # Extract text
                st.session_state.pdf_text = extract_pdf_text(io.BytesIO(pdf_bytes)) # Pass BytesIO for PyPDF2
                
                # Extract images
                st.session_state.extracted_images = extract_images_from_pdf(
                    pdf_bytes, min_width, min_height, min_kb
                )
                
                # Save images to temp directory
                if st.session_state.extracted_images:
                    st.session_state.temp_image_dir = save_images_to_temp_dir(st.session_state.extracted_images)
                
                if st.session_state.pdf_text:
                    st.success(f"PDF analyzed successfully! Found {len(st.session_state.extracted_images)} useful images.")
                    # Clear chat history for new PDF
                    st.session_state.chat_history = [] 
                    st.rerun()
                else:
                    st.error("Failed to extract any text from the PDF.")
    elif st.session_state.uploaded_file_object and not st.session_state.pdf_text:
        # This case happens if a file was uploaded, but text extraction failed.
        st.warning("Please upload a PDF to start or check the previous error messages.")


# Step 2: Display extracted images
if st.session_state.extracted_images:
    with st.expander(f"Step 2: Review Extracted Images ({len(st.session_state.extracted_images)} found)", expanded=True):
        # Create download for images
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for img_info in st.session_state.extracted_images:
                zf.writestr(img_info['filename'], img_info['data'])
        
        zip_bytes = zip_buffer.getvalue()
        if zip_bytes:
            st.download_button(
                label="📥 Download All Extracted Images (.zip)",
                data=zip_bytes,
                file_name="extracted_images.zip",
                mime="application/zip"
            )
        
        st.markdown("### Extracted Images with AI Analysis")
        
        # Display images in a more organized way
        for i, img_info in enumerate(st.session_state.extracted_images):
            with st.container(border=True): # Use Streamlit container for visual grouping
                col1, col2 = st.columns([1, 2])
                
                with col1:
                    # Display the annotated image
                    st.image(img_info['data'], caption=f"Figure {i+1}", use_column_width=True)
                    
                    # Image metadata
                    st.markdown(f"""
                    <div style="background-color: #e0e7ee; padding: 10px; border-radius: 5px; margin-top: 5px;">
                        <small>
                        <b>📐 Size:</b> {img_info['label']['pinpoint_size']}<br/>
                        <b>📁 File:</b> {img_info['filename']}<br/>
                        <b>💾 Size:</b> {len(img_info['original_data'])/1024:.1f} KB (Original)
                        </small>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # Image analysis details
                    st.markdown(f"#### {img_info['label']['description']}")
                    
                    st.markdown(f"""
                    **🎯 Purpose in Document:** {img_info['label']['purpose']}
                    
                    **🔍 AI Analysis:** This image was automatically analyzed and labeled using GPT-4 Vision based on the document context. 
                    The AI identified this as a technical element that supports the document's content.
                    """)
                    
                    # Option to download individual image
                    st.download_button(
                        label=f"⬇️ Download {img_info['filename']}",
                        data=img_info['data'],
                        file_name=img_info['filename'],
                        mime="image/png", # assuming png for annotated images
                        key=f"download_{i}"
                    )
                

# Step 3: Generate specifications
st.markdown("---")
st.markdown("### Step 3: Generate New Product Specifications")

# Display chat messages from history
for chat in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(chat["user"])
    with st.chat_message("assistant"):
        st.markdown(chat["bot"])
        if chat.get("pdf_data"):
            st.download_button(
                label=f"⬇️ Download {chat.get('filename', 'specs.pdf')}",
                data=chat["pdf_data"],
                file_name=chat.get('filename', 'generated_specs.pdf'),
                mime="application/pdf"
            )

# Accept user input
if user_input := st.chat_input("e.g., Generate specs for the LCM700 model", disabled=not st.session_state.pdf_text):
    # Append user query to chat history
    st.session_state.chat_history.append({"user": user_input, "bot": "Thinking..."})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Generating specifications with extracted images..."):
            raw_response_text = get_gemini_response(user_input, st.session_state.pdf_text)
            
            bot_message = ""
            pdf_data = None
            filename = "generated_specs.pdf"

            if raw_response_text.startswith("Error:"):
                bot_message = raw_response_text
            else:
                # Apply table fixing before PDF generation
                fixed_response_text = fix_markdown_tables(raw_response_text)
                
                pdf_data = generate_pdf_from_markdown(fixed_response_text, st.session_state.temp_image_dir)
                
                if pdf_data:
                    bot_message = f"I have generated the datasheet you requested with {len(st.session_state.extracted_images)} extracted images included. The document formatting has been enhanced for a professional layout. You can download it below."
                    target_model_match = re.search(r'([A-Za-z0-9-]+[1-9]00[A-Za-z0-9-]*W?)', user_input, re.IGNORECASE)
                    if target_model_match:
                        # Extract a cleaner model name for filename
                        model_name = target_model_match.group(1).replace(' ', '_').replace('-', '_').lower()
                        filename = f"{model_name}_specs_with_images.pdf"
                else:
                    bot_message = f"I tried to automatically format the document, but there was an error creating the PDF. Here is the raw markdown for review:\n\n---\n\n```markdown\n{raw_response_text}\n```"
            
            st.markdown(bot_message)
            if pdf_data:
                st.download_button(
                    label=f"⬇️ Download {filename}",
                    data=pdf_data,
                    file_name=filename,
                    mime="application/pdf"
                )
            
            # Update the last entry in chat history with the actual bot response and PDF data
            st.session_state.chat_history[-1]["bot"] = bot_message
            st.session_state.chat_history[-1]["pdf_data"] = pdf_data
            st.session_state.chat_history[-1]["filename"] = filename

# --- Additional Features ---
if st.session_state.pdf_text:
    st.markdown("---")
    st.markdown("### Additional Options")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Re-extract only if a file was previously uploaded
        if st.session_state.uploaded_file_object:
            if st.button("🔍 Re-extract Images with New Settings"):
                with st.spinner("Re-extracting images with new settings..."):
                    pdf_bytes = st.session_state.uploaded_file_object.getvalue()
                    st.session_state.extracted_images = extract_images_from_pdf(
                        pdf_bytes, min_width, min_height, min_kb
                    )
                    if st.session_state.extracted_images:
                        st.session_state.temp_image_dir = save_images_to_temp_dir(st.session_state.extracted_images)
                    st.success(f"Re-extracted {len(st.session_state.extracted_images)} images with new settings!")
                    st.rerun()
        else:
            st.button("🔍 Re-extract Images with New Settings", disabled=True, help="Upload a PDF first.")
            
    with col2:
        if st.button("📊 Show PDF Text Summary"):
            if st.session_state.pdf_text:
                text_length = len(st.session_state.pdf_text)
                word_count = len(st.session_state.pdf_text.split())
                st.info(f"**PDF Text Stats:**\n- Characters: {text_length:,}\n- Words: {word_count:,}\n- Images: {len(st.session_state.extracted_images)}")
                
                with st.expander("View Full Extracted Text"):
                    st.text_area("Extracted PDF Text", st.session_state.pdf_text, height=300, disabled=True)
            else:
                st.info("No PDF text extracted yet. Please upload a PDF.")

# --- Footer ---
st.markdown("---")
st.markdown("""
    <div style="text-align: center; color: #666; font-size: 0.9rem;">
    Enhanced PDF Specification Generator - Created with ❤️ using Gemini & OpenAI APIs
    </div>
""", unsafe_allow_html=True)