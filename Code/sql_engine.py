# sql_engine.py (STEP 1) — load 2 CSVs into DuckDB + create a safe JOIN VIEW + return view schema
import duckdb
from pathlib import Path
import re
from typing import Dict, Any, List, Tuple


def _safe_table_name(path: str) -> str:
    name = Path(path).stem.lower()
    return re.sub(r"[^a-z0-9_]", "_", name)


def _type_aware_schema(con: duckdb.DuckDBPyConnection, table_or_view: str) -> Tuple[Dict[str, Any], List[str]]:
    schema_info = con.execute(f"DESCRIBE {table_or_view}").fetchall()

    numeric_cols, date_cols, text_cols = [], [], []
    ingestion_warnings: List[str] = []

    cols_found = [c[0].lower() for c in schema_info]

    pk_candidate = None
    for preferred in ["customer_id", "ticket_id", "sale_id", "transaction_id", "order_id", "id"]:
        if preferred in cols_found:
            pk_candidate = preferred
            break
    if not pk_candidate:
        for col in cols_found:
            if col.endswith("_id"):
                pk_candidate = col
                break

    for row in schema_info:
        name, dtype = row[0], str(row[1]).upper()
        if any(t in dtype for t in ["INT", "DOUBLE", "FLOAT", "DECIMAL", "BIGINT", "HUGEINT"]):
            numeric_cols.append(name)
        elif any(t in dtype for t in ["DATE", "TIMESTAMP"]):
            date_cols.append(name)
        else:
            text_cols.append(name)

    type_schema = {
        "TABLE": table_or_view,
        "PRIMARY_KEY_ID": pk_candidate,
        "NUMERIC COLUMNS": ", ".join(numeric_cols),
        "DATE COLUMNS": ", ".join(date_cols),
        "TEXT COLUMNS": ", ".join(text_cols),
    }
    return type_schema, ingestion_warnings


def load_two_csvs_to_duckdb(
    customers_csv_path: str,
    tickets_csv_path: str,
    join_key: str = "customer_id",
    view_name: str = "customer_tickets",
) -> Tuple[duckdb.DuckDBPyConnection, Dict[str, str], Dict[str, Dict[str, Any]], List[str]]:
    """
    Loads 2 CSVs as separate DuckDB tables + creates a safe JOIN VIEW.
    Returns:
      - con
      - table_names: {"customers": "<tbl>", "tickets": "<tbl>", "view": "<view>"}
      - schemas: {"customers": {...}, "tickets": {...}, "view": {...}}
      - warnings: list[str]
    """
    con = duckdb.connect()
    warnings: List[str] = []

    customers_tbl = _safe_table_name(customers_csv_path)
    tickets_tbl = _safe_table_name(tickets_csv_path)

    # 1) Load BOTH tables
    con.execute(f"""
        CREATE OR REPLACE TABLE {customers_tbl} AS
        SELECT * FROM read_csv_auto('{customers_csv_path}')
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE {tickets_tbl} AS
        SELECT * FROM read_csv_auto('{tickets_csv_path}')
    """)

    # 2) Create a SAFE JOIN VIEW (LLM queries THIS when it needs both)
    # NOTE: we prefix columns to avoid collisions like "id" existing in both tables.
    con.execute(f"""
        CREATE OR REPLACE VIEW {view_name} AS
        SELECT
            c.*,
            t.*
        FROM {customers_tbl} c
        LEFT JOIN {tickets_tbl} t
        ON c."{join_key}" = t."{join_key}"
    """)

    # 3) Build schema for each table + the view
    customers_schema, w1 = _type_aware_schema(con, customers_tbl)
    tickets_schema, w2 = _type_aware_schema(con, tickets_tbl)
    view_schema, w3 = _type_aware_schema(con, view_name)

    warnings.extend(w1)
    warnings.extend(w2)
    warnings.extend(w3)

    table_names = {"customers": customers_tbl, "tickets": tickets_tbl, "view": view_name}
    schemas = {"customers": customers_schema, "tickets": tickets_schema, "view": view_schema}

    return con, table_names, schemas, warnings


if __name__ == "__main__":
    customers_path = r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/customers.csv"
    tickets_path   = r"/Users/pardeepwalia/Desktop/Data/TCS-Submission/Data/csv/tickets.csv"

    con, table_names, schemas, warnings = load_two_csvs_to_duckdb(
        customers_csv_path=customers_path,
        tickets_csv_path=tickets_path,
        join_key="customer_id",
        view_name="customer_tickets",
    )

    print("\n✅ Loaded tables/view:")
    print(table_names)

    # 1) Row counts
    customers_cnt = con.execute(f"SELECT COUNT(*) FROM {table_names['customers']}").fetchone()[0]
    tickets_cnt   = con.execute(f"SELECT COUNT(*) FROM {table_names['tickets']}").fetchone()[0]
    view_cnt      = con.execute(f"SELECT COUNT(*) FROM {table_names['view']}").fetchone()[0]

    print("\n📦 Row counts:")
    print("customers:", customers_cnt)
    print("tickets:  ", tickets_cnt)
    print("view:     ", view_cnt)

    # 2) Quick preview
    print("\n👀 customers sample:")
    print(con.execute(f"SELECT * FROM {table_names['customers']} LIMIT 3").fetchdf())

    print("\n👀 tickets sample:")
    print(con.execute(f"SELECT * FROM {table_names['tickets']} LIMIT 3").fetchdf())

    print("\n👀 view sample (joined):")
    print(con.execute(f"SELECT * FROM {table_names['view']} LIMIT 3").fetchdf())

    # 3) Schema prints
    print("\n🧠 Schemas:")
    print("customers_schema:", schemas["customers"])
    print("tickets_schema:  ", schemas["tickets"])
    print("view_schema:     ", schemas["view"])

    # 4) Warnings
    if warnings:
        print("\n⚠️ Warnings:")
        for w in warnings:
            print("-", w)
    else:
        print("\n✅ No warnings.")