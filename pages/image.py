import streamlit as st
from docx import Document
import zipfile
import os
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from pdf2docx import Converter
import tempfile
import openai
import base64
import json

# Initialize OpenAI client with API key from environment variable
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    st.error("OpenAI API key not found. Please set the OPENAI_API_KEY environment variable.")
    st.stop()
client = openai.OpenAI(api_key=openai_api_key)

# --- System Prompt for LLM ---
SYSTEM_PROMPT = """
You are an expert image and document analysis assistant tasked with labeling images extracted from a DOCX file. Your goal is to provide accurate, concise, and contextually relevant labels for each image based on the document's content. Use the provided document text to understand the context and ensure the labels align with the document's purpose and content.

**Input**:
- Document text from the DOCX file for context.
- The image encoded in base64 format for analysis.
- The image dimensions (width x height in pixels) will be provided separately; do not guess the size.

**Task**:
Analyze the image and document text to generate a label with the following fields:
- **Description**: A precise description of what the image depicts (e.g., "Diagram of a car engine", "Bar chart of 2023 sales data"). Avoid vague terms like "image" or "graphic".
- **Purpose**: The specific role of the image in the document (e.g., "Illustrates the structure of a molecule", "Shows quarterly revenue trends"). Tie this to the document's content.
- **Pinpoint Size**: Use the provided dimensions (width x height) exactly as given.

**Output**:
Return a JSON object with the following fields:
{
  "description": "string",
  "purpose": "string",
  "pinpoint_size": "width x height"
}

**Guidelines**:
- Prioritize the document text to ground your analysis. For example, if the document discusses "solar panel efficiency," the image is likely related to that topic.
- If the image content is ambiguous, make an educated guess based on the document text, but note the uncertainty in the description (e.g., "Likely a diagram of...").
- Ensure the description is specific (e.g., "Pie chart of market share" instead of "Chart").
- Do not include irrelevant or speculative information.
"""

# --- Core Logic Function ---
def extract_useful_images(docx_path, min_width, min_height, min_kb):
    """
    Extracts images from a .docx file based on filtering criteria.

    Args:
        docx_path (str): Path to the .docx file.
        min_width (int): Minimum image width in pixels.
        min_height (int): Minimum image height in pixels.
        min_kb (int): Minimum file size in kilobytes.

    Returns:
        list: A list of tuples, where each tuple contains (filename, image_data, label).
    """
    useful_images = []
    saved_image_count = 0
    doc_text = ""

    try:
        # Open the document and extract text for context
        doc = Document(docx_path)
        doc_text = "\n".join([para.text for para in doc.paragraphs])

        # Iterate through all relationships in the document part
        for rel in doc.part._rels.values():
            if "image" in rel.target_ref:
                image_data = rel.target_part.blob
                file_size_kb = len(image_data) / 1024

                # 1. Filter by file size
                if file_size_kb >= min_kb:
                    try:
                        # Use BytesIO to read image properties
                        img_stream = BytesIO(image_data)
                        image = Image.open(img_stream)
                        width, height = image.size

                        # 2. Filter by dimensions
                        if width >= min_width and height >= min_height:
                            saved_image_count += 1
                            image_ext = image.format.lower()
                            image_filename = f"useful_image_{saved_image_count}.{image_ext}"

                            # Encode image to base64 for LLM
                            base64_image = base64.b64encode(image_data).decode('utf-8')

                            # Call OpenAI API for labeling
                            response = client.chat.completions.create(
                                model="gpt-4o",
                                messages=[
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": f"Document text: {doc_text}\nImage dimensions: {width} x {height}"},
                                            {
                                                "type": "image_url",
                                                "image_url": {"url": f"data:image/{image_ext};base64,{base64_image}"}
                                            }
                                        ]
                                    }
                                ],
                                max_tokens=300
                            )
                            label = response.choices[0].message.content
                            try:
                                label = json.loads(label)
                                # Ensure pinpoint_size matches the actual dimensions
                                label["pinpoint_size"] = f"{width} x {height}"
                            except:
                                label = {
                                    "description": "Unknown",
                                    "pinpoint_size": f"{width} x {height}",
                                    "purpose": "Unknown"
                                }

                            # Annotate the image with the label
                            annotated_image = annotate_image(image, label)
                            img_byte_arr = BytesIO()
                            annotated_image.save(img_byte_arr, format=image.format)
                            annotated_image_data = img_byte_arr.getvalue()

                            useful_images.append((image_filename, annotated_image_data, label))
                    
                    except Exception as e:
                        st.warning(f"Could not process an image part. Error: {e}")
                        
    except Exception as e:
        st.error(f"An error occurred while reading the DOCX file. Error: {e}")
        return []

    return useful_images

# --- Function to Annotate Image ---
def annotate_image(image, label):
    """
    Annotates the image with the provided label using PIL.

    Args:
        image (PIL.Image): The image to annotate.
        label (dict): Dictionary containing description, pinpoint_size, and purpose.

    Returns:
        PIL.Image: The annotated image.
    """
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()

    # Prepare label text
    label_text = (
        f"Description: {label['description']}\n"
        f"Size: {label['pinpoint_size']}\n"
        f"Purpose: {label['purpose']}"
    )

    # Calculate text position (top-left corner)
    text_position = (10, 10)
    text_color = (255, 255, 255)  # White text
    background_color = (0, 0, 0, 128)  # Semi-transparent black background

    # Get text bounding box
    text_bbox = draw.textbbox(text_position, label_text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    # Draw semi-transparent background
    draw.rectangle(
        (text_bbox[0], text_bbox[1], text_bbox[2], text_bbox[3]),
        fill=background_color
    )

    # Draw text
    draw.text(text_position, label_text, font=font, fill=text_color)

    return image

# --- Streamlit App UI ---
st.set_page_config(page_title="PDF & DOCX Image Extractor", layout="wide")

st.title("📄 PDF and DOCX Useful Image Extractor with Labels")
st.markdown("""
Upload a Microsoft Word (`.docx`) or PDF (`.pdf`) file to extract all the "useful" images with labels.
PDFs will be converted to DOCX for image extraction. Images are labeled using an LLM based on the document's context.
""")

# --- Sidebar for Controls ---
with st.sidebar:
    st.header("⚙️ Filter Controls")
    
    # Sliders for filtering
    min_width = st.slider("Minimum Image Width (pixels)", 50, 1000, 150)
    min_height = st.slider("Minimum Image Height (pixels)", 50, 1000, 150)
    min_kb = st.slider("Minimum File Size (KB)", 1, 100, 15)
    
    st.markdown("---")
    st.info("Adjust the sliders to define what a 'useful' image is for your document.")
    
    # File uploader for both .docx and .pdf
    uploaded_file = st.file_uploader("Choose a .docx or .pdf file", type=["docx", "pdf"])

# --- Main App Logic ---
if uploaded_file is not None:
    st.success(f"File **{uploaded_file.name}** uploaded successfully!")
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        docx_path = None
        try:
            # Handle PDF files
            if uploaded_file.name.lower().endswith('.pdf'):
                # Save uploaded PDF to a temporary file
                pdf_path = os.path.join(temp_dir, uploaded_file.name)
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.read())
                
                # Convert PDF to DOCX
                docx_path = os.path.join(temp_dir, f"{os.path.splitext(uploaded_file.name)[0]}.docx")
                cv = Converter(pdf_path)
                cv.convert(docx_path)
                cv.close()
                st.info(f"Converted PDF to DOCX: {docx_path}")
            
            # Handle DOCX files
            elif uploaded_file.name.lower().endswith('.docx'):
                # Save uploaded DOCX to a temporary file
                docx_path = os.path.join(temp_dir, uploaded_file.name)
                with open(docx_path, "wb") as f:
                    f.write(uploaded_file.read())
            
            # Extract images from the DOCX file
            if docx_path:
                extracted_images = extract_useful_images(docx_path, min_width, min_height, min_kb)
                
                if extracted_images:
                    st.header(f"✅ Found {len(extracted_images)} useful images")

                    # Create an in-memory zip file
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for filename, data, _ in extracted_images:
                            zf.writestr(filename, data)
                    
                    # Make the zip file's bytes available for download
                    zip_bytes = zip_buffer.getvalue()

                    # Add the download button
                    st.download_button(
                        label="📥 Download All Images (.zip)",
                        data=zip_bytes,
                        file_name=f"useful_images_{os.path.splitext(uploaded_file.name)[0]}.zip",
                        mime="application/zip"
                    )
                    
                    st.markdown("---")
                    st.subheader("Image Previews with Labels:")

                    # Display images in a grid
                    cols = st.columns(4)
                    for i, (filename, data, _) in enumerate(extracted_images):
                        with cols[i % 4]:
                            st.image(data, caption=filename, use_column_width=True)

                else:
                    st.warning("No images found that match your filter criteria. Try adjusting the sliders in the sidebar.")
            
            else:
                st.error("Failed to process the uploaded file. Please ensure it’s a valid .docx or .pdf file.")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

else:
    st.info("Please upload a `.docx` or `.pdf` file using the sidebar to get started.")