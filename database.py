from pymongo import MongoClient
from datetime import datetime
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.mongo_uri = os.getenv('MONGODB_URI')
        if not self.mongo_uri:
            raise ValueError("Missing MONGODB_URI in .env file")
        
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client.accounting_automation
        
        # Create indexes
        self.db.documents.create_index([("email_id", 1)], unique=True)
        self.db.documents.create_index([("vendor_name", 1)])
        self.db.documents.create_index([("invoice_number", 1)])
        self.db.documents.create_index([("processed_date", 1)])
        self.db.documents.create_index([("status", 1)])

    def store_document(self, 
                      email_id: str,
                      extracted_data: Dict,
                      original_content: bytes,
                      content_type: str,
                      subject: str,
                      sender: str) -> str:
        """Store processed document and its extracted information"""
        try:
            document = {
                'email_id': email_id,
                'subject': subject,
                'sender': sender,
                'content_type': content_type,
                'extracted_text': extracted_data.get('text', ''),
                'amounts': extracted_data.get('amounts', []),
                'dates': extracted_data.get('dates', []),
                'invoice_numbers': extracted_data.get('invoice_numbers', []),
                'vendor_name': extracted_data.get('vendor_name'),
                'original_content': original_content,
                'processed_date': datetime.utcnow(),
                'status': 'pending_review',  # pending_review, approved, rejected
                'accounting_entry': None,  # Will store the generated accounting entry
                'confidence_score': self._calculate_confidence_score(extracted_data),
                'manual_corrections': {},  # Store any manual corrections made during review
                'processing_history': []  # Track changes and approvals
            }

            result = self.db.documents.insert_one(document)
            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Error storing document: {str(e)}")
            raise

    def _calculate_confidence_score(self, extracted_data: Dict) -> float:
        """Calculate confidence score based on extracted information completeness"""
        score = 0.0
        total_checks = 4  # vendor, amount, date, invoice number

        if extracted_data.get('vendor_name'):
            score += 1.0
        
        if extracted_data.get('amounts'):
            score += 1.0
        
        if extracted_data.get('dates'):
            score += 1.0
        
        if extracted_data.get('invoice_numbers'):
            score += 1.0

        return score / total_checks

    def update_document_status(self, 
                             document_id: str, 
                             status: str,
                             accounting_entry: Optional[Dict] = None,
                             corrections: Optional[Dict] = None) -> bool:
        """Update document status and store accounting entry"""
        try:
            update_data = {
                'status': status,
                'last_modified': datetime.utcnow()
            }

            if accounting_entry:
                update_data['accounting_entry'] = accounting_entry

            if corrections:
                update_data['manual_corrections'] = corrections

            # Add to processing history
            history_entry = {
                'timestamp': datetime.utcnow(),
                'status': status,
                'has_corrections': bool(corrections)
            }

            result = self.db.documents.update_one(
                {'_id': document_id},
                {
                    '$set': update_data,
                    '$push': {'processing_history': history_entry}
                }
            )

            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")
            return False

    def get_pending_documents(self, limit: int = 10) -> List[Dict]:
        """Get documents pending review"""
        try:
            documents = self.db.documents.find(
                {'status': 'pending_review'}
            ).sort('processed_date', 1).limit(limit)
            
            return list(documents)

        except Exception as e:
            logger.error(f"Error getting pending documents: {str(e)}")
            return []

    def get_document_by_id(self, document_id: str) -> Optional[Dict]:
        """Get document by ID"""
        try:
            return self.db.documents.find_one({'_id': document_id})
        except Exception as e:
            logger.error(f"Error getting document: {str(e)}")
            return None

    def search_documents(self,
                        vendor_name: Optional[str] = None,
                        invoice_number: Optional[str] = None,
                        date_range: Optional[tuple] = None,
                        status: Optional[str] = None) -> List[Dict]:
        """Search documents based on criteria"""
        try:
            query = {}
            
            if vendor_name:
                query['vendor_name'] = {'$regex': vendor_name, '$options': 'i'}
            
            if invoice_number:
                query['invoice_numbers'] = invoice_number
            
            if date_range:
                query['processed_date'] = {
                    '$gte': date_range[0],
                    '$lte': date_range[1]
                }
            
            if status:
                query['status'] = status

            documents = self.db.documents.find(query).sort('processed_date', -1)
            return list(documents)

        except Exception as e:
            logger.error(f"Error searching documents: {str(e)}")
            return [] 