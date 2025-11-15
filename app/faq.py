import pandas as pd
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

faq_path=Path(__file__).parent / "resources/faq_data.csv"
chroma_client=chromadb.Client()
collection_name_faq="faqs"
groq_client=Groq()

def ingest_faq_data(path):
    # Check if the collection already exists in ChromaDB
    # chroma_client.list_collections() returns all existing collections
    if collection_name_faq not in [c.name for c in chroma_client.list_collections()]:
        print("Ingesting FAQ data into ChromaDB...")

        # Create a new collection in Chroma (or get it if it already exists)
        collection = chroma_client.get_or_create_collection(
            name=collection_name_faq,
        )

        # Read the FAQ CSV file (expects 'question' and 'answer' columns)
        df = pd.read_csv(path)

        # Convert the 'question' column into a list of documents
        docs = df["question"].to_list()

        # Create metadata for each question — store the corresponding answer
        metadata = [{"answer": ans} for ans in df["answer"].to_list()]

        # Create a unique ID for each FAQ entry (e.g., id_0, id_1, id_2, ...)
        ids = [f"id_{i}" for i in range(len(docs))]

        # Add all data (ids, questions, answers) into the ChromaDB collection
        collection.add(
            ids=ids,
            documents=docs,
            metadatas=metadata
        )
    else:
        # If the collection already exists, print a message and skip ingestion
        print("Collection", collection_name_faq, "already exists!")

def get_relevant_qa(query):
    collection=chroma_client.get_collection(name=collection_name_faq)
    result = collection.query(
        query_texts=[query],
        n_results=2
    )
    return result

def generate_ans(query):
    result=get_relevant_qa(query)
    context="".join(ans.get("answer") for ans in result["metadatas"][0])
    prompt=f''' 
        given the question and context, below generate an answer based on the context.
        If you don't know the answer inside the context, then say "I don't know".
        Don't make things up.

        QUESTION: {query}
        CONTEXT: {context}
    '''
    
    completion = groq_client.chat.completions.create(
        model=os.environ["GROQ_MODEL"],
        messages=[
        {
            "role": "user",
            "content":prompt
        }
        ],
        temperature=0.8,
        max_tokens=500
    )

    answer = completion.choices[0].message.content
    return answer
