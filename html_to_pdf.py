import pdfkit
import os
from bs4 import BeautifulSoup

# Path to the input HTML file
input_html_file = "predicted_html.html"  # Replace with your HTML file path
output_pdf_file = "output.pdf"

# Base path for resolving relative URLs (e.g., for local CSS/images)
base_path = os.path.dirname(os.path.abspath(input_html_file))

# CSS to handle table pagination and header repetition
table_css = """
<style>
    table {
        page-break-inside: auto; /* Allow tables to break across pages */
        width: 100%;
        border-collapse: collapse;
    }
    tr {
        page-break-inside: avoid; /* Prevent row splitting when possible */
        page-break-after: auto;
    }
    thead {
        display: table-header-group; /* Repeat headers on each page */
    }
    tbody {
        display: table-row-group;
    }
    th, td {
        border: 1px solid #ddd;
        padding: 8px;
    }
</style>
"""

# Function to inject table CSS into HTML
def inject_table_css(html_file):
    with open(html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f, 'html.parser')
    
    # Find or create the <head> section
    head = soup.head
    if not head:
        head = soup.new_tag('head')
        soup.html.insert(0, head)
    
    # Append the CSS to the head
    style_tag = BeautifulSoup(table_css, 'html.parser')
    head.append(style_tag)
    
    # Save modified HTML to a temporary file
    temp_html_file = "temp_table_formatted.html"
    with open(temp_html_file, 'w', encoding='utf-8') as f:
        f.write(str(soup))
    
    return temp_html_file

# Configuration options for wkhtmltopdf
options = {
    'enable-local-file-access': '',  # Allow access to local files
    'quiet': False,  # Enable verbose output for debugging
    'page-size': 'A4',
    'margin-top': '0.75in',
    'margin-right': '0.75in',
    'margin-bottom': '0.75in',
    'margin-left': '0.75in',
    'no-stop-slow-scripts': '',  # Prevent stopping slow scripts
    'disable-smart-shrinking': '',  # Prevent scaling issues
    'enable-javascript': '',  # Enable JavaScript for dynamic content
}

# Check if the HTML file exists
if not os.path.exists(input_html_file):
    print(f"Error: The file '{input_html_file}' does not exist.")
else:
    try:
        # Inject table CSS into HTML
        temp_html_file = inject_table_css(input_html_file)
        
        # Convert HTML file to PDF
        pdfkit.from_file(temp_html_file, output_pdf_file, options=options, verbose=True)
        print(f"PDF generated successfully as '{output_pdf_file}'")
        
        # Clean up temporary file
        if os.path.exists(temp_html_file):
            os.remove(temp_html_file)
    except Exception as e:
        print(f"Error generating PDF: {e}")