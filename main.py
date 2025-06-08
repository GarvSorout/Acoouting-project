import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import uvicorn
import asyncio
import logging
from email_monitor import EmailMonitor
from document_processor import DocumentProcessor
from database import Database, DocumentModel

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Email-to-Accounting Automation")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
email_monitor = EmailMonitor()
document_processor = DocumentProcessor()
db = Database()
db.connect()

# Background task to check emails periodically
def check_emails():
    try:
        logger.info("Checking for new emails...")
        # Check for new emails
        new_emails = email_monitor.check_new_emails()
        logger.info(f"Found {len(new_emails)} new emails")
        
        for email in new_emails:
            try:
                logger.info(f"Processing email with subject: {email.subject}")
                
                # Process attachments
                if email.attachments:
                    for attachment in email.attachments:
                        logger.info(f"Processing attachment: {attachment.filename}")
                        doc_data = document_processor.process_document(
                            attachment.content,
                            attachment.content_type,
                            email.subject,
                            email.sender
                        )
                        
                        # Store the processed document
                        try:
                            db.store_document(
                                email_id=email.id,
                                extracted_data=doc_data,
                                original_content=attachment.content,
                                content_type=attachment.content_type,
                                subject=email.subject,
                                sender=email.sender
                            )
                            logger.info(f"Successfully stored document from email {email.id}")
                        except Exception as e:
                            logger.error(f"Failed to store document from email {email.id}: {str(e)}")
                
                # Mark email as processed
                email_monitor.mark_as_processed(email.id)
                logger.info(f"Marked email as processed: {email.id}")
                
            except Exception as e:
                logger.error(f"Error processing email {email.id}: {str(e)}")
                continue
    except Exception as e:
        logger.error(f"Error in check_emails: {str(e)}")

# Pydantic models for API
class DocumentUpdate(BaseModel):
    status: str
    accounting_entry: Optional[Dict] = None
    corrections: Optional[Dict] = None

class DateRange(BaseModel):
    start_date: datetime
    end_date: datetime

@app.on_event("startup")
async def startup_event():
    """Run on startup"""
    # Start email checking in background
    asyncio.create_task(check_emails_periodically())

async def check_emails_periodically():
    """Periodically check for new emails"""
    while True:
        try:
            check_emails()
            await asyncio.sleep(60)  # Check every minute
        except Exception as e:
            logger.error(f"Error in periodic email check: {str(e)}")
            await asyncio.sleep(60)  # Wait before retrying

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    db.close()

@app.get("/documents/pending", response_model=List[DocumentModel])
def get_pending_documents(limit: int = 10):
    """Get pending documents"""
    try:
        documents = db.get_pending_documents(limit)
        return documents
    except Exception as e:
        logger.error(f"Error fetching pending documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/{document_id}")
def get_document(document_id: str):
    """Get specific document by ID"""
    document = db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.post("/documents/{doc_id}/status/{status}")
def update_document_status(doc_id: str, status: str):
    """Update document status"""
    try:
        success = db.update_document_status(doc_id, status)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found")
        return {"message": "Status updated successfully"}
    except Exception as e:
        logger.error(f"Error updating document status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/documents/search")
def search_documents(
    vendor_name: Optional[str] = None,
    invoice_number: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None
):
    """Search documents based on criteria"""
    date_range = None
    if start_date and end_date:
        date_range = (start_date, end_date)
    
    documents = db.search_documents(
        vendor_name=vendor_name,
        invoice_number=invoice_number,
        date_range=date_range,
        status=status
    )
    
    return {"documents": documents}

@app.get("/stats")
def get_stats():
    """Get document processing statistics"""
    try:
        return db.get_document_stats()
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000) 