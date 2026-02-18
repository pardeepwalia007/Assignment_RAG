# Code/mcp_server.py
# Run (stdio): python -m Code.mcp_server
# Or run directly: python Code/mcp_server.py
import os
import uuid
import shutil
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .app_langgraph import graph, build_runtime_from_paths, AppState

mcp = FastMCP(name="bi-agent-mcp")

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-memory session store (good enough for assessment)
SESSIONS: Dict[str, Dict[str, Any]] = {}


def _write_bytes(path: str, data: bytes) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


@mcp.tool()
def create_session(
    customers_csv_bytes: bytes,
    tickets_csv_bytes: bytes,
    pdf_files: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Upload files once and build runtime (DuckDB + retriever).
    Returns session_id to reuse for subsequent questions.
    """
    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    customers_path = _write_bytes(os.path.join(session_dir, "customers.csv"), customers_csv_bytes)
    tickets_path = _write_bytes(os.path.join(session_dir, "tickets.csv"), tickets_csv_bytes)

    pdf_paths: List[str] = []
    for i, item in enumerate(pdf_files or []):
        fname = item.get("filename") or f"policy_{i+1}.pdf"
        data  = item.get("bytes") or b""
        pdf_paths.append(_write_bytes(os.path.join(session_dir, fname), data))

    retriever, con, table_name, type_schema, warnings,md_to_pdf = build_runtime_from_paths(
        customers_csv=customers_path,
        tickets_csv=tickets_path,
        pdf_paths=pdf_paths,
        doc_dir=session_dir,
    )

    SESSIONS[session_id] = {
        "retriever": retriever,
        "con": con,
        "table_name": table_name,
        "type_schema": type_schema,
        "warnings": warnings,
        "md_to_pdf": md_to_pdf,
    }

    return {
        "session_id": session_id,
        "warnings": warnings or [],
        "has_docs": bool(pdf_paths),
    }


@mcp.tool()
def ask(
    session_id: str,
    question: str,
) -> Dict[str, Any]:
    """
    Ask a question using an existing session runtime.
    Returns structured output (answer + metadata).
    """
    if session_id not in SESSIONS:
        return {
            "error": "INVALID_SESSION",
            "message": "Session not found. Call create_session first.",
        }

    rt = SESSIONS[session_id]

    initial_state: AppState = {
        "question": question,
        "retriever": rt["retriever"],
        "con": rt["con"],
        "table_name": rt["table_name"],
        "type_schema": rt["type_schema"],
        "error": None,
        "doc_evidence": "",
        "sql_ran": False,
        "intent_spec": None,
        "md_to_pdf": rt.get("md_to_pdf", {}),
    }

    result: Dict[str, Any] = graph.invoke(initial_state)

    sql_output = result.get("sql_output") or {}
    sql_text = sql_output.get("sql") if isinstance(sql_output, dict) else None
    chunks = result.get("retrieved_chunks") or []

    mode = (result.get("mode") or "").lower()
    run_sql = mode in ("sql_only", "hybrid")

    return {
        "final_answer": result.get("final_answer", ""),
        "mode": mode,
        "run_sql": run_sql,
        "sql_ran": bool(result.get("sql_ran", False)),
        "sql": sql_text,
        "retrieved_chunks": len(chunks) if isinstance(chunks, list) else 0,
    }


def main():
    # stdio transport
    mcp.run()


if __name__ == "__main__":
    main()