import markdown
import os
import re

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
    # Example usage for two Markdown files
    first_page_md = "first_page.md"
    remaining_pages_md = "remaining_pages.md"
    css_file = "pdf_styles.css"
    output_file = "output_with_css.html"
    image_file_path = "advance_energy.png"  # Path to the header image
    
    # Check if input files exist
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