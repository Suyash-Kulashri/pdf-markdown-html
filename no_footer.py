import PyPDF2
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.generic import RectangleObject
import os

def remove_header_footer(input_pdf_path, output_pdf_path, top_margin=72, bottom_margin=72):
    """
    Remove headers and footers from a PDF by cropping specified margins.

    Args:
        input_pdf_path (str): Path to the input PDF file.
        output_pdf_path (str): Path where the output PDF will be saved.
        top_margin (float): Height of the header to remove (in points, default 1 inch = 72 points).
        bottom_margin (float): Height of the footer to remove (in points, default 1 inch = 72 points).

    Returns:
        bool: True if successful, False if an error occurs.
    """
    try:
        # Check if input file exists
        if not os.path.exists(input_pdf_path):
            print(f"Error: Input file '{input_pdf_path}' does not exist.")
            return False

        # Open the input PDF
        with open(input_pdf_path, 'rb') as input_file:
            reader = PdfReader(input_file)
            writer = PdfWriter()

            # Process each page
            for page_num in range(len(reader.pages)):
                page = reader.pages[page_num]
                
                # Get the original page dimensions
                media_box = page.mediabox
                width = float(media_box.width)
                height = float(media_box.height)
                
                # Validate margins
                if top_margin < 0 or bottom_margin < 0 or (top_margin + bottom_margin) >= height:
                    print(f"Error: Invalid margins (top: {top_margin}, bottom: {bottom_margin}) for page {page_num + 1}.")
                    return False
                
                # Define new crop box coordinates
                new_crop_box = [
                    float(media_box.lower_left[0]),  # Left remains unchanged
                    float(media_box.lower_left[1]) + bottom_margin,  # Adjust bottom
                    float(media_box.upper_right[0]),  # Right remains unchanged
                    float(media_box.upper_right[1]) - top_margin  # Adjust top
                ]
                
                # Create a RectangleObject for the new crop box
                rect = RectangleObject(new_crop_box)
                
                # Apply the new crop box
                page.mediabox = rect
                page.cropbox = rect
                
                # Add the modified page to the writer
                writer.add_page(page)

            # Save the output PDF
            with open(output_pdf_path, 'wb') as output_file:
                writer.write(output_file)
            print(f"Successfully saved output PDF to '{output_pdf_path}'.")
            return True

    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return False

# Example usage
if __name__ == "__main__":
    input_path = "LCM3000.pdf"  # Replace with your input PDF path
    output_path = "output_no_header_footer.pdf"  # Replace with desired output path
    remove_header_footer(input_path, output_path, top_margin=72, bottom_margin=72)