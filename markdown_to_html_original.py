import markdown
import os
import re

def group_images_in_rows(md_content):
    img_pattern = r'!$$ .*? $$$$ (.*?) $$'
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

def convert_markdown_to_html(md_file_path, css_file_path, output_html_path, image_file_path):
    # Hardcoded footer content
    footer_content = """
Advanced Energy (AE) has devoted more than three decades to perfecting power for its global customers. AE designs and manufactures highly engineered, precision power conversion, measurement and control solutions for mission-critical applications and processes.

Our products enable customer innovation in complex applications for a wide range of industries including semiconductor equipment, industrial, manufacturing, telecommunications, data center computing, and medical. With deep applications know-how and responsive service and support across the globe, we build collaborative partnerships to meet rapid technological developments, propel growth for our customers, and innovate the future of power.

For international contact information, visit advancedenergy.com.

powersales@aei.com (Sales Support)  
productsupport.ep@aei.com (Technical Support)  +1 888 412 7832

Specifications are subject to change without notice. Not responsible for errors or omissions. ©2020 Advanced Energy Industries, Inc. All rights reserved. Advanced Energy®, and AE® are U.S. trademarks of Advanced Energy Industries, Inc."""
    
    # Read the Markdown file
    with open(md_file_path, 'r', encoding='utf-8') as md_file:
        md_content = md_file.read()
    
    # Remove "**TECHNICAL REFERENCE NOTE**" from the file if present
    md_content = re.sub(r'\*\*TECHNICAL REFERENCE NOTE\*\*\s*\n?', '', md_content, flags=re.IGNORECASE)
    
    # Extract the first H1 heading for the page title
    h1_match = re.search(r'^#\s+(.+)$', md_content, re.MULTILINE)
    page_title = h1_match.group(1).strip() if h1_match else "Markdown to HTML"
    
    # Remove the specified text from the bottom of the Markdown content
    text_to_remove = r"""For international contact information,.*?\bAdvanced Energy Industries, Inc\.""".strip()
    md_cleaned = re.sub(
        rf'{text_to_remove}\s*$',
        '',
        md_content,
        flags=re.DOTALL | re.MULTILINE
    ).strip()
    
    # Group images in rows before converting to HTML
    md_grouped = group_images_in_rows(md_cleaned)
    
    # Convert Markdown to HTML
    html_content = markdown.markdown(md_grouped, extensions=['extra', 'codehilite'])
    footer_html = markdown.markdown(footer_content, extensions=['extra', 'codehilite'])
    
    # Read the CSS file
    with open(css_file_path, 'r', encoding='utf-8') as css_file:
        css_content = css_file.read()
    
    # Create the complete HTML with CSS embedded, header, content, and footer
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
    <header style="position: relative; min-height: 80px;" class="header">
        <span style="position: absolute; left: 30px; top: 50px; color: #004080; font-weight: bold; font-size: 1.2em;">TECHNICAL REFERENCE NOTE</span>
        <img src="{image_file_path}" alt="Header Image" style="position: absolute; top: 0; right: 50px; max-width: 700px;">
    </header>
    <main>
        {html_content}
    </main>
    <h2 align="center"> ABOUT ADVANCED ENERGY</h2>
    <footer class="footer">
        {footer_html}
    </footer>
</body>
</html>"""
    
    # Write the output to an HTML file
    with open(output_html_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_output)

if __name__ == "__main__":
    # Example usage for a single Markdown file
    md_file = "predicted_changes.md"
    css_file = "pdf_styles2.css"
    output_file = "predicted_html.html"
    image_file_path = "advance_energy.png"  # Path to the header image
    
    # Check if input files exist
    if not os.path.exists(md_file):
        print(f"Error: Markdown file '{md_file}' not found.")
    elif not os.path.exists(css_file):
        print(f"Error: CSS file '{css_file}' not found.")
    elif not os.path.exists(image_file_path):
        print(f"Error: Image file '{image_file_path}' not found.")
    else:
        try:
            convert_markdown_to_html(md_file, css_file, output_file, image_file_path)
            print(f"HTML file generated: {output_file}")
        except Exception as e:
            print(f"Error processing Markdown file: {str(e)}")