# Code/api.py
# Run: uvicorn Code.api:app --reload --host 127.0.0.1 --port 8000
from fastapi import FastAPI, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Optional
from .mcp_server import create_session, ask


app = FastAPI(title="BI Agent API", version="1.1")


class QueryResponse(BaseModel):
    final_answer: str
    run_sql: bool = False
    sql_ran: bool = False
    retrieved_chunks: int = 0
    sql: Optional[str] = None


@app.post("/query", response_model=QueryResponse)
def query_agent(
    question: str = Form(...),
    customers_csv: UploadFile = File(...),
    tickets_csv: UploadFile = File(...),
    pdf_files: List[UploadFile] = File(default=[]),
) -> QueryResponse:
    # Reset file pointers BEFORE reading bytes
    customers_csv.file.seek(0)
    tickets_csv.file.seek(0)

    pdf_payload = []
    for p in (pdf_files or []):
        p.file.seek(0)
        pdf_payload.append({
            "filename": p.filename,   # keep original name
            "bytes": p.file.read()
        })

    session = create_session(
        customers_csv_bytes=customers_csv.file.read(),
        tickets_csv_bytes=tickets_csv.file.read(),
        pdf_files=pdf_payload,        # <- send name+bytes
    )

    session_id = session["session_id"]
    # Ask MCP
    result = ask(
        session_id=session_id,
        question=question,
    )

    return QueryResponse(
    final_answer=result.get("final_answer", ""),
    run_sql=result.get("run_sql", False),
    sql_ran=result.get("sql_ran", False),
    retrieved_chunks=result.get("retrieved_chunks", 0),
    sql=result.get("sql"),
)