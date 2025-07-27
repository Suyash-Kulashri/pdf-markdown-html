import openai
from openai import OpenAI
import os
import PyPDF2
from dotenv import load_dotenv
# Load environment variables from .env file
load_dotenv()

# Set your OpenAI API key (replace with your actual key or set in environment)
openai.api_key = os.getenv("OPENAI_API_KEY")  # Example: export OPENAI_API_KEY='your-api-key'

# Hardcoded file names
pdf_file = "LCM3000.pdf"
html_file = "output_with_css.html"
css_file = ""  # No separate CSS file, as per your input

# Function to extract text from PDF
def extract_pdf_content(pdf_file):
    try:
        with open(pdf_file, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

# Function to read file content
def read_file(file_path):
    try:
        with open(file_path, 'r') as file:
            return file.read()
    except Exception as e:
        return f"Error reading file {file_path}: {str(e)}"

# Function to call the LLM API (updated for openai>=1.0.0)
def call_llm(prompt):
    try:
        client = OpenAI(api_key=openai.api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use appropriate model (e.g., gpt-4 or gpt-3.5-turbo)
            messages=[
                {"role": "system", "content": "You are an expert in HTML and CSS."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error calling LLM API: {str(e)}"

# Read PDF content
pdf_content = extract_pdf_content(pdf_file)

# Read HTML content
html_content = read_file(html_file)

# Read CSS content (if provided)
css_content = read_file(css_file) if css_file else "No separate CSS file provided."

# Create prompt with task description
prompt = f"""
I have a PDF and the HTML and CSS code. The HTML page has to somehow look like the PDF. I will provide the PDF as context to the LLM and the HTML code. The LLM should modify the code and provide the full HTML code with modification so that the HTML page looks like the PDF. The task also includes removing the footer content of each page of the PDF from the HTML code. Do not remove the last footer from the HTML code.

**PDF Content:**
{pdf_content}

**Original HTML:**
{html_content}

**Original CSS:**
{css_content}

**Instructions:**
1. Modify the HTML and CSS to make the webpage look like the PDF, including fonts, layout, and styling.
2. Remove all <footer> elements except the last one in the HTML.
3. Return the full modified HTML code with CSS included in a <style> tag within the HTML as a complete, valid HTML document.
4. Ensure the output is clean, functional, and matches the PDF's appearance as closely as possible.
"""

# Call LLM to get modified HTML
modified_html = call_llm(prompt)

# Print and save the output
print("\nModified HTML:\n")
print(modified_html)

# Save to a file
output_file = "modified_page.html"
with open(output_file, "w") as file:
    file.write(modified_html)
print(f"\nModified HTML saved to {output_file}")