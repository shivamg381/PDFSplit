import fitz  # PyMuPDF
from PyPDF2 import PdfReader, PdfWriter
from pdf2image import convert_from_path
import pytesseract
import cv2
import numpy as np
from PIL import ImageEnhance, Image

def extract_footer_text(pdf_path):
    """
    Extracts footer text from each page using position-based detection.
    Falls back to OCR for scanned documents.
    """
    footers = []
    
    try:
        # Open PDF with PyMuPDF
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get page dimensions
            page_height = page.rect.height
            
            # Define footer region (bottom 10% of page)
            footer_region = fitz.Rect(
                0,  # left
                page_height * 0.9,  # top (90% down the page)
                page.rect.width,  # right
                page_height  # bottom
            )
            
            # Extract text blocks from the footer region
            text_blocks = page.get_text("blocks", clip=footer_region)
            
            if text_blocks:
                # Sort blocks by vertical position (bottom to top)
                text_blocks.sort(key=lambda b: -b[1])  # b[1] is y-coordinate
                
                # Get the bottommost text block
                footer_text = text_blocks[0][4].strip()  # b[4] is the text content
                footers.append((page_num + 1, footer_text))
            else:
                # If no text blocks found, try OCR
                raise ValueError("No text found in footer region")
                
        doc.close()
        return footers
        
    except Exception as e:
        print(f"Falling back to OCR due to: {str(e)}")
        try:          
            images = convert_from_path(pdf_path, dpi=300)  # Higher DPI for better quality
            footers = []
            
            for i, image in enumerate(images):
                width, height = image.size
                
                # Crop footer area (adjust percentage if needed)
                footer_box = (
                    0,                    # left
                    int(height * 0.85),   # top (85% down)
                    width,                # right
                    height               # bottom
                )
                footer_image = image.crop(footer_box)
                
                # Convert PIL Image to OpenCV format
                footer_cv = cv2.cvtColor(np.array(footer_image), cv2.COLOR_RGB2BGR)
                
                # Image preprocessing
                # 1. Convert to grayscale
                gray = cv2.cvtColor(footer_cv, cv2.COLOR_BGR2GRAY)
                
                # 2. Apply thresholding to handle different backgrounds
                thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
                
                # 3. Denoise
                denoised = cv2.fastNlMeansDenoising(thresh)
                
                # 4. Increase contrast
                contrast = ImageEnhance.Contrast(Image.fromarray(denoised))
                enhanced_image = contrast.enhance(2.0)  # Increase contrast factor
                
                # 5. Scale up image
                scaled = cv2.resize(np.array(enhanced_image), None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
                
                # Apply OCR with improved configuration
                footer_text = pytesseract.image_to_string(
                    scaled,
                    config='--psm 6 --oem 3 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_. '
                ).strip()
                
                # Clean up the extracted text
                footer_text = ' '.join(footer_text.split())  # Remove extra whitespace
                if len(footer_text) > 5:  # Only keep meaningful text
                    footers.append((i + 1, footer_text))
                else:
                    # Try alternative preprocessing if first attempt failed
                    # Apply adaptive thresholding
                    adaptive_thresh = cv2.adaptiveThreshold(
                        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
                    )
                    footer_text = pytesseract.image_to_string(
                        adaptive_thresh,
                        config='--psm 6 --oem 3'
                    ).strip()
                    footers.append((i + 1, footer_text))
                    
            return footers
        
        except Exception as ocr_error:
            print(f"OCR processing failed: {str(ocr_error)}")
            return []

def split_pdf_by_footer(pdf_path):
    """
    Splits the PDF based on changes in the detected footer.
    """
    footers = extract_footer_text(pdf_path)
    for f in footers:
        print(f)
    pdf_reader = PdfReader(pdf_path)
    
    prev_footer = None
    writer = None
    file_parts = []
    
    for i, (page_num, footer) in enumerate(footers):
        if footer != prev_footer:
            if writer:
                output_path = f"split_part_{len(file_parts) + 1}.pdf"
                with open(output_path, "wb") as out_file:
                    writer.write(out_file)
                file_parts.append(output_path)
            writer = PdfWriter()
        writer.add_page(pdf_reader.pages[page_num - 1])
        prev_footer = footer
    if writer:
        output_path = f"split_part_{len(file_parts) + 1}.pdf"
        with open(output_path, "wb") as out_file:
            writer.write(out_file)
        file_parts.append(output_path)
    return file_parts


# Usage
pdf_path = r"C:\Users\1930205\Downloads\GE Demo.pdf" # Change this to your actual file path
split_files = split_pdf_by_footer(pdf_path)
print("Split PDFs:", split_files)