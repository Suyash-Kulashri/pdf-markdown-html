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

# Custom CSS for styling
# Custom CSS for styling - Updated version
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
    .bot-message table {
        width: 100%;
        border-collapse: collapse;
        margin: 8px 0;
    }
    .bot-message table, .bot-message th, .bot-message td {
        border: 1px solid #e2e8f0;
    }
    .bot-message th {
        background-color: #f8fafc;
        padding: 8px;
    }
    .bot-message td {
        padding: 8px;
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
    .stMarkdown h1 {
        color: #1e293b;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 8px;
        margin-bottom: 16px;
    }
    .stMarkdown h2 {
        color: #1e293b;
        margin-top: 24px;
    }
    .stMarkdown h3 {
        color: #334155;
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

# Update the title section
st.title("📄 Product Specification Generator")
st.markdown("""
    <div style="color: #64748b; margin-bottom: 24px;">
    Upload a product PDF (e.g., LCM500) to generate specifications for other models in the series (e.g., LCM700).
    The AI will analyze the document and create a scaled version with consistent formatting.
    </div>
""", unsafe_allow_html=True)

# Update the sidebar
with st.sidebar:
    st.markdown("## Settings")
    if st.button("🔄 Clear Chat History", use_container_width=True):
        st.session_state.spec_chat_history = []
        st.session_state.spec_conversation.memory.clear()
        st.session_state.spec_pdf_text = ""
        st.session_state.spec_pdf_response = None
        st.session_state.spec_raw_response = ""
        st.session_state.spec_input_key += 1
        st.rerun()
    
    st.markdown("---")
    st.markdown("### About")
    st.markdown("""
        This tool helps engineers generate product specifications 
        for different models in the same product series by analyzing 
        an existing product datasheet.
    """)

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

# Function to generate PDF using reportlab with improved table handling
def generate_pdf(content, filename="lcm_specs.pdf"):
    try:
        # Initialize PDF buffer
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=0.75*inch, rightMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
        elements = []

        # Define styles to match LCM500 PDF
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(name='Title', parent=styles['Title'], fontSize=16, leading=20, spaceAfter=12, fontName='Helvetica-Bold')
        section_style = ParagraphStyle(name='Section', parent=styles['Heading1'], fontSize=14, leading=18, spaceAfter=10, fontName='Helvetica-Bold')
        subsection_style = ParagraphStyle(name='SubSection', parent=styles['Heading2'], fontSize=12, leading=16, spaceAfter=8, fontName='Helvetica-Bold')
        normal_style = ParagraphStyle(name='Normal', parent=styles['Normal'], fontSize=10, leading=14, spaceAfter=6, fontName='Helvetica')
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('WORDWRAP', (0, 0), (-1, -1), True),
            ('SPLITBYROW', (0, 0), (-1, -1), True),
        ])

        # Add title
        elements.append(Paragraph("Artesyn LCM700 Series Datasheet", title_style))
        elements.append(Spacer(1, 12))

        # Parse markdown content
        lines = content.split('\n')
        current_list = None
        table_data = None
        table_headers = None
        max_col_widths = []

        for line in lines:
            line = line.strip()
            if not line:
                elements.append(Spacer(1, 6))
                continue

            # Sanitize special characters
            line = re.sub(r'([%#$&_{}\[\]])', r'\1', line)
            line = line.replace('≤', '≤').replace('±', '±').replace('μ', 'μ').replace('°', '°').replace('˚', '°')

            if line.startswith('## '):
                if current_list:
                    elements.append(ListFlowable(current_list, bulletType='bullet', start='bulletchar'))
                    current_list = None
                if table_data and table_headers:
                    if not max_col_widths:
                        max_col_widths = [0.8*inch] * len(table_headers)  # Increased initial width
                    for i, row in enumerate(table_data):
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:  # Only calculate width for non-empty cells
                                # Estimate width based on font size and character count
                                cell_width = max(0.5*inch, len(cell) * 0.025 * inch)  # Reduced multiplier
                                max_col_widths[j] = min(2.0*inch, max(max_col_widths[j], cell_width))  # Increased max width
                    total_width = sum(max_col_widths)
                    max_page_width = 6.5*inch  # Increased to allow wider tables
                    if total_width > max_page_width:
                        scale_factor = max_page_width / total_width
                        max_col_widths = [max(0.5*inch, w * scale_factor) for w in max_col_widths]
                    # Wrap cell content in Paragraphs for proper text wrapping
                    wrapped_table_data = []
                    for i, row in enumerate(table_data):
                        wrapped_row = []
                        for j, cell in enumerate(row):
                            cell = str(cell).strip()
                            if cell:
                                wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append(cell)
                        wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True, splitInRow=False)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                elements.append(Paragraph(line[3:].strip(), section_style))
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
                                wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append(cell)
                        wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True, splitInRow=False)
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
                                wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append(cell)
                        wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True, splitInRow=False)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                elements.append(Paragraph(line[4:-2].strip(), subsection_style))
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
                                wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append(cell)
                        wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True, splitInRow=False)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
                current_list.append(ListItem(Paragraph(line[2:].strip(), normal_style)))
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
                                wrapped_row.append(Paragraph(cell, normal_style))
                            else:
                                wrapped_row.append(cell)
                        wrapped_table_data.append(wrapped_row)
                    table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True, splitInRow=False)
                    elements.append(KeepTogether(table))
                    table_data = None
                    table_headers = None
                    max_col_widths = []
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
                        wrapped_row.append(Paragraph(cell, normal_style))
                    else:
                        wrapped_row.append(cell)
                wrapped_table_data.append(wrapped_row)
            table = Table(wrapped_table_data, colWidths=max_col_widths, style=table_style, splitByRow=True, splitInRow=False)
            elements.append(KeepTogether(table))

        # Build PDF
        doc.build(elements)
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
        template="""You are a product specification expert for the Advanced Energy power supplies. The user has uploaded a PDF with details about any product of Advanced Energy, provided below as extracted text. Your task is to predict the specifications for another product in the series by analyzing the PDF text and scaling parameters proportionally (e.g., LCM700 should have ~700 W output if LCM500 has ~500 W/510 W). Use the exact section structure and formatting of the PDF, including:

- Introduction (description of the product series)
- Special Features (bullet list)
- Electrical Specifications (with subsections Input and Output, using tables for Output)
- Ordering Information (bullet list or table)
- Pin Assignment (text or table, mark as TBD if unclear)
- Mechanical Drawings (text with weight, mounting details, etc.)
- Accessories (bullet list with part numbers)
- About Advanced Energy (brief company description)

For each section, extrapolate specifications for the new product based on the PDF data. For example:
- Scale power output proportionally.
- Adjust voltage ranges, current, and other parameters logically based on the power increase.
- Maintain input voltage range (e.g., 90-264 VAC) unless specific differences are indicated.
- Estimate weight increase (e.g., proportional to power or size).
- For unavailable data (e.g., Pin Assignment details), mark as TBD and note assumptions.
- Include all sections even if some data is TBD, ensuring the structure matches the LCM500 PDF.

If the user input is unrelated to predicting specifications, respond naturally, using the PDF only if relevant. Structure the response in markdown with clear section headers, bullet lists, and tables to match the LCM500 PDF format. Ensure the response is detailed, accurate, and comprehensive, avoiding vague or incomplete predictions.

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
        verbose=True
    )
    return conversation

# Load or initialize conversation chain
if st.session_state.spec_conversation is None:
    st.session_state.spec_conversation = get_conversation_chain()

# Streamlit app layout
st.title("Product Series Specification Query")
st.markdown("Upload a PDF for a product (e.g., LCM500) and ask for the specifications of the next product in its series (e.g., LCM700). The response will be provided as a downloadable PDF matching the structure of the uploaded PDF, or displayed as text if PDF generation fails.")

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
    for chat in st.session_state.spec_chat_history:
        st.markdown(f'<div class="user-message"><strong>You:</strong> {chat["user"]}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="bot-message"><strong>Bot:</strong> {chat["bot"]}</div>', unsafe_allow_html=True)
        if chat.get("raw_response"):
            st.markdown(f'<div class="bot-message"><strong>Raw Response:</strong> {chat["raw_response"]}</div>', unsafe_allow_html=True)
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
if st.sidebar.button("Clear History"):
    st.session_state.spec_chat_history = []
    st.session_state.spec_conversation.memory.clear()
    st.session_state.spec_pdf_text = ""
    st.session_state.spec_pdf_response = None
    st.session_state.spec_raw_response = ""
    st.session_state.spec_input_key += 1
    st.rerun()

# Handle user input
if send_button and user_input:
    if not st.session_state.spec_pdf_text:
        st.error("Please upload a PDF with extractable text before submitting a query.")
    else:
        try:
            # Get response from the chain
            response_dict = st.session_state.spec_conversation({"input": user_input, "pdf_text": st.session_state.spec_pdf_text})
            response = response_dict.get('text', '') if isinstance(response_dict, dict) else str(response_dict)
            
            if not response.strip():
                st.error("LLM returned an empty response. Please check the input or try a different query.")
            else:
                # Store raw response
                st.session_state.spec_raw_response = response
                
                # Generate PDF from response
                pdf_data = generate_pdf(response, filename="lcm_specs.pdf")
                if pdf_data:
                    st.session_state.spec_pdf_response = pdf_data
                    st.session_state.spec_chat_history.append({
                        "user": user_input,
                        "bot": "PDF generated. Download below.",
                        "raw_response": response
                    })
                else:
                    st.session_state.spec_chat_history.append({
                        "user": user_input,
                        "bot": f"Failed to generate PDF. Raw response:\n{response}",
                        "raw_response": response
                    })
                    st.markdown("### Response\n" + response)
                
                # Clear input by updating key
                st.session_state.spec_input_key += 1
                st.rerun()
                
        except Exception as e:
            st.error(f"An error occurred: {str(e)}\nDetails: {traceback.format_exc()}")

# Display download button for PDF response
if st.session_state.spec_pdf_response:
    st.download_button(
        label="Download Response PDF",
        data=st.session_state.spec_pdf_response,
        file_name="lcm_specs.pdf",
        mime="application/pdf"
    )