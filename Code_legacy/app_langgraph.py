# implementation of app.py using langgraph with Invisible Reflection Hints
from duckdb import df
from ingestion import ingest_files
from sql_engine import load_two_csvs_to_duckdb
from pdf_to_markdown import pdfs_to_markdown
from vectorize import build_retriever
from sql_orchestrator import should_run_sql
from summarization_agent import summarize_with_llama
from llm_sql_agent import sql_pipeline_structured
import logging
from intent_llm import QueryInterpreter
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from typing import Any, Optional, List, Dict, Tupleq
import pandas as pd
import re


# Silencing noisy loggers to keep terminal output clean
NOISY_LOGGERS = ["httpx", "urllib3", "ollama", "chromadb", "langchain", "langchain_core"]
for logger in NOISY_LOGGERS:
    logging.getLogger(logger).setLevel(logging.CRITICAL)
logging.disable(logging.CRITICAL)

# Shared state
class AppState(TypedDict, total=False):
    question: str
    paths: List[str]
    csv_path: str
    pdf_paths: List[str]
    paths_md: List[str]
    doc_dir: str
    con: Any
    table_name: str
    type_schema: Dict[str, Any]
    num_cols: List[str]
    retriever: Any
    retrieved_chunks: List[Any]
    doc_evidence: str
    intent_spec: Any
    sql_ran: bool
    sql_output: Optional[Dict[str, Any]]
    summary_payload: Dict[str, Any]
    final_answer: str
    mode: str # "docs_only"| "sql_only" |"hybrid"

    
# Nodes
def decide_mode(state: AppState) -> AppState:
    q = state["question"]
    ql = q.lower()
    schema = state.get("type_schema", {})

    # Policy/docs cues
    docs_keywords = [
        "policy", "rule", "definition", "define", "meaning", "standard",
        "eligibility", "terms", "sla", "guideline", "procedure", "compliance",
        "refund", "return", "exchange", "rma",
        "shipping", "shipment", "delivery", "timeframe", "track", "domestic", "international",
        "privacy", "data", "account", "security", "retention", "delete"
    ]
    docs_needed = any(k in ql for k in docs_keywords)

    # Numeric/analytics cues (SQL-worthy)
    sql_cues = [
        "how many", "count", "number of", "total", "sum", "average", "avg",
        "min", "max", "median", "trend", "over time", "by month", "by week",
        "top", "bottom", "highest", "lowest", "rank", "distribution", "group by",
        "percent", "percentage", "rate"
    ]
    docs_needed = any(k in ql for k in docs_keywords)
    sql_needed = should_run_sql(q, schema=schema)

    name_like = bool(re.search(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", q))

    entity_keywords = ["customer", "profile", "ticket", "tickets", "account", "order", "history"]
    state_keywords  = ["open", "closed", "status", "priority", "show", "list", "find", "give", "how many"]

    entity_needed = any(k in ql for k in entity_keywords)
    state_needed  = any(k in ql for k in state_keywords) or name_like

    structured_needed = entity_needed and state_needed
    run_sql = sql_needed or structured_needed

    if docs_needed and run_sql:
        mode = "hybrid"
    elif run_sql and not docs_needed:
        mode = "sql_only"
    else:
        mode = "docs_only"

    print(f"\n[Langraph] Node: decide_mode -> {mode}")
    return {"mode": mode}

def retrieve_docs(state: AppState) -> AppState:
    """Retrieves relevant document chunks for the query."""
    print("\n [Langraph] Node: retrieve_docs")
    q = state["question"]
    retriever = state.get("retriever")
    print("\n [Langraph] Node: retriever_docs")
    chunks = retriever.invoke(q) if retriever else []
    doc_evidence = "\n".join(c.page_content for c in chunks) if chunks else ""
    print(f"[Langraph] Retrieved chunks: {len(chunks) if chunks else 0}")
    print(f"\ntype_schema: {state['type_schema']}")
    return {
        "retrieved_chunks": chunks,
        "doc_evidence": doc_evidence,
    }

def route_from_mode(state: AppState) -> str:
    # where do we go first?
    m = state.get("mode", "docs_only")
    if m == "sql_only":
        return "run_sql_path"
    # docs_only OR hybrid both start with docs retrieval
    return "retrieve_docs"

def route_after_docs(state: AppState) -> str:
    # after docs retrieval, hybrid continues to SQL, docs_only summarizes
    m = state.get("mode", "docs_only")
    return "run_sql_path" if m == "hybrid" else "summarize"



# updated function with  intent refinement
def run_sql_path(state: AppState) -> AppState:
    """Runs SQL pipeline with Intent Patching (keeps 'q' pure)."""
    print("\n [Langraph] Node: run_sql_path")

    q = state["question"]
    doc_evidence = state.get("doc_evidence", "") or ""

    con = state["con"]
    table_name = state["table_name"]
    type_schema = state["type_schema"]

    # 2. Run Interpreter (Standard)
   
    interpreter = QueryInterpreter(con, table_name, type_schema)
    refined_spec = interpreter.refine_intent(
        q,
        business_context=doc_evidence,
    )
    # Early Exit 
    if refined_spec.intent == "metadata":
        return {
        "intent_spec": refined_spec,
        "sql_ran": False,
        "sql_output": None,
        "doc_evidence": doc_evidence,
        "error": None,
        "sql_evidence": "",
     }


    # 3. Run SQL Pipeline 
    output = sql_pipeline_structured(
        q,
        refined_spec,
        con=con,
        table_name=table_name,
        type_schema=type_schema,
    )

    print(f"-----Sql_output----: {output.get('sql')}")
    print(f"-----Refined-Intent----: {refined_spec}")

    # 4. Output Handling (Standard)
    current_error = output.get("error")
    sql_evidence = ""
    if output.get("sql_ran") and output.get("sql_result"):
        res = output["sql_result"]
        rows = res.get("rows", [])
        cols = res.get("columns", [])
        if rows:
            sql_evidence += "\n\n[SQL_RESULT]\n"
            sql_evidence += f"COLUMNS: {', '.join(str(c) for c in cols)}\n"
            preview_rows = rows[:20]
            for r in preview_rows:
                sql_evidence += f"ROW: {', '.join(str(x) for x in r)}\n"
    

    return {
        "intent_spec": refined_spec,
        "sql_ran": bool(output.get("sql_ran")),
        "sql_output": output,
        "doc_evidence": doc_evidence,
        "error": current_error,
        "sql_evidence": sql_evidence,
    }



def summarize(state: AppState) -> AppState:
    """Produces final response using clean doc_evidence."""
    print("\n [Langraph] Node: summarize")
    q = state["question"]
    doc_evidence = state.get("doc_evidence") or ""

    mode = state.get("mode", "docs_only")
    sql_output = state.get("sql_output") if mode in ("sql_only", "hybrid") else None
    
    # Now this line is safe
    augmented_evidence = doc_evidence 
    
    intent_spec = state.get("intent_spec")
    intent_val = getattr(intent_spec, "intent", None)
    if mode == "sql_only":
        source_type = "SQL Only"
    elif mode == "hybrid":
        source_type = "Hybrid (Docs + SQL)"
    else:
        source_type = "Docs Only"

    summary_payload = {
        "question": q,
        "source_type": source_type,
        "business_rules": augmented_evidence,
        "sql_output": sql_output,
        "intent": intent_val,
    }

    final_answer = summarize_with_llama(
        question=q,
        evidence=summary_payload,
        source_type=summary_payload["source_type"],
    )

    return {
        "summary_payload": summary_payload,
        "final_answer": final_answer,
        "sql_output": None,
    }

# Ingestion & Build Runtime Logic for testing 
def build_runtime() ->  Tuple[Any, Any, str, Dict[str, Any], List[str]]:
    paths = [
        r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/pdfs/Privacy_Account_Policy.pdf",
        r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/pdfs/Refund_Returns_Policy.pdf",
        r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/pdfs/Shipping_Delivery_Policy.pdf",r'/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/customers.csv',r'/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/tickets.csv'

    ]
    csv_paths, pdf_paths = ingest_files(paths)

    customers_csv = next(p for p in csv_paths if "customer" in p.lower())
    tickets_csv   = next(p for p in csv_paths if "ticket" in p.lower())

    con, table_names, schemas, warnings = load_two_csvs_to_duckdb(
        customers_csv_path=customers_csv,
        tickets_csv_path=tickets_csv,
        join_key="customer_id",
        view_name="customer_tickets",
    )

    table_name = table_names["view"]
    type_schema = schemas["view"]

    paths_md, errors_md, is_md = pdfs_to_markdown(pdf_paths, r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/docs/")
    retriever = build_retriever(paths_md)

    return retriever, con, table_name, type_schema, warnings

def build_runtime_from_paths(customers_csv: str, tickets_csv: str, pdf_paths: List[str], doc_dir: str):
    con, table_names, schemas, warnings = load_two_csvs_to_duckdb(
        customers_csv_path=customers_csv,
        tickets_csv_path=tickets_csv,
        join_key="customer_id",
        view_name="customer_tickets",
    )

    table_name = table_names["view"]
    type_schema = schemas["view"]

    paths_md, errors_md, is_md = pdfs_to_markdown(pdf_paths, doc_dir)
    retriever = build_retriever(paths_md) if paths_md else None

    return retriever, con, table_name, type_schema, warnings

# Graph Construction
graph_builder = StateGraph(AppState)

graph_builder.add_node("decide_mode", decide_mode)
graph_builder.add_node("retrieve_docs", retrieve_docs)
graph_builder.add_node("run_sql_path", run_sql_path)
graph_builder.add_node("summarize", summarize)

# START -> decide_mode
graph_builder.add_edge(START, "decide_mode")

# decide_mode -> (sql_only -> run_sql_path) OR (docs_only/hybrid -> retrieve_docs)
graph_builder.add_conditional_edges(
    "decide_mode",
    route_from_mode,
    {
        "run_sql_path": "run_sql_path",
        "retrieve_docs": "retrieve_docs",
    }
)

# retrieve_docs -> (hybrid -> run_sql_path) OR (docs_only -> summarize)
graph_builder.add_conditional_edges(
    "retrieve_docs",
    route_after_docs,
    {
        "run_sql_path": "run_sql_path",
        "summarize": "summarize",
    }
)

# run_sql_path -> summarize (for sql_only and hybrid)
graph_builder.add_edge("run_sql_path", "summarize")

# summarize -> END
graph_builder.add_edge("summarize", END)

graph = graph_builder.compile()

# Export Mermaid Diagram
png_bytes = graph.get_graph().draw_mermaid_png()
with open("agentic_rag_langgraph.png", "wb") as f:
    f.write(png_bytes)

# Main Loop CLI
def bi_agent():
    retriever, con, table_name, type_schema, warnings = build_runtime()
    # Prepare warning message
    dq_msg = "\n".join(warnings) if warnings else None
    if dq_msg:
        print(f"\n[SYSTEM ALERT]: {dq_msg}\n")
   # CLI Loop
    while True:
        q = input("User:  ")
        if not q or q.lower() in {"exit", "quit", "q"}:
            break
        initial_state: AppState = {
            "question": q,
            "retriever": retriever,
            "con": con,
            "table_name": table_name,
            "type_schema": type_schema,
        }
        result = graph.invoke(initial_state)
        print("\n🤖 Agent Response:")
        print(result["final_answer"])
        print("\n" + "-" * 60 + "\n")

if __name__ == "__main__":
    bi_agent()

