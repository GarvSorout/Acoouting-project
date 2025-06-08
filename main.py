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
from database import Database

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

# Background task to check emails periodically
async def check_emails_periodically():
    while True:
        try:
            # Check for new emails
            new_emails = email_monitor.check_new_emails()
            
            for email in new_emails:
                # Process each attachment
                for attachment in email['attachments']:
                    # Extract information from document
                    extracted_data = document_processor.process_document(
                        content=attachment['content'],
                        content_type=attachment['content_type'],
                        subject=email['subject'],
                        sender=email['sender']
                    )
                    
                    # Store in database
                    db.store_document(
                        email_id=email['email_id'],
                        extracted_data=extracted_data,
                        original_content=attachment['content'],
                        content_type=attachment['content_type'],
                        subject=email['subject'],
                        sender=email['sender']
                    )
                
                # Mark email as processed
                email_monitor.mark_as_processed(email['email_id'])
                
            # Wait for 5 minutes before next check
            await asyncio.sleep(300)
            
        except Exception as e:
            logger.error(f"Error in email checking task: {str(e)}")
            await asyncio.sleep(60)  # Wait a minute before retrying

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
    # Start background task
    asyncio.create_task(check_emails_periodically())

@app.get("/documents/pending")
async def get_pending_documents(limit: int = Query(10, gt=0, le=100)):
    """Get documents pending review"""
    documents = db.get_pending_documents(limit)
    return {"documents": documents}

@app.get("/documents/{document_id}")
async def get_document(document_id: str):
    """Get specific document by ID"""
    document = db.get_document_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document

@app.put("/documents/{document_id}")
async def update_document(document_id: str, update: DocumentUpdate):
    """Update document status and accounting entry"""
    success = db.update_document_status(
        document_id=document_id,
        status=update.status,
        accounting_entry=update.accounting_entry,
        corrections=update.corrections
    )
    
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return {"status": "success"}

@app.get("/documents/search")
async def search_documents(
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
async def get_stats():
    """Get system statistics"""
    try:
        # Get counts for different document statuses
        pending = len(db.search_documents(status="pending_review"))
        approved = len(db.search_documents(status="approved"))
        rejected = len(db.search_documents(status="rejected"))
        
        # Get documents processed in last 24 hours
        yesterday = datetime.utcnow() - timedelta(days=1)
        recent = len(db.search_documents(date_range=(yesterday, datetime.utcnow())))
        
        return {
            "total_documents": pending + approved + rejected,
            "pending_review": pending,
            "approved": approved,
            "rejected": rejected,
            "processed_last_24h": recent
        }
    
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting statistics")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 