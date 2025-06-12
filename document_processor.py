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
        logger.info("Initializing DocumentProcessor")
        # Improved patterns for better accuracy
        self.amount_patterns = [
            r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})',  # $1,234.56 format
            r'\$\s*\d+\.\d{2}',  # $123.45 format
            r'(?:Total|Amount|Due|Balance)[\s:]*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # Context-aware amounts
            r'(?:USD|CAD)?\s*\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d{2}))',  # Currency prefixed amounts
        ]
        
        self.date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',  # MM/DD/YYYY or M/D/YYYY
            r'\d{1,2}-\d{1,2}-\d{4}',  # MM-DD-YYYY or M-D-YYYY
            r'\d{4}-\d{1,2}-\d{1,2}',  # YYYY-MM-DD or YYYY-M-D
            r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',  # Full month names
            r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}'  # Abbreviated month names
        ]
        
        self.invoice_patterns = [
            r'(?i)invoice\s*#?\s*:?\s*([A-Z]{2,4}-\d{4}-\d{4,6})',  # INV-2024-123456 format
            r'(?i)inv\s*#?\s*:?\s*([A-Z]{2,4}-\d{4}-\d{4,6})',     # INV-2024-123456 format
            r'(?i)invoice\s*(?:number|no|#)\s*:?\s*([A-Z0-9-]{6,})', # Invoice Number: ABC-123
            r'(?i)bill\s*#?\s*:?\s*([A-Z0-9-]{6,})',               # Bill # ABC-123
            r'(?i)reference\s*#?\s*:?\s*([A-Z0-9-]{6,})',          # Reference # ABC-123
        ]

    def process_image(self, image_data: bytes) -> str:
        """Extract text from image using OCR"""
        try:
            logger.info("Processing image with OCR")
            image = Image.open(io.BytesIO(image_data))
            text = pytesseract.image_to_string(image)
            logger.info(f"Successfully extracted {len(text)} characters from image")
            return text
        except Exception as e:
            logger.error(f"Error processing image: {str(e)}")
            return ""

    def extract_text_from_pdf(self, pdf_data: bytes) -> str:
        """Convert PDF to images and extract text using OCR"""
        try:
            logger.info("Processing PDF document")
            # Save PDF data to temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                temp_pdf.write(pdf_data)
                temp_pdf_path = temp_pdf.name

            # Convert PDF to images
            images = pdf2image.convert_from_path(temp_pdf_path)
            logger.info(f"Converted PDF to {len(images)} images")
            
            # Clean up temporary file
            os.unlink(temp_pdf_path)

            # Extract text from each image
            text = ""
            for i, image in enumerate(images, 1):
                logger.info(f"Processing page {i} of PDF")
                text += pytesseract.image_to_string(image) + "\n"

            logger.info(f"Successfully extracted {len(text)} characters from PDF")
            return text
        except Exception as e:
            logger.error(f"Error processing PDF: {str(e)}")
            return ""

    def extract_amounts(self, text: str) -> List[float]:
        """Extract monetary amounts from text with improved precision"""
        amounts = []
        seen_amounts = set()  # Avoid duplicates
        
        # Look for amounts with dollar signs and context
        for pattern in self.amount_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                # Get the amount part (might be in a group or the whole match)
                if match.groups():
                    amount_str = match.group(1)
                else:
                    amount_str = match.group(0)
                
                # Clean up the amount string
                amount_str = re.sub(r'[^\d.,]', '', amount_str)
                amount_str = amount_str.replace(',', '')
                
                try:
                    amount = float(amount_str)
                    # Filter out unrealistic amounts (too small or too large)
                    if 0.01 <= amount <= 1000000 and amount not in seen_amounts:
                        amounts.append(amount)
                        seen_amounts.add(amount)
                except ValueError:
                    continue
        
        # Sort amounts by value (largest first, as main invoice amount is usually the largest)
        amounts.sort(reverse=True)
        logger.info(f"Found {len(amounts)} amounts in text")
        return amounts

    def extract_dates(self, text: str) -> List[datetime]:
        """Extract dates from text with improved parsing"""
        dates = []
        seen_dates = set()  # Avoid duplicates
        
        for pattern in self.date_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                date_str = match.group(0)
                
                # Try different date formats
                date_formats = [
                    '%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', 
                    '%B %d, %Y', '%B %d %Y', '%b %d, %Y', '%b %d %Y'
                ]
                
                for fmt in date_formats:
                    try:
                        date = datetime.strptime(date_str, fmt)
                        if date not in seen_dates:
                            dates.append(date)
                            seen_dates.add(date)
                        break
                    except ValueError:
                        continue
        
        logger.info(f"Found {len(dates)} dates in text")
        return dates

    def extract_invoice_numbers(self, text: str) -> List[str]:
        """Extract complete invoice numbers from text"""
        invoice_numbers = []
        seen_numbers = set()  # Avoid duplicates
        
        for pattern in self.invoice_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                if len(match.groups()) > 0:
                    invoice_num = match.group(1).strip()
                    if invoice_num and invoice_num not in seen_numbers:
                        invoice_numbers.append(invoice_num)
                        seen_numbers.add(invoice_num)
        
        # Also look for standalone patterns that look like invoice numbers
        standalone_patterns = [
            r'\b([A-Z]{2,4}-\d{4}-\d{4,6})\b',  # INV-2024-123456
            r'\b([A-Z]{3,}\d{6,})\b',           # ABC123456
        ]
        
        for pattern in standalone_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                invoice_num = match.group(1).strip()
                if invoice_num and invoice_num not in seen_numbers and len(invoice_num) >= 6:
                    invoice_numbers.append(invoice_num)
                    seen_numbers.add(invoice_num)
        
        logger.info(f"Found {len(invoice_numbers)} invoice numbers in text")
        return invoice_numbers

    def extract_vendor_name(self, text: str, subject: str, sender: str) -> Optional[str]:
        """Extract vendor name with improved logic"""
        logger.info("Attempting to extract vendor name")
        
        # First, try to extract from document text (most accurate)
        text_lines = text.split('\n')
        
        # Look for company name patterns in the first few lines of the document
        for i, line in enumerate(text_lines[:5]):
            line = line.strip()
            # Skip empty lines and lines that look like headers
            if not line or line.upper() in ['INVOICE', 'BILL', 'STATEMENT']:
                continue
            
            # Look for lines that contain company indicators
            company_indicators = ['LLC', 'Inc', 'Corp', 'Ltd', 'Company', 'Partners', 'Group', 'Solutions']
            if any(indicator in line for indicator in company_indicators):
                # Clean up the line
                vendor_name = re.sub(r'[^\w\s&.,]', '', line).strip()
                if len(vendor_name) > 3:
                    logger.info(f"Found vendor name from document: {vendor_name}")
                    return vendor_name
        
        # Try to extract from subject line
        if 'from' in subject.lower():
            parts = subject.lower().split('from')
            if len(parts) > 1:
                vendor_name = parts[1].strip()
                # Clean up common email artifacts
                vendor_name = re.sub(r'<.*?>', '', vendor_name).strip()
                if len(vendor_name) > 3:
                    logger.info(f"Found vendor name from subject: {vendor_name}")
                    return vendor_name
        
        # Finally, try to extract from email sender
        if '<' in sender:
            vendor_name = sender.split('<')[0].strip()
        else:
            vendor_name = sender.split('@')[0] if '@' in sender else sender
        
        # Clean up the vendor name
        vendor_name = re.sub(r'[^\w\s&.,]', '', vendor_name).strip()
        
        if vendor_name and len(vendor_name) > 3:
            logger.info(f"Found vendor name from sender: {vendor_name}")
            return vendor_name

        logger.warning("No vendor name found")
        return None

    def process_document(self, content: bytes, content_type: str, subject: str = "", sender: str = "") -> Dict:
        """Process document and extract relevant information"""
        try:
            logger.info(f"Processing document of type: {content_type}")
            # Extract text based on content type
            if content_type.startswith('image/'):
                text = self.process_image(content)
            elif content_type == 'application/pdf':
                text = self.extract_text_from_pdf(content)
            else:
                logger.warning(f"Unsupported content type: {content_type}")
                return {}

            if not text:
                logger.warning("No text extracted from document")
                return {}

            # Extract information with improved algorithms
            amounts = self.extract_amounts(text)
            dates = self.extract_dates(text)
            invoice_numbers = self.extract_invoice_numbers(text)
            vendor_name = self.extract_vendor_name(text, subject, sender)

            result = {
                'text': text,
                'amounts': amounts,
                'dates': dates,
                'invoice_numbers': invoice_numbers,
                'vendor_name': vendor_name,
                'content_type': content_type
            }

            logger.info(f"Document processing complete. Found: {len(amounts)} amounts, {len(dates)} dates, {len(invoice_numbers)} invoice numbers")
            return result

        except Exception as e:
            logger.error(f"Error processing document: {str(e)}")
            return {} 