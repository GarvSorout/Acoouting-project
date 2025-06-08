# Basic Email-to-Accounting Automation System

This system automates the process of converting emails containing financial documents (invoices, receipts, statements) into accounting entries. It helps accountants save time by eliminating manual data entry and document searching.

## Features

- **Email Monitoring**: Automatically monitors specified email inboxes for new financial documents
- **Document Processing**: 
  - Extracts text from PDFs, images, and email bodies
  - Uses OCR for scanned documents
  - Identifies key information like dates, amounts, vendors, and invoice numbers
- **Smart Matching**: 
  - Uses fuzzy matching to categorize transactions
  - Learns from corrections to improve accuracy over time
  - Matches documents to existing transactions in the accounting system
- **Accounting Integration**:
  - Automatically creates draft entries in the accounting system
  - Provides a web interface for review and approval
  - Maintains an audit trail of all automated entries

## Setup

1. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Install Tesseract OCR:
   ```bash
   # For macOS
   brew install tesseract
   
   # For Ubuntu/Debian
   sudo apt-get install tesseract-ocr
   ```

3. Create a `.env` file with your configuration:
   ```
   EMAIL_HOST=imap.gmail.com
   EMAIL_USER=your-email@gmail.com
   EMAIL_PASSWORD=your-app-specific-password
   MONGODB_URI=your-mongodb-connection-string
   ```

## Usage

1. Start the server:
   ```bash
   uvicorn main:app --reload
   ```

2. Access the web interface at `http://localhost:8000`

3. Configure email folders to monitor and accounting categories

4. Review and approve automated entries through the web interface

## Architecture

- FastAPI backend for the web interface and API
- MongoDB for storing processed documents and matching history
- Machine learning model for transaction categorization
- Email monitoring service using IMAP
- OCR processing pipeline for document text extraction

## Security Notes

- Uses app-specific passwords for email access
- Stores sensitive information in environment variables
- Implements approval workflow before finalizing entries
- Maintains audit logs of all automated actions 