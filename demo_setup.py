import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
import random
from dotenv import load_dotenv
import time
from reportlab.pdfgen import canvas
from io import BytesIO
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

def create_pdf_invoice(vendor_name, amount, invoice_number):
    """Create a PDF invoice"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    
    # Add invoice header
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, 800, "INVOICE")
    
    # Add vendor info
    c.setFont("Helvetica", 12)
    c.drawString(50, 750, vendor_name)
    c.drawString(50, 735, "123 Business St")
    c.drawString(50, 720, "Business City, BC 12345")
    
    # Add invoice details
    c.drawString(50, 680, f"Date: {datetime.now().strftime('%B %d, %Y')}")
    c.drawString(50, 665, f"Invoice #: {invoice_number}")
    
    # Add amount
    c.drawString(50, 600, "Description")
    c.drawString(400, 600, "Amount")
    c.line(50, 595, 550, 595)
    c.drawString(50, 575, "Professional Services")
    c.drawString(400, 575, f"${amount:,.2f}")
    
    c.line(50, 550, 550, 550)
    c.drawString(400, 525, f"Total Due: ${amount:,.2f}")
    
    # Add footer
    c.drawString(50, 100, "Please pay within 30 days.")
    c.drawString(50, 85, "Thank you for your business!")
    
    c.save()
    return buffer.getvalue()

def send_test_email(subject, body, pdf_content):
    """Send a test email with PDF attachment"""
    sender_email = os.getenv('EMAIL_USER')
    sender_password = os.getenv('EMAIL_PASSWORD')
    
    if not all([sender_email, sender_password]):
        raise ValueError("Missing email credentials in .env file")
    
    # Create message
    msg = MIMEMultipart()
    msg['From'] = f"Demo Vendor <{sender_email}>"
    msg['To'] = sender_email
    msg['Subject'] = subject
    
    # Add body
    msg.attach(MIMEText(body, 'plain'))
    
    # Add PDF attachment
    pdf_attachment = MIMEApplication(pdf_content, _subtype='pdf')
    pdf_attachment.add_header('Content-Disposition', 'attachment', filename='invoice.pdf')
    msg.attach(pdf_attachment)
    
    # Send email
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, sender_password)
        server.send_message(msg)

def run_demo():
    """Run a demonstration of the system"""
    logger.info("Starting Email-to-Accounting Demo...")
    
    vendors = [
        "Tech Solutions Inc.",
        "Office Supplies Co.",
        "Consulting Partners LLC",
        "Marketing Experts Group",
        "Cloud Services Pro"
    ]
    
    # Send a few test invoices
    for i in range(5):
        vendor = random.choice(vendors)
        amount = random.uniform(100, 5000)
        invoice_number = f"INV-2024-{random.randint(1000, 9999)}"
        
        # Create PDF invoice
        pdf_content = create_pdf_invoice(vendor, amount, invoice_number)
        
        # Create and send invoice
        subject = f"Invoice {invoice_number} from {vendor}"
        body = "Please find attached invoice for recent services."
        
        logger.info(f"\nSending test email {i+1}/5:")
        logger.info(f"Vendor: {vendor}")
        logger.info(f"Amount: ${amount:,.2f}")
        logger.info(f"Invoice #: {invoice_number}")
        
        try:
            send_test_email(subject, body, pdf_content)
            logger.info("✓ Email sent successfully with PDF attachment")
            time.sleep(2)  # Wait between emails
        except Exception as e:
            logger.error(f"✗ Error sending email: {str(e)}")
    
    logger.info("\nDemo emails have been sent!")
    logger.info("\nNext steps:")
    logger.info("1. Start the application: python main.py")
    logger.info("2. Wait a few minutes for the background task to process the emails")
    logger.info("3. Check the web interface at http://localhost:8000/docs")
    logger.info("4. Use the /documents/pending endpoint to see processed documents")

if __name__ == "__main__":
    run_demo() 