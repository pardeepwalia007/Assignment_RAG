# Generative AI Multi Agent System for Customer Support

## LangGraph Orchestration Flow

![LangGraph Execution Flow](agentic_rag_langgraph.png)

---

## 1. Overview

This project implements a Generative AI powered Multi Agent System that enables natural language interaction with both structured and unstructured customer data.

The system is designed to assist a customer support executive in retrieving, analyzing, and summarizing information that is distributed across structured databases and policy documents.

Key capabilities:

- Retrieve customer profiles and ticket history from structured data sources
- Search and summarize company policy documents in PDF format
- Combine structured and unstructured information into a single contextual response
- Produce grounded, evidence-based answers to reduce hallucination risk

---

## 2. Assignment Objective Coverage

This implementation satisfies the stated assessment objectives as follows:

### Structured Data Handling

- Customer and ticket datasets stored in DuckDB
- Automatic join between customers and tickets
- Natural language to SQL translation
- Support for filtering, grouping, aggregation, and metrics (COUNT, AVG, etc.)

### Unstructured Data Handling

- PDF ingestion pipeline
- PDF to Markdown conversion using Docling
- Embedding generation and vector indexing
- Semantic retrieval using Chroma Vector Database

### Multi Agent Architecture

- LangGraph state-based orchestration
- Deterministic routing between:
  - Docs only mode
  - SQL only mode
  - Hybrid mode (Docs + SQL)
- Evidence synthesis prior to final response generation

### Technology Stack

- LangChain
- LangGraph
- Ollama (local LLM)
- DuckDB
- Chroma Vector Database
- MCP Server
- FastAPI
- Streamlit

---

## 3. System Architecture

User Interface  
→ FastAPI  
→ MCP Server  
→ LangGraph Orchestrator  
→  
 1. SQL Agent (DuckDB)  
 2. Document Retriever (Chroma Vector DB)  
→ Summarization Agent  
→ Final Response  

---

## 4. LangGraph Execution Flow

The application uses a StateGraph to coordinate execution:

1. **decide_mode**  
   Determines whether the query requires:
   - docs_only
   - sql_only
   - hybrid

2. **retrieve_docs**  
   Performs semantic retrieval from the vector database.

3. **run_sql_path**  
   Executes structured queries using the Query Interpreter and SQL pipeline.

4. **summarize**  
   Generates a grounded response using only observed evidence.

This controlled routing ensures reproducible execution paths and reduces hallucination.

---

## 5. Project Structure

```text
Code/
│
├── api.py
├── app_langgraph.py
├── ingestion.py
├── intent_llm.py
├── llm_sql_agent.py
├── mcp_server.py
├── pdf_to_markdown.py
├── sql_engine.py
├── sql_orchestrator.py
├── summarization_agent.py
├── vectorize.py
├── ui.py
└── test_mcp.py
```

---

## 6. Workflow

### Step 1: Upload Data

Required:
- customers.csv
- tickets.csv

Optional:
- Policy PDF documents

### Step 2: Session Initialization

The MCP server performs:

- Creation of a DuckDB database
- Construction of a joined view (`customer_tickets`)
- Conversion and indexing of policy documents into a vector database

### Step 3: Query Processing

LangGraph determines the appropriate execution path and produces a structured response.

---

## 7. Setup

### Prerequisites

- Python 3.10 or 3.11
- Ollama installed and running locally
- An Ollama model pulled (example: `qwen2.5:14b-instruct-q5_K_M`)

### Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Start Ollama

```bash
ollama serve
ollama pull qwen2.5:14b-instruct-q5_K_M
```

---

## 8. Running the Application

### Option A: Streamlit UI (Recommended)

Terminal 1:

```bash
uvicorn Code.api:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```bash
streamlit run Code/ui.py
```

Open:

```
http://localhost:8501
```

Upload required files and begin querying through the chat interface.

---

### Option B: MCP CLI Test

```bash
python -m Code.test_mcp
```

This validates:

- MCP session creation
- SQL execution
- Document retrieval
- LangGraph routing

---

## 9. API Usage

### Endpoint

POST `/query`

### Request Format

Multipart form data containing:

- `question` (string)
- `customers_csv` (file)
- `tickets_csv` (file)
- `pdf_files` (optional list of PDF files)

### Example

```bash
curl -X POST "http://127.0.0.1:8000/query" \
  -F "question=How many open tickets are there?" \
  -F "customers_csv=@Data/csv/customers.csv" \
  -F "tickets_csv=@Data/csv/tickets.csv" \
  -F "pdf_files=@Data/pdfs/Refund_Returns_Policy.pdf"
```

---

## 10. Demonstration Queries

1. Basic RAG  
   "What is the standard delivery timeframe for domestic shipments?"

2. Basic SQL  
   "How many total tickets does Ema Patel have in her history?"

3. Hybrid Query  
   "Does Ema Patel have any open refund tickets, and what is the processing timeline for them?"

4. Calculation  
   "What is the average satisfaction score for all Closed tickets?"

5. Edge Case  
   "What is the policy for shipping to Mars?"

---

## 11. Environment Notes

This project runs entirely locally and does not require external API keys.

Ensure:

- Ollama is running
- The selected model is available
- Port 8000 is available for FastAPI
- Port 8501 is available for Streamlit

---

## 12. Limitations

- Designed for synthetic or demonstration datasets
- In-memory session store (not production persistent)
- Local LLM execution via Ollama
- Vector index stored locally

