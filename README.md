# Generative AI Multi Agent System for Customer Support

## 1. Overview

This project implements a Generative AI powered Multi Agent System that enables natural language interaction with both structured and unstructured customer data.

The system is designed for a customer support executive who needs to:

- Retrieve customer profile and ticket data from structured databases
- Search and summarize company policy documents in PDF format
- Combine structured and unstructured information into a single contextual response
- Prevent hallucination and provide grounded, reference backed answers

This solution satisfies the requirements defined in the assignment instructions.

---

## 2. Assignment Objective Coverage

The system fulfills the following objectives:

### Structured Data
- Customer and ticket history stored in DuckDB
- Natural language to SQL generation
- Join handling between customers and tickets
- Aggregations including COUNT and AVG

### Unstructured Data
- PDF ingestion
- PDF to Markdown conversion using Docling
- Embedding and vector indexing
- Semantic retrieval using Chroma Vector Database

### Multi Agent System
- LangGraph state machine orchestration
- Routing between:
  - Docs only
  - SQL only
  - Hybrid Docs + SQL
- Evidence synthesis before final response generation

### Required Stack
- LangChain
- LangGraph
- Ollama LLM
- DuckDB
- Chroma Vector DB
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

The system uses a StateGraph to control execution:

1. decide_mode  
   Determines if query is:
   - docs_only
   - sql_only
   - hybrid

2. retrieve_docs  
   Performs semantic retrieval from vector database

3. run_sql_path  
   Uses QueryInterpreter and SQL pipeline

4. summarize  
   Produces grounded final response using only observed evidence

This ensures deterministic routing and hallucination prevention.

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
## 6. How It Works

### Step 1: Upload Data
- customers.csv
- tickets.csv
- policy PDF files

### Step 2: Create Session
MCP server builds:
- DuckDB database
- Joined view customer_tickets
- Vector DB from policy documents

### Step 3: Ask Question
LangGraph determines execution path.


![Agentic RAG LangGraph Flow](agentic_rag_langgraph.png)
