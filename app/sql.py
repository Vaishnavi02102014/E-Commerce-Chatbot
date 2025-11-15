import sqlite3
import pandas as pd
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv
import os
import re

load_dotenv()

db_path=Path(__file__).parent.parent / "web_scrapping/products.db"
sql_client=Groq()

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
        model=os.environ["GROQ_MODEL"],
        temperature=0.2,
        max_tokens=1024
    )

    return chat_completion.choices[0].message.content

def run_query(query):
    if query.strip().upper().startswith("SELECT"):
        with sqlite3.connect(db_path) as conn:
            df=pd.read_sql_query(query, conn)
            return df 
        
def sql_chain(question):
    sql_query=generate_query(question)
    pattern="<SQL>(.*?)</SQL>"
    match = re.search(pattern, sql_query, re.DOTALL)
    if match is None:
        return "Sorry, LLM is not able to generate a query for your question."
    df=run_query(match.group(1).strip())
    if df is None:
        return "No result found"
    
    #converts df into list of dictionaries. [{col1:val1, col2:val2}, {col1:val3, col2:val4}]
    context=df.to_dict(orient="records")

    answer=data_comprehension(question, context)
    return answer

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
        2. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
        3. Campus Women Running Shoes: Rs. 1104 (35 percent off), Rating: 4.4 <link>
    '''

    chat_completion = sql_client.chat.completions.create(
        model=os.environ["GROQ_MODEL"],
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
 

