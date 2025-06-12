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
            
            # Test connection
            self.client.admin.command('ping')
            
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
            self.db.documents.create_index("email_id")
            logger.info("Database indexes created successfully")
        except Exception as e:
            logger.error(f"Failed to create indexes: {str(e)}")
            raise

    def store_document(self, *, email_id: str, extracted_data: Dict[str, Any], 
                      original_content: bytes = None, content_type: str = None, 
                      subject: str = None, sender: str = None) -> str:
        """Store a processed document"""
        try:
            logger.info(f"Preparing to store document from email {email_id}")
            
            # Create document dictionary
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
            
            # Insert document and get the result
            result = self.db.documents.insert_one(document)
            document_id = str(result.inserted_id)
            
            logger.info(f"Document stored successfully with ID: {document_id}")
            return document_id
            
        except Exception as e:
            if "duplicate key error" in str(e):
                logger.warning(f"Document for email {email_id} already exists, skipping")
                return None
            else:
                logger.error(f"Error storing document: {str(e)}")
                raise

    def get_pending_documents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get pending documents"""
        try:
            logger.info(f"Fetching up to {limit} pending documents")
            cursor = self.db.documents.find({"status": "pending"}).limit(limit)
            documents = []
            
            for doc in cursor:
                # Convert ObjectId to string and remove binary content for API response
                doc["_id"] = str(doc["_id"])
                if "original_content" in doc:
                    doc["original_content"] = None  # Don't send binary data in API
                documents.append(doc)
                
            logger.info(f"Found {len(documents)} pending documents")
            return documents
        except Exception as e:
            logger.error(f"Failed to fetch pending documents: {str(e)}")
            raise

    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific document by ID"""
        try:
            doc = self.db.documents.find_one({"_id": ObjectId(document_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                if "original_content" in doc:
                    doc["original_content"] = None  # Don't send binary data in API
            return doc
        except Exception as e:
            logger.error(f"Failed to get document {document_id}: {str(e)}")
            return None

    def update_document_status(self, doc_id: str, status: str, 
                             accounting_entry: Optional[Dict] = None,
                             corrections: Optional[Dict] = None) -> bool:
        """Update document status"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            
            if accounting_entry:
                update_data["accounting_entry"] = accounting_entry
            if corrections:
                update_data["corrections"] = corrections
                
            result = self.db.documents.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update document status: {str(e)}")
            raise

    def search_documents(self, vendor_name: Optional[str] = None,
                        invoice_number: Optional[str] = None,
                        date_range: Optional[tuple] = None,
                        status: Optional[str] = None) -> List[Dict]:
        """Search documents based on criteria"""
        try:
            query = {}
            
            if vendor_name:
                query["vendor_name"] = {"$regex": vendor_name, "$options": "i"}
            if invoice_number:
                query["invoice_numbers"] = {"$in": [invoice_number]}
            if status:
                query["status"] = status
            if date_range:
                start_date, end_date = date_range
                query["created_at"] = {"$gte": start_date, "$lte": end_date}
                
            cursor = self.db.documents.find(query)
            documents = []
            
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if "original_content" in doc:
                    doc["original_content"] = None  # Don't send binary data in API
                documents.append(doc)
                
            return documents
        except Exception as e:
            logger.error(f"Failed to search documents: {str(e)}")
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
                if status in stats:
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
            logger.info("Database connection closed") 