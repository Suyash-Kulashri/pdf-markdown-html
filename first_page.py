import pdfplumber
import markdown
import os
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize OpenAI client with API key from environment
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set")

client = OpenAI(api_key=openai_api_key)

def extract_pdf_first_page(pdf_path):
    """Extract text and image references from the first page of a PDF."""
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return "", []
            first_page = pdf.pages[0]
            text = first_page.extract_text() or ""
            # Extract image references (assuming placeholders like [Image: filename])
            images = []
            lines = text.split('\n')
            for line in lines:
                if line.startswith('[Image:') and line.endswith(']'):
                    image_name = line.strip('[]').replace('Image:', '').strip()
                    images.append(image_name)
            # If no placeholders found, check for actual images
            if not images and hasattr(first_page, 'images'):
                for i, _ in enumerate(first_page.images):
                    images.append(f"images/{os.path.splitext(os.path.basename(pdf_path))[0]}-0-{i}.png")
            return text, images
    except Exception as e:
        print(f"Error extracting PDF: {e}")
        return "", []

def read_markdown(md_path):
    """Read content from a Markdown file."""
    try:
        if not os.path.exists(md_path):
            raise FileNotFoundError(f"Markdown file not found: {md_path}")
        with open(md_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading Markdown: {e}")
        return ""

def read_css(css_path):
    """Read content from a CSS file."""
    try:
        if not os.path.exists(css_path):
            raise FileNotFoundError(f"CSS file not found: {css_path}")
        with open(css_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading CSS: {e}")
        return ""

def generate_html(pdf_path, md_path, css_path, output_path):
    """Generate HTML using OpenAI API based on PDF, Markdown, and CSS inputs."""
    # Extract content from inputs
    pdf_text, pdf_images = extract_pdf_first_page(pdf_path)
    md_content = read_markdown(md_path)
    css_content = read_css(css_path)

    # Prepare prompt for OpenAI
    prompt = f"""
You are tasked with generating an HTML file that replicates the first page of a PDF document, using content from a Markdown file and styling based on a provided CSS file. The PDF follows a consistent format (header with title/subtitle, product description, features list, specs table, compliance/safety lists, and images) but with varying content. The output HTML should match the following layout and styling, incorporating content from the PDF and Markdown. You may modify the CSS if necessary to achieve the desired appearance but maintain the core styling approach.

### Target HTML Structure and Requirements:
- **Header**: A grey background div containing:
  
  - An `<h1>` with the main title (e.g., product name from PDF/Markdown).
  - An `<h2>` with a subtitle (e.g., product specification from PDF/Markdown).
  - The first image (from PDF images) positioned to the right of the `<h1>`.
- **Main Content**:
  - A section with a title (e.g., "PRODUCT DESCRIPTION") and a paragraph of text from PDF or Markdown.
  - A "SPECIAL FEATURES" section with a `<ul>` of features (bullet points) from PDF or Markdown.
  - An "AT A GLANCE" table summarizing key specs (e.g., Total Power, Input Voltage, # of Outputs) from PDF or Markdown.
  - A "COMPLIANCE" and "SAFETY" section displayed side-by-side using flexbox, with `<ul>` lists from PDF or Markdown.
- **Images**: Remaining images (e.g., second and third, if available) in a vertical stack in the bottom-right corner of the page.
- **Footer**: A copyright notice (e.g., "©2025 Company Name") from PDF or Markdown.
- **Styling**:
  - Container: max-width 816px, white background, padding, subtle box-shadow.
  - Images are in an `images` folder with names as in PDF (e.g., `images/[filename]-0-0.png`).
  - Use provided CSS as a base, adjusting only if needed to match the layout.

### Inputs:
**PDF First Page Content:**
Text:
```
{pdf_text}
```
Images:
```
{pdf_images}
```

**Markdown Content (first_page.md):**
```
{md_content}
```

**CSS Content (first_page.css):**
```
{css_content}
```

### Instructions:
- Generate a complete HTML file (`first_page_html.html`) integrating PDF and Markdown content with CSS styling.
- Match the described layout: header (grey background, `<p>`, `<h1>`, `<h2>`, first image on right), content sections, remaining images in bottom-right, footer.
- Use image filenames from PDF input (e.g., `images/[filename]-0-1.png`).
- Prioritize Markdown for text content but use PDF for image references if conflicting.
- Modify CSS only if necessary, preserving original styles as much as possible.
- Output only the HTML content with `<style>` tag (original or modified CSS).
- Do not include explanations or comments outside the HTML code.

### Output:
Complete HTML content, including `<style>` tag with CSS, ready for `first_page_html.html`.
"""

    try:
        # Call OpenAI API to generate HTML
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a highly skilled web developer tasked with generating HTML and CSS code."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000
        )
        html_content = response.choices[0].message.content.strip()

        # Save the generated HTML to output file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"HTML file generated successfully at {output_path}")
    except Exception as e:
        print(f"Error generating HTML with OpenAI: {e}")

if __name__ == "__main__":
    # Define file paths
    pdf_path = "LCM300.pdf"
    md_path = "first_page.md"
    css_path = "first_page.css"
    output_path = "first_page_html.html"

    # Validate input files
    for path in [pdf_path, md_path, css_path]:
        if not os.path.exists(path):
            print(f"Error: File not found - {path}")
            exit(1)

    # Generate HTML
    generate_html(pdf_path, md_path, css_path, output_path)