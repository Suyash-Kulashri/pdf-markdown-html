import os
import base64
from openai import OpenAI
from bs4 import BeautifulSoup
from weasyprint import HTML
from dotenv import load_dotenv

# Load OpenAI API key from .env file
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env file")

# Initialize OpenAI client
client = OpenAI(api_key=api_key)

# Path to the input HTML file
input_html_file = "predicted_html.html"  # Replace with your HTML file path
output_pdf_file = "output.pdf"
temp_html_file = "temp_processed.html"  # Temporary file for debugging

# Base path for resolving relative URLs (e.g., for local images)
base_path = os.path.dirname(os.path.abspath(input_html_file))

# Simplified CSS for table formatting
table_css = """
<style>
table {
    break-inside: auto;
    width: 100%;
    border-collapse: collapse;
}
tr {
    break-inside: avoid;
    break-after: auto;
}
thead {
    display: table-header-group;
}
tbody {
    display: table-row-group;
}
th, td {
    border: 1px solid #ddd;
    padding: 8px;
    font-size: 12px;
}
img {
    max-width: 100%;
}
</style>
"""

# Function to convert local images to base64
def image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            ext = os.path.splitext(image_path)[1].lower()
            mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else 'image/png' if ext == '.png' else 'image/gif'
            return f"data:{mime_type};base64,{encoded_string}"
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

# Function to preprocess HTML with OpenAI
def preprocess_html_with_openai(html_content, base_path):
    # Collect base64 strings for local images
    soup = BeautifulSoup(html_content, 'html.parser')
    image_base64_map = {}
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and not src.startswith(('http://', 'https://', 'data:')):
            image_path = os.path.join(base_path, src)
            if os.path.exists(image_path):
                base64_str = image_to_base64(image_path)
                if base64_str:
                    image_base64_map[src] = base64_str
                else:
                    print(f"Warning: Skipping image {src} due to processing error")
            else:
                print(f"Warning: Image not found at {image_path}")

    # Prepare prompt for OpenAI
    prompt = f"""
You are an expert in HTML and CSS. I have an HTML file with tables and images. Your task is to:
1. Inject the following CSS into the <head> section to ensure proper table formatting for PDF conversion:
   ```html
   {table_css}
   ```
2. Replace local image paths with base64 data URLs using the provided map.
3. Do not modify any other parts of the HTML except for adding the CSS and updating image src attributes.
4. Ensure tables have <thead> and <tbody> for header repetition on multi-page PDFs.
5. Return only the modified HTML content, nothing else.

Here is the HTML content:
```html
{html_content}
```

Here are the base64 strings for local images:
{'\n'.join([f"{src}: {base64_str}" for src, base64_str in image_base64_map.items()])}

Return the modified HTML content.
"""

    # Call OpenAI API
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise HTML and CSS processor. Return only the modified HTML content, no explanations or extra text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        modified_html = response.choices[0].message.content
        # Validate the modified HTML
        if not modified_html.strip():
            raise ValueError("OpenAI returned empty HTML content")
        soup = BeautifulSoup(modified_html, 'html.parser')
        if not soup.html:
            raise ValueError("OpenAI returned invalid HTML")
        return modified_html
    except Exception as e:
        print(f"Error with OpenAI API: {e}")
        return None

# Check if the HTML file exists
if not os.path.exists(input_html_file):
    print(f"Error: The file '{input_html_file}' does not exist.")
else:
    try:
        # Read the input HTML
        with open(input_html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Preprocess HTML with OpenAI
        processed_html = preprocess_html_with_openai(html_content, base_path)
        if not processed_html:
            raise ValueError("Failed to preprocess HTML with OpenAI")

        # Save processed HTML for debugging
        with open(temp_html_file, 'w', encoding='utf-8') as f:
            f.write(processed_html)

        # Convert HTML to PDF using WeasyPrint
        HTML(temp_html_file).write_pdf(
            output_pdf_file,
            stylesheets=[]  # CSS is already injected
        )

        print(f"PDF generated successfully as '{output_pdf_file}'")
        print(f"Processed HTML saved as '{temp_html_file}' for debugging (not deleted)")

    except Exception as e:
        print(f"Error generating PDF: {e}")