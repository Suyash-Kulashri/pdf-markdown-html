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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib import colors
from xml.sax.saxutils import escape

# Load environment variables from .env file
load_dotenv()

# --- Google API Configuration ---
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    st.error("Google API key is missing. Please add it to your .env file (e.g., GOOGLE_API_KEY='your_key_here').")
    st.stop()

try:
    genai.configure(api_key=api_key)
except Exception as e:
    st.error(f"Failed to configure Gemini API: {e}")
    st.stop()

# --- Streamlit Page Setup ---
st.set_page_config(layout="wide", page_title="Dynamic Specification Generator", page_icon="📄")

# --- Custom CSS for Styling ---
st.markdown("""
    <style>
    .stApp {
        background-color: #0000;
    }
    /* Other UI styles can go here */
    </style>
""", unsafe_allow_html=True)


# --- Main App Interface ---
st.title("📄 Dynamic Product Specification Generator")
st.markdown("""
    <div style="color: #475569; margin-bottom: 24px; font-size: 1.1rem;">
    Upload a product datasheet (e.g., LCM300) to generate specifications for other models in the series (e.g., LCM700). The AI will create a scaled version with consistent, professional formatting, ready to be downloaded as a PDF.
    </div>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.markdown("## ⚙️ Controls")
    if st.button("🔄 Clear Chat & Reset", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.markdown("---")
    st.markdown("### About This App")
    st.markdown("This tool uses Google's Gemini to help engineers create new datasheets by intelligently scaling parameters from an existing document.")

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

# --- Core Functions ---

def extract_pdf_text(uploaded_file):
    try:
        uploaded_file.seek(0)
        pdf_reader = PyPDF2.PdfReader(uploaded_file)
        text = "".join(page.extract_text() + "\n" for page in pdf_reader.pages if page.extract_text())
        
        if len(text.strip()) < 100:
            st.warning("Initial text extraction was minimal. Attempting OCR fallback...")
            uploaded_file.seek(0)
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

def fix_markdown_tables(markdown_text):
    lines = markdown_text.split('\n')
    corrected_lines = []
    in_table = False
    expected_columns = 0

    for line in lines:
        stripped_line = line.strip()
        is_table_row = stripped_line.startswith('|') and stripped_line.endswith('|')

        if not in_table and is_table_row:
            if re.match(r'\|-*\|', stripped_line.replace(' ', '')):
                continue
            in_table = True
            expected_columns = len(stripped_line.split('|'))
            corrected_lines.append(line)
        elif in_table and is_table_row:
            if re.match(r'\|-*\|', stripped_line.replace(' ', '')):
                continue
            current_columns = len(stripped_line.split('|'))
            if current_columns != expected_columns:
                corrected_lines.append('')
                expected_columns = current_columns
                corrected_lines.append(line)
            else:
                corrected_lines.append(line)
        elif in_table and not is_table_row:
            in_table = False
            expected_columns = 0
            corrected_lines.append(line)
        else:
            corrected_lines.append(line)
            
    return '\n'.join(corrected_lines)

def sanitize_for_reportlab(text):
    text = str(text)
    text = re.sub(r'<br\s*/?>', '___BR___', text, flags=re.IGNORECASE)
    text = escape(text)
    text = text.replace('___BR___', '<br/>')
    return text

def generate_pdf_from_markdown(content):
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
        table_style_config = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('TOPPADDING', (0, 0), (-1, 0), 8),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.Color(0.9, 0.9, 0.9), colors.white]),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ])

        lines = content.split('\n')
        if lines and lines[0].startswith('# '):
            doc_title = lines.pop(0)[2:].strip()
            elements.append(Paragraph(sanitize_for_reportlab(doc_title), title_style))
            elements.append(Spacer(1, 18))

        in_table = False
        table_data = []
        
        def build_table(data):
            if not data: return None
            try:
                page_width = A4[0] - (doc.leftMargin + doc.rightMargin)
                num_columns = len(data[0]) if data else 0
                if num_columns == 0: return None

                col_widths = [0] * num_columns
                for row in data:
                    for i, cell in enumerate(row):
                        col_widths[i] = max(col_widths[i], len(cell))
                
                total_chars = sum(col_widths)
                if total_chars > 0:
                    col_widths = [page_width * (width / total_chars) for width in col_widths]
                else:
                    col_widths = [page_width / num_columns] * num_columns

                wrapped_data = [[Paragraph(sanitize_for_reportlab(cell), normal_style) for cell in row] for row in data]
                table = Table(wrapped_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(table_style_config)
                return KeepTogether(table)
            except Exception as e:
                st.warning(f"Could not build table. Error: {e}")
                return None

        for line in lines:
            line = line.strip()
            if not line:
                if in_table:
                    table_obj = build_table(table_data)
                    if table_obj: elements.append(table_obj)
                    in_table = False
                    table_data = []
                continue

            if line.startswith('|') and line.endswith('|'):
                if not in_table:
                    in_table = True
                    table_data = []
                if re.match(r'\|-*\|', line.replace(' ', '')): continue
                table_data.append([cell.strip() for cell in line.split('|')[1:-1]])
                continue
            
            if in_table:
                table_obj = build_table(table_data)
                if table_obj: elements.append(table_obj)
                in_table = False
                table_data = []

            if line.startswith('## '):
                elements.append(Paragraph(sanitize_for_reportlab(line[3:].strip().upper()), section_style))
            elif line.startswith('### '):
                elements.append(Paragraph(sanitize_for_reportlab(line[4:].strip()), subsection_style))
            elif line.startswith(('* ','- ',' ')):
                elements.append(Paragraph(f"• {sanitize_for_reportlab(line[2:])}", list_style))
            elif not line.startswith('#'):
                elements.append(Paragraph(sanitize_for_reportlab(line), normal_style))
        
        if in_table:
            table_obj = build_table(table_data)
            if table_obj: elements.append(table_obj)

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data
    except Exception as e:
        st.error(f"Error generating PDF: {e}")
        st.error(traceback.format_exc())
        return None

# --- FINAL, MOST STRICT PROMPT ---
def get_gemini_response(user_input, pdf_text):
    prompt = f"""
    You are an expert engineering assistant. Your task is to generate a new, complete datasheet for a different product model based on the user's request, using the provided PDF text as a reference.

    **CRITICAL Instructions:**
    1.  **Analyze Source:** Read the "Source PDF Text" to understand its structure, formatting, and technical parameters.
    2.  **Identify Target:** Determine the new product model from the "User Query".
    3.  **Scale ALL Parameters Logically:**
        * **Electrical:** Intelligently extrapolate specifications. If the source is a 300W power supply and the target is 700W, proportionally scale power, current, etc. Keep constant parameters like input voltage range.
        * **Physical:** You **MUST** logically scale physical properties. A higher power unit should be larger and heavier. Estimate new dimensions (Length, Width, Height) and Weight, and state your reasoning in parentheses, e.g., "(Dimensions scaled proportionally to the ~133% increase in power)". **Do not assume physical properties are identical.**

    4.  **Maintain Structure:** Replicate the *exact* section structure of the source. Generate content for every single section.
    
    5.  **CRITICAL RULE: NO PLACEHOLDERS OR SUMMARIES.** This is a non-negotiable rule. Your output **MUST** be a complete, standalone document. You are **strictly forbidden** from using summary phrases like 'This section remains the same as the source document,' 'Details are as per the original,' or '(Identical to source, no changes needed)'. You **MUST** generate the full content for every section by either scaling the data or copying the original content verbatim if it is identical.
    
    6.  **Format as Markdown:** The entire output must be clean markdown. Use '#', '##', '###' for titles and headers.
    
    7.  **Table Formatting Rule:** It is critical that **every row in a single markdown table block has the exact same number of columns**. If you need to present data with different column structures, you **MUST** start a new, separate table.

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

# --- Main Application Logic ---

with st.expander("Step 1: Upload a Source Datasheet", expanded=not st.session_state.pdf_text):
    uploaded_file = st.file_uploader("Upload a product PDF", type=["pdf"], label_visibility="collapsed")
    if uploaded_file and not st.session_state.pdf_text:
        with st.spinner("Analyzing PDF... This may take a moment."):
            st.session_state.pdf_text = extract_pdf_text(uploaded_file)
            if st.session_state.pdf_text:
                st.success("PDF analyzed successfully!")
                st.rerun()

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
    st.session_state.chat_history.append({"user": user_input, "bot": "Thinking..."})

    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Gemini is thinking and generating the document..."):
            raw_response_text = get_gemini_response(user_input, st.session_state.pdf_text)
            
            bot_message = ""
            pdf_data = None
            filename = "generated_specs.pdf"

            if "Error:" in raw_response_text:
                bot_message = raw_response_text
            else:
                fixed_response_text = fix_markdown_tables(raw_response_text)
                pdf_data = generate_pdf_from_markdown(fixed_response_text)
                
                if pdf_data:
                    bot_message = "I have generated the datasheet you requested. The document formatting has been enhanced for a professional layout. You can download it below."
                    target_model_match = re.search(r'([A-Za-z0-9-]+[1-9]00[A-Za-z0-9-]*W?)', user_input, re.IGNORECASE)
                    if target_model_match:
                        filename = f"{target_model_match.group(1).lower().replace(' ', '_')}_specs.pdf"
                else:
                    bot_message = f"I tried to automatically format the document, but there was still an error creating the PDF. Here is the raw markdown for review:\n\n---\n\n{raw_response_text}"
            
            st.markdown(bot_message)
            if pdf_data:
                st.download_button(
                    label=f"⬇️ Download {filename}",
                    data=pdf_data,
                    file_name=filename,
                    mime="application/pdf"
                )
            
            st.session_state.chat_history[-1]["bot"] = bot_message
            st.session_state.chat_history[-1]["pdf_data"] = pdf_data
            st.session_state.chat_history[-1]["filename"] = filename
            