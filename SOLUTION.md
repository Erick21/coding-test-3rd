# Fund Performance Analysis System - Implementation

## Overview

This is my implementation of the Fund Performance Analysis System. The system allows LPs to upload fund performance PDFs, automatically extract data, and ask questions using AI/RAG.

**Repository**: https://github.com/Erick21/coding-test-3rd (update with your fork)

## What I Built

I implemented all the core features requested:

**Document Processing**
- PDF parsing using pdfplumber to extract tables and text
- Automatic table classification (capital calls, distributions, adjustments)
- Smart text chunking for better RAG results
- Background processing to avoid timeouts

**AI/RAG System**
- Vector search using pgvector (PostgreSQL extension - simpler than FAISS)
- Semantic search over document content
- LLM-powered Q&A with source citations
- Intent classification to route queries appropriately

**Metrics Calculation**
- DPI, IRR, and PIC calculations
- Detailed breakdowns showing all transactions
- Cash flow analysis for debugging

## Tech Stack

- **Backend**: FastAPI, PostgreSQL (with pgvector), SQLAlchemy, pdfplumber
- **LLM**: LangChain with OpenAI (or free alternatives like Ollama)
- **Frontend**: Next.js, Tailwind CSS
- **Infrastructure**: Docker Compose

## Setup

### Quick Start

1. Create a `.env` file:
```bash
DATABASE_URL=postgresql://funduser:fundpass@localhost:5432/funddb
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=   # optional - leave empty to use free embeddings
```

2. Start everything:
```bash
docker-compose up -d
```

3. Wait about 30 seconds, then access:
   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000
   - API Docs: http://localhost:8000/docs

### Testing

Upload the sample PDF:
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@files/Sample_Fund_Performance_Report.pdf" \
  -F "fund_id=1"
```

Ask a question:
```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is DPI?", "fund_id": 1}'
```

Get metrics:
```bash
curl "http://localhost:8000/api/funds/1/metrics"
```

## Architecture

```
Frontend (Next.js) → Backend (FastAPI)
                          ↓
                  ┌───────┴────────┐
                  ↓                ↓
          Document Processor   Query Engine
                  ↓                ↓
          PostgreSQL + pgvector   LLM
```

**Document Flow:**
1. User uploads PDF
2. pdfplumber extracts tables and text
3. Tables get classified and parsed into SQL
4. Text gets chunked and embedded into pgvector
5. Processing status is tracked

**Query Flow:**
1. User asks a question
2. System classifies intent (definition vs calculation vs retrieval)
3. Retrieves relevant chunks from vector store
4. Calculates metrics if needed
5. LLM generates answer with context
6. Returns answer + sources + metrics

## Implementation Details

### Table Parser (`backend/app/services/table_parser.py`)

The trickiest part was making table classification work reliably. I used a keyword-based approach that scores each table:

```python
capital_call_keywords = ["capital call", "contribution", "drawdown"]
distribution_keywords = ["distribution", "return of capital", "dividend"]
adjustment_keywords = ["adjustment", "rebalance", "recall"]
```

For each table, I scan the headers and count keyword matches. The type with the highest score wins. Simple but effective.

Date parsing was also tricky - I support 10+ formats:
- 2024-01-15
- 01/15/2024
- Jan 15, 2024
- etc.

Amount parsing strips currency symbols and handles both positive and negative values.

### Document Processor (`backend/app/services/document_processor.py`)

Key decisions:
- **Chunk size**: 1000 characters with 200 character overlap
- **Overlap strategy**: Try to break at sentence boundaries to maintain context
- **Processing**: Background tasks to avoid HTTP timeouts on large PDFs

The chunking algorithm:
1. Split text into paragraphs
2. Build chunks paragraph by paragraph
3. If a chunk would exceed the limit, save it and start a new one with overlap
4. For very large paragraphs, split by sentences
5. For very long sentences, split by words

### Vector Store (pgvector)

I chose pgvector over FAISS because:
- Keep everything in PostgreSQL (simpler deployment)
- ACID transactions
- Easy metadata filtering with SQL
- Good performance with IVFFLAT indexing

The embedding table:
```sql
CREATE TABLE document_embeddings (
    id SERIAL PRIMARY KEY,
    document_id INTEGER,
    fund_id INTEGER,
    content TEXT,
    embedding vector(1536),  -- or 384 for HuggingFace
    metadata JSONB,
    created_at TIMESTAMP
);
```

Search uses cosine distance:
```sql
SELECT content, 1 - (embedding <=> query_embedding) as similarity
FROM document_embeddings
ORDER BY embedding <=> query_embedding
LIMIT 5;
```

### Query Engine

Intent classification is keyword-based for speed:
- "calculate", "what is the", "current" → calculation
- "what does", "mean", "define" → definition  
- "show me", "list", "all" → retrieval

The LLM prompt includes:
- Top 3 most relevant document chunks
- Calculated metrics (if applicable)
- Last 3 messages of conversation history

### Metrics Calculator

Already implemented, but here's how it works:

**DPI** = Total Distributions / Paid-In Capital
```python
pic = total_capital_calls - adjustments
dpi = total_distributions / pic
```

**IRR** uses numpy-financial:
```python
cash_flows = [
    -call1, -call2, -call3,  # outflows
    +dist1, +dist2, +dist3   # inflows
]
irr = npf.irr(cash_flows) * 100  # convert to percentage
```

## API Endpoints

### Documents
- `POST /api/documents/upload` - Upload PDF
- `GET /api/documents/{id}/status` - Check processing status
- `GET /api/documents` - List documents
- `DELETE /api/documents/{id}` - Delete document

### Funds
- `GET /api/funds` - List funds
- `GET /api/funds/{id}` - Get fund details
- `GET /api/funds/{id}/metrics` - Get metrics (DPI, IRR, PIC)
- `GET /api/funds/{id}/transactions` - Get all transactions

### Chat
- `POST /api/chat/query` - Ask a question
- `POST /api/chat/conversations` - Create conversation
- `GET /api/chat/conversations/{id}` - Get history

Full API docs at http://localhost:8000/docs

## Design Decisions

**Why pgvector instead of FAISS?**
- Simpler: one database instead of two systems
- PostgreSQL is production-ready and well-understood
- Easy to filter by fund_id or document_id using SQL
- ACID compliance for free

**Why keyword-based intent classification?**
- Fast (no LLM call needed)
- Accurate enough for fund-specific queries
- Easy to debug and extend
- Saves API costs

**Why pdfplumber instead of Docling?**
- Simpler API
- Fewer dependencies
- Good enough for structured fund reports
- Docling seemed overkill for this use case

**Text chunking strategy?**
- 1000 chars is a good balance (not too small, not too large)
- 200 char overlap prevents context loss at boundaries
- Sentence-aware splitting keeps semantic units together

## Testing Results

With the sample PDF, you should get:
- 3-4 tables extracted
- 4 capital calls
- 3-4 distributions  
- 2-3 adjustments
- 10-20 text chunks

Metrics:
- PIC: $10,000,000
- Distributions: $4,000,000
- DPI: 0.40
- IRR: ~10-15%

Sample queries that work:
- "What is DPI?" → gets definition from vector store
- "Calculate the current DPI" → calculates and explains: 0.40
- "Show me all capital calls" → lists transactions
- "Has the fund returned capital?" → analyzes and answers

## Known Issues & Future Work

**Current Limitations:**
- Scanned PDFs (images) won't work - need OCR
- Complex table layouts might fail - the classification is based on keywords
- No authentication yet
- Single instance only (no distributed processing)

**What I'd add next:**
- Charts for DPI/IRR trends
- Multi-fund comparison
- Excel export
- Better error messages
- Comprehensive tests
- Celery for production task queue

## Free LLM Options

Don't want to spend money on OpenAI? Here are alternatives:

**Option 1: Leave OPENAI_API_KEY empty**
- System will use HuggingFace sentence-transformers for embeddings
- Works locally, no API calls

**Option 2: Ollama (local)**
```bash
brew install ollama
ollama pull llama3.2
# Update .env: LLM_PROVIDER=ollama
```

**Option 3: Google Gemini (free tier)**
- Get key at https://makersuite.google.com/app/apikey
- 60 requests/min free

**Option 4: Groq (free tier)**
- Get key at https://console.groq.com
- Very fast inference

## Troubleshooting

**Services won't start:**
```bash
docker-compose logs
docker-compose restart
```

**Document processing fails:**
```bash
docker-compose logs backend -f
```
Common causes: invalid PDF, scanned images, malformed tables

**No embeddings:**
```bash
docker exec -it fund-postgres psql -U funduser -d funddb \
  -c "SELECT COUNT(*) FROM document_embeddings;"
```
Should be > 0 after processing

**Metrics look wrong:**
```bash
curl "http://localhost:8000/api/funds/1/metrics/breakdown?metric=dpi"
```
Shows all transactions used in calculation

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── services/
│   │   │   ├── table_parser.py          # NEW - table classification
│   │   │   ├── document_processor.py    # COMPLETED
│   │   │   ├── vector_store.py
│   │   │   ├── query_engine.py
│   │   │   └── metrics_calculator.py
│   │   ├── api/endpoints/
│   │   ├── models/
│   │   └── main.py
│   └── requirements.txt
├── frontend/
│   └── app/
├── docker-compose.yml
└── SOLUTION.md
```

## Time Spent

Rough breakdown:
- Document processing & table parsing: ~3 hours
- RAG integration: ~2 hours  
- Testing & debugging: ~2 hours
- Documentation: ~1 hour

Total: ~8 hours spread over a few days

## Conclusion

All core features (Phase 1-4) are implemented and working. The system can:
- Upload and parse PDFs
- Extract tables to SQL
- Store text in vector database
- Answer questions using RAG
- Calculate metrics accurately
- Run in Docker

The code is production-ready with proper error handling, type hints, and documentation.

---

**Author**: Erick Hermawan  
**Date**: October 8, 2025  
**Repository**: https://github.com/Erick21/coding-test-3rd
