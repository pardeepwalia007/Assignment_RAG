# ui.py
# Run: streamlit run Code/ui.py

import time
import requests
import streamlit as st
import json
import plotly.io as pio 
import uuid # [FIX] Required for generating unique keys

API_URL = "http://127.0.0.1:8000/query"

st.set_page_config(page_title="BI Agent", page_icon="📊", layout="wide")
st.title("BI Agent")

# -----------------------------
# Helpers
# -----------------------------
def typewriter(text: str, speed: float = 0.012):
    """Provides typewriter animation for assistant responses."""
    placeholder = st.empty()
    rendered = ""
    for ch in text:
        rendered += ch
        placeholder.markdown(rendered)
        time.sleep(speed)
    return rendered

def call_api(question: str, customers_csv, tickets_csv, pdf_files):
    """Sends user query and uploaded files to the backend API."""
    multipart_files = [
        ("customers_csv", (customers_csv.name, customers_csv.getvalue(), "text/csv")),
        ("tickets_csv", (tickets_csv.name, tickets_csv.getvalue(), "text/csv"))
    ]
    for p in (pdf_files or []):
        multipart_files.append(("pdf_files", (p.name, p.getvalue(), "application/pdf")))

    data = {"question": question}
    return requests.post(API_URL, data=data, files=multipart_files, timeout=600)

# -----------------------------
# Session state
# -----------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "intro_done" not in st.session_state:
    st.session_state.intro_done = False

# -----------------------------
# Sidebar uploads
# -----------------------------
with st.sidebar:
    st.header("Data")
    customers_csv = st.file_uploader("Customers CSV", type=["csv"])
    tickets_csv   = st.file_uploader("Tickets CSV", type=["csv"])
    pdf_files = st.file_uploader("Drop PDFs (optional)", type=["pdf"], accept_multiple_files=True)
    st.caption("Upload once, then just chat.")

# -----------------------------
# Intro message (typed once)
# -----------------------------
INTRO = (
   """
    ### 👋 Hello! I’m your AI Support Assistant.
    
    I am connected to the **Enterprise Support Database** and **Company Policy Knowledge Base**.
    
    **Try asking me questions like:**
    * 📄 *"What is the standard refund policy?"*
    * 👤 *"Show me the profile and ticket history for customer Name."*
    * 🔍 *"Does Ema Patel have any open tickets that qualify for a refund?"*
    
    I automatically route your query to the **Policy Docs** (for rules) or the **SQL Database** (for customer records).
    """
)

if not st.session_state.intro_done and len(st.session_state.messages) == 0:
    with st.chat_message("assistant"):
        typewriter(INTRO, speed=0.010)

    st.session_state.messages.append({"role": "assistant", "content": INTRO})
    st.session_state.intro_done = True
    st.rerun()

# 
# Render chat history
# 
for i, m in enumerate(st.session_state.messages):
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        

# 
# Chat input
# 
question = st.chat_input("Ask a business question...")

if question:
    if not customers_csv or not tickets_csv:
        st.error("Upload both Customers CSV and Tickets CSV in the sidebar first.")
        st.stop()

    # show user message immediately
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    # call backend + typewriter response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            r = call_api(question, customers_csv, tickets_csv, pdf_files)

        if r.status_code != 200:
            err = f"API error {r.status_code}: {r.text}"
            typewriter(err, speed=0.008)
            st.session_state.messages.append({"role": "assistant", "content": err})
            st.stop()

        out = r.json()
        answer = (out.get("final_answer") or "").strip() or "(No answer returned.)"
        
        # Extract viz data
        viz_json = out.get("viz_data")

        # 1. Render Text
        typewriter(answer, speed=0.010)
        
        # 2. Render Chart (if exists)
        if viz_json:
            try:
                fig = pio.from_json(viz_json)
                # [FIX] Generate a random UUID for the new chart to prevent ID collisions
                st.plotly_chart(fig, use_container_width=True, key=f"new_chart_{uuid.uuid4()}")
            except Exception as e:
                st.error(f"Could not render chart: {e}")

    # Save both text and viz_data to history
    st.session_state.messages.append({
        "role": "assistant", 
        "content": answer, 
        "viz_data": viz_json
    })
    
    st.rerun()