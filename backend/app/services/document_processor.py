"""
Document processor - extracts tables and text from PDFs using pdfplumber.

Tables go to SQL, text gets chunked and embedded for vector search.
"""
from typing import Dict, List, Any
import pdfplumber
import re
from app.core.config import settings
from app.services.table_parser import TableParser
from app.services.vector_store import VectorStore
from app.db.session import SessionLocal


class DocumentProcessor:
    """Process PDF documents - extract tables and text"""
    
    def __init__(self):
        self.table_parser = TableParser()
        self.vector_store = VectorStore()
    
    async def process_document(self, file_path: str, document_id: int, fund_id: int) -> Dict[str, Any]:
        """
        Process a PDF document
        
        Args:
            file_path: Path to the PDF file
            document_id: Database document ID
            fund_id: Fund ID
            
        Returns:
            Processing result with statistics
        """
        db = SessionLocal()
        
        try:
            # Extract content from PDF
            tables, text_content = self._extract_pdf_content(file_path)
            
            # Parse tables and store in database
            table_stats = self.table_parser.parse_tables(tables, db, fund_id)
            
            # Chunk text content
            chunks = self._chunk_text(text_content)
            
            # Store chunks in vector database
            chunk_count = 0
            for chunk in chunks:
                try:
                    await self.vector_store.add_document(
                        content=chunk["text"],
                        metadata={
                            "document_id": document_id,
                            "fund_id": fund_id,
                            "page": chunk["page"],
                            "chunk_index": chunk["chunk_index"]
                        }
                    )
                    chunk_count += 1
                except Exception as e:
                    print(f"Error storing chunk: {e}")
            
            return {
                "status": "completed",
                "statistics": {
                    "pages_processed": len(text_content),
                    "tables_found": len(tables),
                    "capital_calls": table_stats["capital_calls"],
                    "distributions": table_stats["distributions"],
                    "adjustments": table_stats["adjustments"],
                    "text_chunks": chunk_count,
                    "errors": table_stats["errors"]
                }
            }
            
        except Exception as e:
            print(f"Error processing document: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
        finally:
            db.close()
    
    def _extract_pdf_content(self, file_path: str) -> tuple:
        """Extract tables and text from PDF"""
        tables = []
        text_content = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract tables from page
                page_tables = page.extract_tables()
                
                if page_tables:
                    for table in page_tables:
                        if table and len(table) > 1:  # Skip empty or single-row tables
                            tables.append(table)
                
                # Extract text from page
                text = page.extract_text()
                
                if text:
                    # Clean text
                    cleaned_text = self._clean_text(text)
                    
                    if cleaned_text.strip():
                        text_content.append({
                            "page": page_num + 1,
                            "text": cleaned_text
                        })
        
        return tables, text_content
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove page numbers (common patterns)
        text = re.sub(r'Page\s+\d+', '', text, flags=re.IGNORECASE)
        
        # Remove multiple newlines
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        return text.strip()
    
    def _chunk_text(self, text_content: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Break text into chunks for vector storage.
        Using 1000 char chunks with 200 char overlap to preserve context.
        """
        chunks = []
        chunk_index = 0
        
        for page_content in text_content:
            text = page_content["text"]
            page = page_content["page"]
            
            # Split by paragraphs to keep semantic units together
            paragraphs = text.split('\n\n')
            
            current_chunk = ""
            
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                
                if not paragraph:
                    continue
                
                # Would this paragraph make the chunk too big?
                if len(current_chunk) + len(paragraph) > settings.CHUNK_SIZE:
                    if current_chunk:
                        chunks.append({
                            "text": current_chunk.strip(),
                            "page": page,
                            "chunk_index": chunk_index
                        })
                        chunk_index += 1
                        
                        # Start new chunk with overlap
                        overlap_text = self._get_overlap_text(current_chunk)
                        current_chunk = overlap_text + " " + paragraph
                    else:
                        # Paragraph is larger than chunk size, split it
                        para_chunks = self._split_large_paragraph(paragraph, page, chunk_index)
                        chunks.extend(para_chunks)
                        chunk_index += len(para_chunks)
                        current_chunk = ""
                else:
                    # Add paragraph to current chunk
                    current_chunk += ("\n\n" if current_chunk else "") + paragraph
            
            # Save remaining chunk
            if current_chunk.strip():
                chunks.append({
                    "text": current_chunk.strip(),
                    "page": page,
                    "chunk_index": chunk_index
                })
                chunk_index += 1
        
        return chunks
    
    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from end of previous chunk"""
        if len(text) <= settings.CHUNK_OVERLAP:
            return text
        
        # Get last CHUNK_OVERLAP characters, but try to break at sentence boundary
        overlap = text[-settings.CHUNK_OVERLAP:]
        
        # Find last sentence boundary
        sentence_end = max(overlap.rfind('. '), overlap.rfind('! '), overlap.rfind('? '))
        
        if sentence_end > 0:
            return overlap[sentence_end + 2:]
        
        return overlap
    
    def _split_large_paragraph(
        self, 
        paragraph: str, 
        page: int, 
        start_index: int
    ) -> List[Dict[str, Any]]:
        """Split a large paragraph into chunks"""
        chunks = []
        sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        
        current_chunk = ""
        chunk_index = start_index
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) > settings.CHUNK_SIZE:
                if current_chunk:
                    chunks.append({
                        "text": current_chunk.strip(),
                        "page": page,
                        "chunk_index": chunk_index
                    })
                    chunk_index += 1
                
                # Start new chunk
                if len(sentence) > settings.CHUNK_SIZE:
                    # Split long sentence by words
                    words = sentence.split()
                    current_chunk = ""
                    for word in words:
                        if len(current_chunk) + len(word) > settings.CHUNK_SIZE:
                            if current_chunk:
                                chunks.append({
                                    "text": current_chunk.strip(),
                                    "page": page,
                                    "chunk_index": chunk_index
                                })
                                chunk_index += 1
                            current_chunk = word
                        else:
                            current_chunk += (" " if current_chunk else "") + word
                else:
                    current_chunk = sentence
            else:
                current_chunk += (" " if current_chunk else "") + sentence
        
        if current_chunk.strip():
            chunks.append({
                "text": current_chunk.strip(),
                "page": page,
                "chunk_index": chunk_index
            })
        
        return chunks
