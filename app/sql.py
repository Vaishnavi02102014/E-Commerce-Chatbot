# app/sql.py
import sqlite3
import pandas as pd
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv
import os
import re
import traceback
import logging

load_dotenv()
sql_client = Groq()

logger = logging.getLogger("app.sql")
logger.setLevel(logging.INFO)

def create_db_from_csv_if_missing(db_path: Path, csv_path: Path, table_name: str = "product"):
    """
    If db_path does not exist but csv_path exists, create a sqlite DB and write the CSV to the table.
    """
    try:
        if db_path.exists():
            logger.info(f"DB already exists at {db_path}")
            return True

        if not csv_path.exists():
            logger.warning(f"CSV for DB creation not found at {csv_path}")
            return False

        logger.info(f"Creating DB at {db_path} from CSV {csv_path} ...")
        df = pd.read_csv(csv_path)

        # Basic column check and cast - adapt as needed
        expected_cols = ['product_link', 'title', 'brand', 'price', 'discount', 'avg_rating', 'total_ratings']
        missing = [c for c in expected_cols if c not in df.columns]
        if missing:
            logger.warning(f"CSV is missing columns required for table creation: {missing}. Proceeding anyway.")

        # convert numeric columns where possible
        for col in ["price", "discount", "avg_rating", "total_ratings"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Ensure parent dir exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to sqlite
        with sqlite3.connect(db_path) as conn:
            df.to_sql(table_name, conn, if_exists="replace", index=False)
        logger.info(f"Created DB and table '{table_name}' with {len(df)} rows.")
        return True
    except Exception as e:
        logger.error("Failed to create DB from CSV: " + str(e))
        logger.error(traceback.format_exc())
        return False

def find_db():
    """
    Robustly find products.db in the repo. If not found, try to build from CSV.
    Returns a pathlib.Path to the DB or raises FileNotFoundError.
    """
    here = Path(__file__).resolve()
    project_root = here.parents[1]  # app/ -> project root
    expected = project_root / "web_scrapping" / "products.db"

    if expected.exists():
        return expected

    # fallback: search for any products.db under project root
    candidates = list(project_root.rglob("products.db"))
    if candidates:
        return candidates[0]

    # if not found try to create from CSV if flipkart_product_data.csv exists
    csv_candidate = project_root / "web_scrapping" / "flipkart_product_data.csv"
    created = create_db_from_csv_if_missing(expected, csv_candidate)
    if created and expected.exists():
        return expected

    # still not found - raise readable error
    raise FileNotFoundError(
        f"products.db not found. Tried: {expected}. "
        f"CSV fallback present? {csv_candidate.exists()}. "
        "If you want to include a prebuilt DB, add web_scrapping/products.db to repo or host it and modify sql.py."
    )

# locate DB at import time (raises if not available and cannot be created)
try:
    db_path = find_db()
    logger.info(f"Using DB at: {db_path}")
except Exception as e:
    # Keep the error, but don't crash import - functions will raise meaningful errors later.
    logger.error("Error locating/creating products.db: " + str(e))
    db_path = None

def generate_query(question):
    sql_prompt=''' 
       You are an expert in understanding the database schema and generating SQL queries for a natural language
       question pertaining to the data you have. The schema is provided in the schema tags
       <schema>
       table: product
       
       fields:
       product_link- string (hyperlink to product)
       title- string (name of the product)
       brand- string (brand of the product)
       price- integer (price of the product in Indian Rupees)
       discount- float (discount on the product. 10% discount is represented as 0.1, 20% discount is
       represented as 0.2)
       avg_rating- integer (average rating of the product. Range 0-5, 5 is the highest)
       total_ratings- integer (total number of ratings for the product)
       </schema>

       Make sure whenever you try to search for a brand name, the name can be in any case.
       So, make sure to use %LIKE% to find the brand in condition. Never use "ILIKE".
       Create a single sql query for the question provided.
       The query should have all the fields in SELECT clause (i.e. SELECT *)
       Just the sql query is needed, nothing else.
       the SQL query should be generated within <SQL></SQL> tags.
    '''

    chat_completion = sql_client.chat.completions.create(
        messages=[
            {
                "role": "system",
                "content": sql_prompt,
            },
            {
                "role": "user",
                "content": question,
            }
        ],
        model=os.environ.get("GROQ_MODEL"),
        temperature=0.2,
        max_tokens=1024
    )

    return chat_completion.choices[0].message.content

def run_query(query):
    if db_path is None:
        raise FileNotFoundError("products.db not found on server and could not be created. Check logs.")

    if not query.strip().upper().startswith("SELECT"):
        raise ValueError("Only SELECT queries are allowed.")

    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query(query, conn)
            return df
        except Exception as e:
            logger.error("SQL execution error: " + str(e))
            logger.error("Query was: " + query)
            logger.error(traceback.format_exc())
            raise

def sql_chain(question):
    try:
        sql_query = generate_query(question)
    except Exception as e:
        logger.error("LLM SQL generation failed: " + str(e))
        return "Sorry, could not generate SQL for that question."

    pattern = r"<SQL>(.*?)</SQL>"
    match = re.search(pattern, sql_query, re.DOTALL)
    if match is None:
        logger.error("LLM did not return SQL in <SQL> tags. Full LLM output:")
        logger.error(sql_query)
        return "Sorry, LLM did not return a SQL query."

    try:
        df = run_query(match.group(1).strip())
    except FileNotFoundError as fe:
        # friendly message for missing DB
        logger.error(str(fe))
        return "Products database not found on server. Please create web_scrapping/products.db or add flipkart_product_data.csv so the app can build the DB."
    except Exception as e:
        logger.error("Error running SQL: " + str(e))
        return f"Error executing SQL: {e}"

    if df is None or df.empty:
        return "No result found"

    # convert df into list of dicts for comprehension step
    context = df.to_dict(orient="records")
    try:
        answer = data_comprehension(question, context)
        return answer
    except Exception as e:
        logger.error("Data comprehension failed: " + str(e))
        logger.error(traceback.format_exc())
        return "Failed to create answer from data."

def data_comprehension(question, context):
    comprehension_promt='''
        You are an expert in understanding the context of the question and replying based on the data pertaining 
        to the question provided. You will be provided with QUESTION: and DATA:. The data will be in the form of an array or a dataframe or dict. 
        Reply based on only the data provided as Data for answering the question asked as QUESTION. 
        Do not write anything like 'Based on the data' or any other technical words. Just a plain simple natural language response. 
        The Data would always be in context to the question asked. For example is the question is “What is the average rating?” 
        and data is “4.3”, then answer should be “The average rating for the product is 4.3”. So make sure the response is curated 
        with the QUESTION and DATA. Make sure to note the column names to have some context, if needed, for your response. 
        There can also be cases where you are given an entire dataframe in the DATA: field. Always remember that the data field 
        contains the answer of the question asked. 

        All you need to do is to always reply in the following format when asked about a product: 
        product title, price in indian rupees, discount, and rating, and then product link. 
        Take care that all the products are in a list format, one line after the other. Not as a paragraph.

        For example:
        1. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
    '''

    chat_completion = sql_client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL"),
        messages=[
        {
            "role": "system",
            "content": comprehension_promt
        },
        {
            "role": "user",
            "content": f"QUESTION {question} DATA {context}"
        }
        ],
        temperature=0.3,
    )
    
    return chat_completion.choices[0].message.content
