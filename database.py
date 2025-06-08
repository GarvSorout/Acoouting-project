from pymongo import MongoClient
from datetime import datetime
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv
import logging
import certifi
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
import json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom JSON encoder to handle ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        if isinstance(o, datetime):
            return o.isoformat()
        return super().default(o)

# Pydantic models with custom JSON serialization
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")
        return field_schema

class DocumentModel(BaseModel):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    text: str
    amounts: List[float]
    dates: List[datetime]
    invoice_numbers: List[str]
    vendor_name: Optional[str]
    content_type: str
    original_content: Optional[bytes] = None
    email_subject: Optional[str] = None
    email_sender: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
        json_encoders={ObjectId: str, bytes: lambda x: None}  # Don't serialize binary data
    )

class Database:
    def __init__(self):
        self.client = None
        self.db = None

    def connect(self):
        """Connect to MongoDB"""
        logger.info("Connecting to MongoDB...")
        try:
            # Get MongoDB connection string from environment variable
            mongo_url = os.getenv("MONGODB_URI")
            if not mongo_url:
                raise ValueError("Missing MONGODB_URI in environment variables")
            
            # Use certifi for SSL certificate verification
            self.client = MongoClient(mongo_url, tlsCAFile=certifi.where())
            self.db = self.client.accounting_automation
            
            # Drop existing unique index if it exists
            try:
                self.db.documents.drop_index("email_id_1")
                logger.info("Dropped existing email_id unique index")
            except Exception:
                pass  # Index might not exist
            
            # Create indexes
            self.create_indexes()
            
            logger.info("Connected to MongoDB successfully")
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise

    def create_indexes(self):
        """Create necessary indexes"""
        try:
            self.db.documents.create_index("status")
            self.db.documents.create_index("created_at")
            self.db.documents.create_index("vendor_name")
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
            raise

    def store_document(self, *, email_id: int, extracted_data: Dict[str, Any], original_content: bytes = None, content_type: str = None, subject: str = None, sender: str = None) -> None:
        """Store a processed document"""
        try:
            logger.info(f"Preparing to store document from email {email_id}")
            
            # Create document model
            document = {
                "email_id": str(email_id),
                "text": extracted_data.get("text", ""),
                "amounts": extracted_data.get("amounts", []),
                "dates": extracted_data.get("dates", []),
                "invoice_numbers": extracted_data.get("invoice_numbers", []),
                "vendor_name": extracted_data.get("vendor_name"),
                "content_type": content_type or extracted_data.get("content_type", "unknown"),
                "original_content": original_content,
                "email_subject": subject,
                "email_sender": sender,
                "status": "pending",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            
            logger.info(f"Document prepared with vendor: {document['vendor_name']}, amounts: {document['amounts']}")
            
            # Insert document
            self.db.documents.insert_one(document)
            logger.info("Document stored successfully")
        except Exception as e:
            if "duplicate key error" in str(e):
                logger.warning(f"Document for email {email_id} already exists, skipping")
            else:
                logger.error(f"Error storing document: {str(e)}")
                raise

    def get_pending_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending documents"""
        try:
            logger.info(f"Fetching up to {limit} pending documents")
            cursor = self.db.documents.find({"status": "pending"}).limit(limit)
            documents = list(cursor)
            for doc in documents:
                doc["_id"] = str(doc["_id"])
            logger.info(f"Found {len(documents)} pending documents")
            return documents
        except Exception as e:
            logger.error(f"Failed to fetch pending documents: {str(e)}")
            raise

    def update_document_status(self, doc_id: str, status: str) -> bool:
        """Update document status"""
        try:
            result = self.db.documents.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update document status: {str(e)}")
            raise

    def get_document_stats(self) -> Dict[str, int]:
        """Get document processing statistics"""
        try:
            pipeline = [
                {
                    "$group": {
                        "_id": "$status",
                        "count": {"$sum": 1}
                    }
                }
            ]
            
            cursor = self.db.documents.aggregate(pipeline)
            stats = {"total": 0, "pending": 0, "processed": 0, "error": 0}
            
            for result in cursor:
                status = result["_id"]
                count = result["count"]
                stats[status] = count
                stats["total"] += count
                
            return stats
        except Exception as e:
            logger.error(f"Failed to get document stats: {str(e)}")
            raise

    def close(self):
        """Close database connection"""
        if self.client:
            self.client.close()

    def store_document(self, 
                      email_id: str,
                      extracted_data: Dict,
                      original_content: bytes,
                      content_type: str,
                      subject: str,
                      sender: str) -> str:
        """Store processed document and its extracted information"""
        try:
            logger.info(f"Preparing to store document from email {email_id}")
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
                'status': 'pending_review',
                'accounting_entry': None,
                'confidence_score': self._calculate_confidence_score(extracted_data),
                'manual_corrections': {},
                'processing_history': []
            }

            logger.info(f"Document prepared with vendor: {document['vendor_name']}, amounts: {document['amounts']}")
            result = self.db.documents.insert_one(document)
            logger.info(f"Document stored successfully with ID: {result.inserted_id}")
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
            logger.info(f"Fetching up to {limit} pending documents")
            documents = self.db.documents.find(
                {'status': 'pending_review'}
            ).sort('processed_date', 1).limit(limit)
            
            result = list(documents)
            logger.info(f"Found {len(result)} pending documents")
            return result

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