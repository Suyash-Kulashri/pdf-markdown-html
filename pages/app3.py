import traceback
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
import PyPDF2
from pdf2image import convert_from_bytes
import pytesseract
import io
import re
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem, KeepTogether
from reportlab.lib import colors
import markdown

# Load environment variables from .env file
load_dotenv()

# Validate OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("OpenAI API key is missing in .env file. Please provide a valid key.")
    st.stop()
os.environ["OPENAI_API_KEY"] = api_key

# Set wide layout
st.set_page_config(layout="wide", page_title="Product Series Specification Query", page_icon=":document:")

# Custom CSS for Streamlit app (for UI elements, not HTML content)
st.markdown("""
    <style>
    .chat-container {
        margin-bottom: 100px;
    }
    .user-message {
        background-color: #f0f2f6;
        color: #1e293b;
        padding: 12px 16px;
        border-radius: 18px 18px 4px 18px;
        margin: 8px 15% 8px 0;
        max-width: 85%;
        word-wrap: break-word;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
    }
    .bot-message {
        background-color: #ffffff;
        color: #1e293b;
        padding: 12px 16px;
        border-radius: 18px 18px 18px 4px;
        margin: 8px 0 8px 15%;
        max-width: 85%;
        word-wrap: break-word;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        border: 1px solid #e2e8f0;
    }
    .input-container {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background-color: #ffffff;
        padding: 16px;
        display: flex;
        align-items: center;
        z-index: 1000;
        box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        border-top: 1px solid #e2e8f0;
    }
    .stTextInput > div > div > input {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 24px;
        color: #1e293b;
        padding: 12px 20px;
        width: 100%;
        margin-right: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        transition: all 0.3s;
    }
    .stTextInput > div > div > input:focus {
        border-color: #6366f1;
        box-shadow: 0 0 0 2px rgba(99,102,241,0.2);
    }
    .stTextInput > div > div > input::placeholder {
        color: #94a3b8;
        opacity: 1;
    }
    .stButton > button {
        background: linear-gradient(90deg, #6366f1, #8b5cf6);
        border: none;
        border-radius: 24px;
        color: white;
        padding: 12px 24px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.3s;
        height: 48px;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #4f46e5, #7c3aed);
        transform: translateY(-1px);
    }
    .stButton > button:active {
        transform: translateY(0);
    }
    .stFileUploader > div > div > div {
        background-color: #ffffff;
        border: 1px dashed #e2e8f0;
        border-radius: 12px;
        padding: 16px;
        color: #64748b;
        transition: all 0.3s;
    }
    .stFileUploader > div > div > div:hover {
        border-color: #6366f1;
    }
    .stDownloadButton > button {
        background: linear-gradient(90deg, #10b981, #34d399);
        border: none;
        border-radius: 24px;
        color: white;
        padding: 12px 24px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.3s;
        margin-top: 16px;
    }
    .stDownloadButton > button:hover {
        background: linear-gradient(90deg, #059669, #10b981);
        transform: translateY(-1px);
    }
    </style>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        const input = document.querySelector('input');
        input.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.querySelector('button').click();
            }
        });
        input.focus();
    });
    </script>
""", unsafe_allow_html=True)

# Initialize session state
if "spec_conversation" not in st.session_state:
    st.session_state.spec_conversation = None
if "spec_chat_history" not in st.session_state:
    st.session_state.spec_chat_history = []
if "spec_input_key" not in st.session_state:
    st.session_state.spec_input_key = 0
if "spec_pdf_text" not in st.session_state:
    st.session_state.spec_pdf_text = ""
if "spec_pdf_response" not in st.session_state:
    st.session_state.spec_pdf_response = None
if "spec_raw_response" not in st.session_state:
    st.session_state.spec_raw_response = ""
if "spec_html_response" not in st.session_state:
    st.session_state.spec_html_response = ""
if "spec_processed_response" not in st.session_state:
    st.session_state.spec_processed_response = False  # New flag to prevent duplicate processing

# Function to extract text from PDF
def extract_pdf_text(uploaded_file):
    try:
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = ""
        for page in pdf_reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        if not text.strip():
            # Fallback to OCR
            try:
                images = convert_from_bytes(uploaded_file.getvalue())
                for image in images:
                    text += pytesseract.image_to_string(image) + "\n"
            except Exception as ocr_error:
                st.error(f"OCR extraction failed: {str(ocr_error)}")
        if not text.strip():
            st.error("No text could be extracted from the PDF. It may be a scanned image or empty.")
            return ""
        return text
    except Exception as e:
        st.error(f"Error reading PDF: {str(e)}\nDetails: {traceback.format_exc()}")
        return ""

# Function to convert markdown to styled HTML using pdf_styles.css
def markdown_to_html(markdown_text):
    # Convert markdown to HTML
    html = markdown.markdown(markdown_text, extensions=['tables'])
    # Embed CSS from pdf_styles.css
    css = """
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            background-color: #f4f4f4;
            color: #333;
            margin-left: 150px;
            margin-right: 150px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        header {
            color: #fff;
            padding: 20px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }
        h1 {
            margin: 0;
            font-size: 2.5em;
            color: #004080;
            font-weight: bold;
            background-color: #dfdfdd;
        }
        .section {
            background: #fff;
            margin: 20px 0;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        h2 {
            color: #004080;
            border-bottom: 2px solid #004080;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        h3 {
            color: rgb(133, 131, 131);
            margin-top: 0px;
            background-color: #dfdfdd;
            font-size: medium;
            font-weight: normal;
        }
        table {
            width: 70%;
            border-collapse: collapse;
            margin: 30px auto;
        }
        table, th, td {
            border: 1px solid #000000;
        }
        th, td {
            padding: 12px;
            text-align: center;
        }
        th {
            background-color: #004080;
            color: #fff;
        }
        tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        ul {
            list-style-type: disc;
            margin: 15px 0;
            padding-left: 20px;
        }
        .footer {
            text-align: center;
            padding: 20px;
            background: #004080;
            color: #fff;
            border-radius: 0 0 8px 8px;
            margin-top: 20px;
            font-size: 12pt;
        }
        .footer a {
            color: #ffd700;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
        .note {
            background: #e6f3ff;
            padding: 10px;
            border-left: 4px solid #004080;
            margin: 10px 0;
        }
        .image-placeholder {
            background: #eee;
            padding: 20px;
            text-align: center;
            margin: 20px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            align-items: center;
        }
        .image-placeholder p {
            margin: 0;
            font-style: italic;
            align-items: center;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 0 auto;
            align-items: center;
        }
        pre {
            background: #f9f9f9;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
        strong {
            color: #004080;
        }
        .image-row {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin: 20px 0;
            flex-wrap: wrap;
        }
        .image-row img {
            max-width: 30%;
            height: auto;
            display: block;
            margin: 0 auto;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
    """
    # Wrap HTML in styled container
    styled_html = f"""
    <html>
    <head>
        <style>{css}</style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>Artesyn LCM700 Series Datasheet</h1>
            </header>
            {html}
            <div class="footer">
                Generated by Product Specification Generator | <a href="https://www.advancedenergy.com">Advanced Energy</a>
            </div>
        </div>
    </body>
    </html>
    """
    return styled_html

# Function to generate PDF with styling from pdf_styles.css
def generate_pdf(content, filename="lcm_specs.pdf"):
    try:
        # Initialize PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
        elements = []

        # Define styles to match pdf_styles.css, fallback to Helvetica if Arial unavailable
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name='Title',
            fontSize=25,
            leading=30,
            spaceAfter=12,
            fontName='Helvetica',  # Changed to Helvetica for wider compatibility
            textColor=colors.Color(0, 0.25, 0.5),  # #004080
            backColor=colors.Color(0.8745, 0.8745, 0.8667),  # #dfdfdd
            alignment=1,  # Center
        )
        section_style = ParagraphStyle(
            name='Section',
            fontSize=14,
            leading=18,
            spaceAfter=20,
            spaceBefore=20,
            fontName='Helvetica',
            textColor=colors.Color(0, 0.25, 0.5),  # #004080
            borderWidth=2,
            borderColor=colors.Color(0, 0.25, 0.5),
            borderPadding=(0, 0, 10, 0),  # Bottom border
        )
        subsection_style = ParagraphStyle(
            name='SubSection',
            fontSize=12,
            leading=16,
            spaceAfter=8,
            fontName='Helvetica',
            textColor=colors.Color(0.5216, 0.5137, 0.5137),  # rgb(133, 131, 131)
            backColor=colors.Color(0.8745, 0.8745, 0.8667),  # #dfdfdd
            fontWeight='normal',
        )
        normal_style = ParagraphStyle(
            name='Normal',
            fontSize=10,
            leading=14,
            spaceAfter=6,
            fontName='Helvetica',
            textColor=colors.Color(0.2, 0.2, 0.2),  # #333
        )
        bold_style = ParagraphStyle(
            name='Bold',
            fontSize=10,
            leading=14,
            spaceAfter=6,
            fontName='Helvetica-Bold',
            textColor=colors.Color(0, 0.25, 0.5),  # #004080
        )
        note_style = ParagraphStyle(
            name='Note',
            fontSize=10,
            leading=14,
            spaceAfter=6,
            fontName='Helvetica',
            backColor=colors.Color(0.902, 0.953, 1),  # #e6f3ff
            borderWidth=4,
            borderColor=colors.Color(0, 0.25, 0.5),  # #004080
            borderPadding=(0, 0, 0, 10),  # Left border
            leftIndent=10,
            rightIndent=10,
            topPadding=10,
            bottomPadding=10,
        )
        footer_style = ParagraphStyle(
            name='Footer',
            fontSize=12,
            leading=14,
            fontName='Helvetica',
            textColor=colors.white,
            backColor=colors.Color(0, 0.25, 0.5),  # #004080
            alignment=1,  # Center
            spaceBefore=20,
        )
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0, 0.25, 0.5)),  # #004080
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.Color(0.2, 0.2, 0.2)),  # #333
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
            ('SPLITBYROW', (0, 0), (-1, -1), True),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.Color(0.975, 0.975, 0.975)]),  # #f9f9f9 for even rows
        ])

        # Add header
        elements.append(Paragraph("Artesyn LCM700 Series Datasheet", title_style))
        elements.append(Spacer(1, 12))

        # Parse markdown content
        lines = content.split('\n')
        current_list = None
        table_data = None
        table_headers = None
        max_col_widths = []

        def parse_bold(text):
            parts = []
            while '**' in text:
                start = text.find('**')
                end = text.find('**', start + 2)
                if end == -1:
                    parts.append(Paragraph(text, normal_style))
                    return parts
                if start > 0:
                    parts.append(Paragraph(text[:start], normal_style))
                bold_text = text[start+2:end]
                parts.append(Paragraph(bold_text, bold_style))
                text = text[end+2:]
            if text:
                parts.append(Paragraph(text, normal_style))
            return parts

        for line in lines:
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 6))
                continue

            # Sanitize special characters
            line = re.sub(r'([%#$&_{}\[\]])', r'\\\1', line)
            line = line.replace('≤', '≤').replace('±', '±').replace('μ', 'μ').replace('°', '°').replace('˚', '°')

            if line.startswith('## '):
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                elements.append(Spacer(1, 20))
                elements.append(Paragraph(line[3:].strip(), section_style))
                elements.append(Spacer(1, 20))
            elif line.startswith('### '):
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                elements.append(Paragraph(line[4:].strip(), subsection_style))
            elif line.startswith('- **') and line.endswith('**'):
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                bold_text = line[4:-2].strip()
                elements.append(Paragraph(bold_text, bold_style))
            elif line.startswith('- '):
                if not current_list:
                    current_list = []
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                list_text = line[2:].strip()
                if '**' in list_text:
                    for part in parse_bold(list_text):
                        current_list.append(ListItem(part))
                else:
                    current_list.append(ListItem(Paragraph(list_text, normal_style)))
            elif line.startswith('|'):
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if not table_data:
                    table_data = []
                cols = [col.strip() for col in line.split('|')[1:-1] if col.strip()]
                if not table_headers and cols:
                    table_headers = cols
                    table_data.append(cols)
                elif table_headers and len(cols) == len(table_headers):
                    table_data.append(cols)
            elif line.lower().startswith('note:'):
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                elements.append(Paragraph(line[5:].strip(), note_style))
            elif line.startswith('!['):  # Handle image placeholders
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                placeholder_text = re.search(r'\[(.*?)\]', line).group(1) if re.search(r'\[(.*?)\]', line) else "Image Placeholder"
                elements.append(Paragraph(placeholder_text, note_style))
            elif line:
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                if '**' in cell:
                                    cell_parts = parse_bold(cell)
                                    wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                                else:
                                    wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append("")
                            wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                else:
                    if '**' in line:
                        for parts in parse_bold(line):
                            elements.append(parts)
                    else:
                        if line in ['Input', 'Output']:
                            elements.append(Paragraph(line.strip(), subsection_style))
                        else:
                            elements.append(Paragraph(line.strip(), normal_style))

        # Append any remaining list or table
        if current_list:
            elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
        if table_data and table_headers:
            if not max_col_widths:
                max_col_widths = [0.8*inch] * len(table_headers)
            for i, row in enumerate(table_data):
                for j, cell in enumerate(row):
                    cell = str(cell).strip()
                    if cell:
                        cell_width = max(0.5*inch, len(cell) * 0.025 * inch)
                        max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))
            total_width = sum(max_col_widths)
            max_page_width = 6.5*inch
            if total_width > max_page_width:
                scale_factor = max_page_width / total_width
                max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
            wrapped_table_data = []
            for i, row in enumerate(table_data):
                wrapped_row = []
                for j, cell in enumerate(row):
                    cell = str(cell).strip()
                    if cell:
                        if '**' in cell:
                            cell_parts = parse_bold(cell)
                            wrapped_row.append(cell_parts[0] if len(cell_parts) == 1 else cell_parts)
                        else:
                            wrapped_row.append(Paragraph(cell, normal_style))
                    else:
                        wrapped_row.append("")
                    wrapped_table_data.append(wrapped_row)
            table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True)
            elements.append(KeepTogether(table))

        # Add footer
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Generated by Product Specification Generator | Advanced Energy", footer_style))

        # Build PDF
        doc.build(elements)
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}\nDetails: {traceback.format_exc()}")
        return None

# Initialize the LLM and chain
@st.cache_resource
def get_conversation_chain():
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7)
    memory = ConversationBufferMemory(memory_key="history", input_key="input")
    prompt = PromptTemplate(
        input_variables=["input", "history", "pdf_text"],
        template="""You are a product specification expert for Advanced Energy power supplies. The user has uploaded a PDF with details about an Advanced Energy product, provided below as extracted text. Your task is to predict the specifications for another product in the series by analyzing the PDF text and scaling parameters proportionally (e.g., LCM700 should have ~700 W output if LCM500 has ~500 W/510 W). Use the exact section structure and formatting of the PDF, including:

- Introduction (a detailed description of the product series, its purpose, and key characteristics)
- Special Features (a comprehensive bullet list of unique features and benefits)
- Electrical Specifications (with subsections Input and Output, using tables for Output with precise values)
- Ordering Information (a detailed bullet list or table with model codes and options)
- Pin Assignment (text or table, marked as TBD with clear assumptions if unclear)
- Mechanical Drawings (detailed text with weight, dimensions, mounting details, etc., include a note like "Note: Refer to mechanical drawing for details" where appropriate)
- Accessories (a complete bullet list with part numbers and descriptions)
- About Advanced Energy (a thorough company description with its mission and expertise)

For each section, provide highly descriptive, accurate, and comprehensive specifications for the new product based on the PDF data. For example:
- Scale power output proportionally (e.g., increase by ~40% for LCM700 compared to LCM500).
- Adjust voltage ranges, current, efficiency, and other parameters logically, providing detailed reasoning for each adjustment.
- Maintain input voltage range (e.g., 90-264 VAC) unless specific differences are indicated in the PDF.
- Estimate weight and dimensions with precise calculations (e.g., proportional to power or size, with a clear explanation).
- For unavailable data (e.g., Pin Assignment details), mark as TBD and provide detailed assumptions based on industry standards or the product series.
- Include all sections, ensuring the structure matches the LCM500 PDF exactly, with no missing or abbreviated content.
- Ensure all specifications are as detailed as possible, including numerical values, ranges, conditions, and any relevant notes or assumptions (e.g., prefix notes with "Note:").
- Use markdown formatting with clear section headers (##, ###), bullet lists, and tables. For bold text, use **text** syntax where appropriate (e.g., in Special Features or Ordering Information). For image placeholders (e.g., mechanical drawings), use markdown like "![Mechanical Drawing](placeholder)" and note "Note: Refer to mechanical drawing for details".
- Do not include any introductory or extraneous text in the response, such as "Here's a detailed prediction..." or similar. Provide only the structured markdown content with section headers, bullet lists, and tables as specified.

If the user input is unrelated to predicting specifications, respond naturally, using the PDF only if relevant. Ensure the response is exhaustive, avoiding any vagueness or incomplete predictions, and include all relevant details to make the output as informative as possible.

PDF Text:
{pdf_text}

Conversation History: {history}
User Input: {input}
Assistant Response:"""
    )
    conversation = LLMChain(
        llm=llm,
        prompt=prompt,
        memory=memory,
        verbose=False  # Disabled verbose to reduce logging noise
    )
    return conversation

# Load or initialize conversation chain
if st.session_state.spec_conversation is None:
    st.session_state.spec_conversation = get_conversation_chain()

# Streamlit app layout
st.title("📄 Product Specification Generator")
st.markdown("""
    Upload a PDF for a product (e.g., LCM500) and ask for the specifications of the next product in its series (e.g., LCM700). 
    The response will be displayed as styled HTML and downloadable as a PDF matching the structure of the uploaded PDF.
""")

# PDF upload
with st.spinner("Extracting PDF text..."):
    uploaded_file = st.file_uploader("Upload Product PDF", type=["pdf"], accept_multiple_files=False)
    if uploaded_file:
        st.session_state.spec_pdf_text = extract_pdf_text(uploaded_file)
        if st.session_state.spec_pdf_text:
            st.success("PDF uploaded successfully!")
        else:
            st.warning("PDF text extraction failed. No response will be generated.")

# Chat history display
with st.container():
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    for chat in st.session_state.spec_chat_history[:-1]:  # Exclude the latest response to avoid duplication
        st.markdown(f'<div class="user-message"><strong>You:</strong> {chat["user"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="bot-message"><strong>Bot:</strong> {chat["bot"]}</div>', unsafe_allow_html=True)
        if chat.get("html_response"):
            st.markdown(f'<div class="bot-message">{chat["html_response"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Input container at bottom
with st.container():
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    cols = st.columns([8, 1])
    with cols[0]:
        user_input = st.text_input("Ask about the next product in the series:", key=f"input_{st.session_state.spec_input_key}", label_visibility="collapsed", placeholder="e.g., Specifications for LCM700")
    with cols[1]:
        send_button = st.button("Send")
    st.markdown('</div>', unsafe_allow_html=True)

# Sidebar clear chat history button
with st.sidebar:
    st.markdown("## Settings")
    if st.button("🔄 Clear Chat History", use_container_width=True):
        st.session_state.spec_chat_history = []
        st.session_state.spec_conversation.memory.clear()
        st.session_state.spec_pdf_text = ""
        st.session_state.spec_pdf_response = None
        st.session_state.spec_raw_response = ""
        st.session_state.spec_html_response = ""
        st.session_state.spec_processed_response = False
        st.session_state.spec_input_key += 1
        st.rerun()

# Handle user input
if send_button and user_input and not st.session_state.spec_processed_response:
    if not st.session_state.spec_pdf_text:
        st.error("Please upload a PDF with extractable text before submitting a query.")
    else:
        try:
            # Get response from the chain
            with st.spinner("Generating response..."):
                response_dict = st.session_state.spec_conversation({"input": user_input, "pdf_text": st.session_state.spec_pdf_text})
                response = response_dict.get('text', '') if isinstance(response_dict, dict) else str(response_dict)
            
            if not response.strip():
                st.error("LLM returned an empty response. Please check the input or try a different query.")
            else:
                # Store raw response
                st.session_state.spec_raw_response = response
                
                # Convert markdown to HTML
                html_response = markdown_to_html(response)
                st.session_state.spec_html_response = html_response
                
                # Generate PDF from response
                pdf_data = generate_pdf(response, filename="lcm_specs.pdf")
                if pdf_data:
                    st.session_state.spec_pdf_response = pdf_data
                    st.session_state.spec_chat_history.append({
                        "user": user_input,
                        "bot": "Response displayed below as HTML. Download PDF using the button.",
                        "html_response": html_response
                    })
                else:
                    st.session_state.spec_chat_history.append({
                        "user": user_input,
                        "bot": "Failed to generate PDF. HTML response displayed below.",
                        "html_response": html_response
                    })
                
                # Mark response as processed
                st.session_state.spec_processed_response = True
                
                # Clear input by updating key
                st.session_state.spec_input_key += 1
                
                # Rerun to update display
                st.rerun()
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}\nDetails: {traceback.format_exc()}")

# Display latest response
if st.session_state.spec_html_response and st.session_state.spec_processed_response:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    if st.session_state.spec_chat_history:
        latest_chat = st.session_state.spec_chat_history[-1]
        st.markdown(f'<div class="user-message"><strong>You:</strong> {latest_chat["user"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="bot-message"><strong>Bot:</strong> {latest_chat["bot"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="bot-message">{latest_chat["html_response"]}</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Display download button for PDF response
if st.session_state.spec_pdf_response:
    st.download_button(
        label="Download Response PDF",
        data=st.session_state.spec_pdf_response,
        file_name="lcm_specs.pdf",
        mime="application/pdf"
    )
elif st.session_state.spec_processed_response:
    st.warning("PDF generation failed. HTML response is available above.")
