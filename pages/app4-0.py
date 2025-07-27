import streamlit as st
import PyPDF2
import pandas as pd
from openai import OpenAI
import os
import re
from io import StringIO
from dotenv import load_dotenv
# Load environment variables
load_dotenv()

# Streamlit app title
st.title("PDF Version Change Predictor")

# Input for OpenAI API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    api_key = st.text_input("Enter your OpenAI API Key", type="password")

# Text area for user to specify the series or context
series_query = st.text_area("Specify the series or context for prediction (e.g., 'Predict changes for the next version of a financial report series' or 'Generate datasheet for 700W model based on 300W model' or 'Specifications unchanged, make minimal updates')", 
                           placeholder="Enter the series or context here...")

# File uploader for PDF
uploaded_file = st.file_uploader("Upload a PDF file", type="pdf")

def extract_text_and_tables(pdf_file):
    """Extract text and potential tables from PDF."""
    text = ""
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # Attempt to detect tables (basic regex-based detection)
        table_pattern = r'(\w+\s+\w+\s+\d+\s+\d+\n)+'
        tables = re.findall(table_pattern, text)
        table_data = []
        for table in tables:
            # Split table into rows and columns
            rows = table.strip().split('\n')
            table_content = [row.split() for row in rows]
            table_data.append(pd.DataFrame(table_content))
        return text, table_data
    except Exception as e:
        st.error(f"Error extracting PDF: {e}")
        return None, None

def generate_markdown(text, tables, api_key, series_query):
    """Generate Markdown with predictions using OpenAI LLM."""
    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""
        You are an expert engineering assistant tasked with generating a new, complete datasheet or document for the next version of a product based on the provided PDF content and user-specified series/context.

        **Series/Context:** {series_query}

        **CRITICAL Instructions:**
        - **Analyze Source:** Read the provided PDF content to understand its structure, formatting, and technical parameters.
        - **Identify Target:** Determine the target product model or version from the series/context. If the series/context specifies a new model (e.g., 'Generate datasheet for 700W model based on 300W model'), create a new datasheet for that model. If it indicates unchanged or nearly same specifications (e.g., 'Specifications unchanged'), use the original PDF content as the base and make only minimal, necessary changes as specified.
        - **Scale Parameters Logically (if applicable):**
          - **Electrical:** For a new model, intelligently extrapolate specifications (e.g., if scaling from a 300W to a 700W power supply, proportionally scale power, current, etc.). Keep constant parameters like input voltage range unchanged unless specified.
          - **Physical:** Logically scale physical properties for a new model. A higher power unit should be larger and heavier. Estimate new dimensions (Length, Width, Height) and weight, and include reasoning in parentheses (e.g., '(Dimensions scaled proportionally to the ~133% increase in power)').
        - **Preserve Unchanged Content:** If the series/context indicates unchanged or nearly same specifications, preserve the original PDF content verbatim, including structure and wording, unless changes are explicitly required.
        - **No Placeholders or Summaries:** Generate a complete, standalone document. Do not use phrases like 'This section remains the same,' 'Details as per original,' or '(Identical to source)'. Include full content for every section, either by scaling data or copying verbatim if unchanged.
        - **Maintain Structure:** Replicate the exact section structure of the source PDF, including all sections and subsections.
        - **Format as Markdown:** Use clean Markdown with:
          - Main heading (#) for the document title
          - Subheadings (##) for major sections
          - Sub-subheadings (###) for minor sections
          - Bold text (**text**) for key terms or modified sections
          - Properly formatted tables with consistent column counts per table block (start a new table block if column structures differ)
        - **Table Formatting:** Ensure every row in a single Markdown table block has the same number of columns. If tables are detected, include them with predicted changes relevant to the series/context.
        - Use clear, concise language.

        **Source PDF Content:**
        ```
        {text}
        ```

        **Generated Markdown Datasheet for the Target Product:**
        """
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates structured Markdown."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1500
        )
        markdown_content = response.choices[0].message.content

        # Append tables to Markdown if they exist
        if tables:
            markdown_content += "\n\n## Predicted Table Updates\n"
            for i, table in enumerate(tables):
                markdown_content += f"\n### Table {i+1}\n"
                markdown_content += table.to_markdown(index=False) + "\n"
                markdown_content += f"\n**Predicted Change**: The values in Table {i+1} may change based on trends in the {series_query} series.\n"

        return markdown_content
    except Exception as e:
        st.error(f"Error generating Markdown: {e}")
        return None

def save_markdown(markdown_content):
    """Save Markdown content to a file in the root directory."""
    try:
        filename = "predicted_changes.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        return filename
    except Exception as e:
        st.error(f"Error saving Markdown: {e}")
        return None

# Process uploaded PDF
if uploaded_file and api_key and series_query:
    with st.spinner("Processing PDF and generating predictions..."):
        # Extract text and tables
        text, tables = extract_text_and_tables(uploaded_file)
        
        if text:
            # Generate Markdown with predictions
            markdown_content = generate_markdown(text, tables, api_key, series_query)
            
            if markdown_content:
                # Save Markdown file
                filename = save_markdown(markdown_content)
                
                if filename:
                    st.success(f"Markdown file saved as {filename}")
                    
                    # Display Markdown content
                    st.subheader("Generated Markdown Content")
                    st.markdown(markdown_content)
else:
    if not api_key:
        st.warning("Please enter your OpenAI API key.")
    if not uploaded_file:
        st.warning("Please upload a PDF file.")
    if not series_query:
        st.warning("Please specify the series or context for prediction.")