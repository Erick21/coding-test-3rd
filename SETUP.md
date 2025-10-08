# Setup Guide

## Prerequisites

- Docker & Docker Compose
- That's it!

(Optional: Node.js 18+ and Python 3.11+ if you want to run locally without Docker)

## Quick Start

### 1. Environment Variables

Create a `.env` file in the root directory:

```bash
# Database
DATABASE_URL=postgresql://funduser:fundpass@localhost:5432/funddb

# Redis
REDIS_URL=redis://localhost:6379/0

# OpenAI (optional - leave empty to use free HuggingFace embeddings)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4-turbo-preview
OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# If you don't have OpenAI key, that's fine - the system will fall back to
# HuggingFace sentence-transformers which works locally
```

### 2. Start Services

```bash
docker-compose up -d
```

Wait about 30-60 seconds for everything to initialize.

### 3. Check Status

```bash
docker-compose ps
```

You should see 4 services running:
- fund-postgres (PostgreSQL with pgvector)
- fund-redis (Redis)
- fund-backend (FastAPI)
- fund-frontend (Next.js)

### 4. Access

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Testing the System

### Via Web Interface

1. Go to http://localhost:3000/upload
2. Upload `files/Sample_Fund_Performance_Report.pdf`
3. Wait for processing to complete (5-10 seconds)
4. Go to http://localhost:3000/chat
5. Ask: "What is DPI?"

### Via Command Line

**Upload a document:**
```bash
curl -X POST "http://localhost:8000/api/documents/upload" \
  -F "file=@files/Sample_Fund_Performance_Report.pdf" \
  -F "fund_id=1"
```

**Check status:**
```bash
curl "http://localhost:8000/api/documents/1/status"
```

**Ask a question:**
```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is DPI?",
    "fund_id": 1
  }'
```

**Get metrics:**
```bash
curl "http://localhost:8000/api/funds/1/metrics"
```

## Free LLM Alternatives

Don't have an OpenAI API key? No problem! Here are free options:

### Option 1: No LLM Key Needed (Default)

Just leave `OPENAI_API_KEY` empty in your `.env`. The system will automatically use:
- HuggingFace sentence-transformers for embeddings (runs locally)
- Basic query processing without LLM (still works for calculations)

### Option 2: Ollama (Local, Free)

```bash
# Install Ollama
brew install ollama  # or download from ollama.com

# Pull a model
ollama pull llama3.2

# Add to .env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

### Option 3: Google Gemini (Free Tier)

1. Get API key: https://makersuite.google.com/app/apikey
2. Add to `.env`: `GOOGLE_API_KEY=your-key`
3. 60 requests/min free

### Option 4: Groq (Free Tier)

1. Get API key: https://console.groq.com
2. Add to `.env`: `GROQ_API_KEY=your-key`
3. Very fast inference

## Troubleshooting

### Services won't start

```bash
# Check logs
docker-compose logs

# Common fix: restart everything
docker-compose down
docker-compose up -d
```

### Backend errors

```bash
# Check backend logs
docker-compose logs backend -f
```

### Database issues

```bash
# Check if pgvector is installed
docker exec -it fund-postgres psql -U funduser -d funddb -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Check embeddings table
docker exec -it fund-postgres psql -U funduser -d funddb -c "SELECT COUNT(*) FROM document_embeddings;"
```

### Document processing fails

Common causes:
- PDF is a scanned image (need OCR, not implemented)
- Tables are too complex or unstructured
- Missing tables in the PDF

Check logs:
```bash
docker-compose logs backend | grep -A 10 "Error"
```

### Clean start

If things are really messed up:
```bash
docker-compose down -v  # removes volumes too
docker-compose up -d
```

## Local Development (Without Docker)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://funduser:fundpass@localhost:5432/funddb
export REDIS_URL=redis://localhost:6379/0

# Run migrations
python app/db/init_db.py

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Set environment
export NEXT_PUBLIC_API_URL=http://localhost:8000

# Start dev server
npm run dev
```

Note: You'll still need PostgreSQL (with pgvector) and Redis running locally or via Docker.

## Expected Results

After uploading the sample PDF, you should see:

**Processing Statistics:**
- Pages: 2-5
- Tables found: 3-4
- Capital calls: 4
- Distributions: 3-4
- Adjustments: 2-3
- Text chunks: 10-20

**Metrics:**
- PIC: $10,000,000
- Total Distributions: $4,000,000
- DPI: 0.40
- IRR: ~10-15%

**Sample Queries:**
- "What is DPI?" → Definition
- "Calculate the current DPI" → 0.40 with explanation
- "Show me all capital calls" → List of 4 transactions
- "Has the fund returned capital to LPs?" → Analysis

## Performance

Typical processing times:
- Small PDF (5 pages): 2-3 seconds
- Medium PDF (20 pages): 5-8 seconds
- Large PDF (50+ pages): 15-30 seconds

Query response times:
- Vector search: 50-100ms
- Calculation: 100-200ms
- LLM response: 1-2 seconds

## Notes

- First run might be slower (downloading embeddings model)
- Background tasks run in FastAPI (consider Celery for production)
- Vector search uses IVFFLAT index (tune `lists` parameter for large datasets)
- Embeddings are 1536-dim for OpenAI, 384-dim for HuggingFace

## Need Help?

Check the API docs at http://localhost:8000/docs - it has examples for all endpoints.
