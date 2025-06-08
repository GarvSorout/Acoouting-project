import pytesseract
from PIL import Image
import pdf2image
import io
import re
from typing import Dict, List, Optional
import logging
from datetime import datetime
import tempfile
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DocumentProcessor:
    def __init__(self):
        self.amount_pattern = r'\$?\d{1,3}(?:,\d{3})*(?:\.\d{2})?'
        self.date_patterns = [
            r'\d{2}/\d{2}/\d{4}',  # MM/DD/YYYY
            r'\d{2}-\d{2}-\d{4}',  # MM-DD-YYYY
            r'\d{4}-\d{2}-\d{2}',  # YYYY-MM-DD
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}'  # Month DD, YYYY
        ]
        self.invoice_patterns = [
            r'(?i)invoice\s*#?\s*([A-Z0-9-]+)',
            r'(?i)inv\s*#?\s*([A-Z0-9-]+)',
            r'(?i)bill\s*#?\s*([A-Z0-9-]+)'
        ]

    def process_image(self, image_data: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image)
            return text
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return ""

    def process_pdf(self, pdf_data: bytes) -> str:
        """Convert PDF to images and extract text using OCR"""
        try:
            # Save PDF data to temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(pdf_data)
                temp_pdf_path = temp_pdf.name

            # Convert PDF to images
            images = pdf2image.convert_from_path(temp_pdf_path)
            
            # Clean up temporary file
            os.unlink(temp_pdf_path)

            # Extract text from each image
            text = ""
            for image in images:
                text += pytesseract.image_to_string(image) + "\n"

            return text
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return ""

    def extract_amounts(self, text: str) -> List[float]:
        """Extract potential amount values from text"""
        amounts = []
        matches = re.finditer(self.amount_pattern, text)
        for match in matches:
            amount_str = match.group(0).replace('$', '').replace(',', '')
            try:
                amount = float(amount_str)
                amounts.append(amount)
            except ValueError:
                continue
        return amounts

    def extract_dates(self, text: str) -> List[datetime]:
        """Extract potential dates from text"""
        dates = []
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                date_str = match.group(0)
                try:
                    # Try different date formats
                    for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%B %d, %Y', '%B %d %Y']:
                        try:
                            date = datetime.strptime(date_str, fmt)
                            dates.append(date)
                            break
                        except ValueError:
                            continue
                except Exception:
                    continue
        return dates

    def extract_invoice_numbers(self, text: str) -> List[str]:
        """Extract potential invoice numbers from text"""
        invoice_numbers = []
        for pattern in self.invoice_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) > 0:
                    invoice_numbers.append(match.group(1))
        return invoice_numbers

    def extract_vendor_name(self, text: str, subject: str, sender: str) -> Optional[str]:
        """Attempt to extract vendor name from various sources"""
        # First try to extract from email sender
        email_parts = sender.split('<')
        if len(email_parts) > 1:
            vendor_name = email_parts[0].strip()
            if vendor_name:
                return vendor_name

        # Try to extract from subject
        if 'invoice' in subject.lower():
            parts = subject.split('from')
            if len(parts) > 1:
                return parts[1].strip()

        # Look for common patterns in text
        patterns = [
            r'(?i)from:\s*([A-Za-z0-9\s]+)(?=\n)',
            r'(?i)vendor:\s*([A-Za-z0-9\s]+)(?=\n)',
            r'(?i)company:\s*([A-Za-z0-9\s]+)(?=\n)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match and match.group(1).strip():
                return match.group(1).strip()

        return None

    def process_document(self, content: bytes, content_type: str, subject: str = "", sender: str = "") -> Dict:
        """Process document and extract relevant information"""
        try:
            # Extract text based on content type
            if content_type.startswith('image/'):
                text = self.process_image(content)
            elif content_type == 'application/pdf':
                text = self.process_pdf(content)
            else:
                logger.warning(f"Unsupported content type: {content_type}")
                return {}

            # Extract information
            amounts = self.extract_amounts(text)
            dates = self.extract_dates(text)
            invoice_numbers = self.extract_invoice_numbers(text)
            vendor_name = self.extract_vendor_name(text, subject, sender)

            return {
                'text': text,
                'amounts': amounts,
                'dates': dates,
                'invoice_numbers': invoice_numbers,
                'vendor_name': vendor_name,
                'content_type': content_type
            }

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {} 