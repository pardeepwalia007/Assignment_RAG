# test_mcp.py
# testing purpose of mcp server 
# 
from Code.mcp_server import create_session, ask

with open(r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/customers.csv", "rb") as f:
    customers_bytes = f.read()

with open(r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/tickets.csv", "rb") as f:
    tickets_bytes = f.read()

session = create_session(
    customers_csv_bytes=customers_bytes,
    tickets_csv_bytes=tickets_bytes,
    pdf_files=[]
)

sid = session["session_id"] if isinstance(session, dict) else session
print("Session ID:", sid)

result = ask(
    session_id=sid,
    question="How many open tickets are there?"
)

print("Result:", result if isinstance(result, str) else result.get("answer", result))