import duckdb
from pathlib import Path
import re
from typing import Dict,Any,List, Tuple


def load_csv_to_duckdb(csv_path: str):
    """
    Loads CSV into DuckDB and extracts schema for SQL operations.

    """
    con = duckdb.connect()
    table_name = Path(csv_path).stem.lower()
    table_name = re.sub(r'[^a-z0-9_]', '_', table_name)
    ingestion_warnings = [] # Collect data quality warnings
    # Load CSV into DuckDB
    con.execute(f"CREATE TABLE IF NOT EXISTS {table_name} AS SELECT * FROM read_csv_auto('{csv_path}')")

    # Extract schema information
    schema_info = con.execute(f"DESCRIBE {table_name}").fetchall()
        
    numeric_cols, date_cols, text_cols = [], [], []
    
    # Identifies primary key for transaction uniqueness.
    pk_candidate = None
    cols_found = [col[0].lower() for col in schema_info]
    
    for preferred in ["sale_id", "transaction_id", "order_id", "id"]:
        if preferred in cols_found:
            pk_candidate = preferred
            break
    
    if not pk_candidate: # Fallback to any column ending in _id
        for col in cols_found:
            if col.endswith("_id"):
                pk_candidate = col
                break

    for col in schema_info:
        name, dtype = col[0], str(col[1]).upper()
        if any(t in dtype for t in ["INT", "DOUBLE", "FLOAT", "DECIMAL"]):
            numeric_cols.append(name)
        elif any(t in dtype for t in ["DATE", "TIMESTAMP"]):
            date_cols.append(name)
        else:
            text_cols.append(name)
    print("testing")
    type_aware_schema = {
    "TABLE": table_name,
    "PRIMARY_KEY_ID": pk_candidate,
    "NUMERIC COLUMNS": ", ".join(numeric_cols),
    "DATE COLUMNS": ", ".join(date_cols),
    "TEXT COLUMNS": ", ".join(text_cols),
    }
    print(f"Type-aware schema: {type_aware_schema}")

    return con, table_name, type_aware_schema, numeric_cols , ingestion_warnings

# load_csv_to_duckdb(r'/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/customers.csv')