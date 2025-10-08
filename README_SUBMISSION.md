# Fund Performance Analysis System

**Repository**: https://github.com/Erick21/coding-test-3rd (update with your fork)

## What This Is

An AI-powered system for analyzing fund performance PDFs. Upload a document, and you can:
- Automatically extract tables (capital calls, distributions, adjustments) to SQL
- Ask natural language questions about the fund
- Calculate metrics like DPI, IRR, PIC
- Get answers with source citations

Built for the InterOpera-Apps coding challenge.

## Quick Start

```bash
# 1. Create .env file
echo "DATABASE_URL=postgresql://funduser:fundpass@localhost:5432/funddb
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=" > .env

# 2. Start
docker-compose up -d

# 3. Access
# Frontend: http://localhost:3000
# Backend: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

## Main Features

- **Document Processing**: PDF parsing with pdfplumber, automatic table classification
- **RAG System**: Vector search (pgvector) + LLM for Q&A
- **Metrics**: Accurate DPI, IRR, PIC calculations
- **API**: FastAPI with full documentation

## Documentation

- **SOLUTION.md** - Complete implementation details (start here)
- **SETUP.md** - Setup instructions and troubleshooting

## Tech Stack

Backend: FastAPI, PostgreSQL (pgvector), pdfplumber, LangChain  
Frontend: Next.js, Tailwind CSS  
Infrastructure: Docker Compose

## Implementation Notes

I implemented the missing components:
1. `table_parser.py` - Automatic table classification using keyword matching
2. `document_processor.py` - PDF processing pipeline with smart text chunking
3. All RAG/vector search functionality

Used pgvector instead of FAISS (simpler - keeps everything in PostgreSQL).

Time spent: ~8 hours over a few days.

## Testing

```bash
# Upload sample PDF
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@files/Sample_Fund_Performance_Report.pdf" \
  -F "fund_id=1"

# Ask a question
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is DPI?", "fund_id": 1}'

# Get metrics
curl "http://localhost:8000/api/funds/1/metrics"
```

Expected results:
- DPI: 0.40
- IRR: ~10-15%
- Processing time: 5-10 seconds

## Notes

- Leave OPENAI_API_KEY empty to use free HuggingFace embeddings
- First run downloads the embedding model (~100MB)
- Check SETUP.md for troubleshooting

---

Erick Hermawan | October 2025

