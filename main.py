import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore

from pinecone import Pinecone
from openai import OpenAI
from langchain_community.document_loaders import YoutubeLoader, PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tiktoken
from typing import List
from fastapi.responses import StreamingResponse
import json
import re

from sqlalchemy.orm import Session
from database import SessionLocal, Base, engine, init_db
from models import Product, SubProduct, Complaint
from complaint_storage import store_complaint

# Initialize the database
init_db()

# Load environment variables
load_dotenv()

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get API keys from environment variables
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY is not set in .env file")
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY is not set in .env file")

# Initialize HuggingFace Embeddings
hf_embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize OpenRouter client
openrouter_client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# Initialize Pinecone
pc = Pinecone(api_key=PINECONE_API_KEY)
pinecone_index = pc.Index("ruby")

# Initialize PineconeVectorStore
vectorstore = PineconeVectorStore(index_name="ruby", embedding=hf_embeddings)

# Initialize tokenizer for text splitting
tokenizer = tiktoken.get_encoding('p50k_base')

def tiktoken_len(text):
    tokens = tokenizer.encode(
        text,
        disallowed_special=()
    )
    return len(tokens)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=60,
    length_function=tiktoken_len,
    separators=["\n\n", "\n", " ", ""]
)

def get_rag_context(query: str) -> str:
    # Load the embedding model
    model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    # Create the embedding for the query
    query_embedding = model.encode(query)

    # Query the Pinecone index using the embedding
    top_matches = pinecone_index.query(
        vector=query_embedding.tolist(),
        top_k=10,
        include_metadata=True,
        namespace="json-documents"
    )

    # Get the list of retrieved texts
    contexts = [item['metadata']['text'] for item in top_matches['matches']]

    # Log the retrieved contexts
    print(f"Retrieved contexts: {contexts}")

    # Create the augmented query with context
    augmented_query = "<CONTEXT>\n" + "\n\n-------\n\n".join(contexts[:10]) + "\n-------\n</CONTEXT>\n\n\n\nMY QUESTION:\n" + query

    print(f"Augmented query: {augmented_query}")
    return augmented_query

def perform_rag(query: str) -> str:
    augmented_query = get_rag_context(query)

    system_prompt = """You are a customer complaint analyst. Categorize and analyze the given complaint based on the context provided. Your response should be in plain text and follow this format:

Product: [Main product category of the complaint]
Sub-product: [Sub-product category if applicable]
Complaint: [The text of the complaint]

Ensure the response includes all the fields as described, and format it exactly as shown. No additional information or text should be included outside of this format."""

    res = openrouter_client.chat.completions.create(
        model="qwen/qwen-2-7b-instruct:free",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_query}
        ]
    )

    # Ensure the response is valid plain text
    response = res.choices[0].message.content

    try:
        # Extract details and validate
        product = extract_field(response, "Product")
        print(f"Product: {product}")
        sub_product = extract_field(response, "Sub-product")
        print(f"Sub-product: {sub_product}")
        complaint = extract_field(response, "Complaint")
        print(f"Complaint: {complaint}")

        if not product or not sub_product or not complaint:
            raise ValueError("Missing expected fields in the response")

        # Store the complaint in the database
        print("Storing complaint in the database...")
        store_complaint(product, sub_product, complaint)

    except Exception as e:
        print(f"Error processing the response: {e}")
        raise e

    return response

def extract_field(text: str, field_name: str) -> str:
    """Helper function to extract a specific field from the plain text response."""
    import re
    pattern = rf"{field_name}: (.+)"
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else None

async def stream_rag(query: str):
    augmented_query = get_rag_context(query)

    system_prompt = """You are a customer complaint analyst. Categorize and analyze the given complaint based on the context provided. Your response should be in plain text and follow this format:

Product: [Main product category of the complaint]
Sub-product: [Sub-product category if applicable]
Complaint: [The text of the complaint]

Ensure the response includes all the fields as described, and format it exactly as shown. No additional information or text should be included outside of this format."""

    stream = openrouter_client.chat.completions.create(
        model="qwen/qwen-2-7b-instruct:free",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_query}
        ],
        stream=True
    )

    full_response = ""
    print("Streaming response:")
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            full_response += content
            print(content, end="")  # Print each chunk as it is received
            yield content

    print(f"\nFull streamed response: {full_response}")

    # Extract details and validate
    try:
        product = extract_field(full_response, "Product")
        print(f"Product: {product}")
        sub_product = extract_field(full_response, "Sub-product")
        print(f"Sub-product: {sub_product}")
        complaint = extract_field(full_response, "Complaint")
        print(f"Complaint: {complaint}")

        if not product or not sub_product or not complaint:
            raise ValueError("Missing expected fields in the response")

        # Store the complaint in the database
        print("Storing complaint in the database...")
        store_complaint(product, sub_product, complaint)

    except Exception as e:
        print(f"Error processing the response: {e}")
        raise e

class Query(BaseModel):
    query: str

@app.post("/rag")
async def rag_endpoint(query: Query):
    try:
        response = perform_rag(query.query)
        return {"response": response}
    except Exception as e:
        print(f"Error in /rag endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/stream_rag")
async def stream_rag_endpoint(query: Query):
    try:
        return StreamingResponse(stream_rag(query.query), media_type="text/plain")
    except Exception as e:
        print(f"Error in /stream_rag endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest_json")
async def ingest_json(file: UploadFile = File(...)):
    try:
        # Save the uploaded file temporarily
        temp_file_path = f"temp_{file.filename}"
        with open(temp_file_path, "wb") as buffer:
            buffer.write(await file.read())

        print(f"Uploaded JSON saved at: {temp_file_path}")
        
        # Load JSON
        with open(temp_file_path, "r") as f:
            data = json.load(f)

        print(f"Loaded JSON data: {data}")

        # Split the JSON content into chunks
        texts = [json.dumps(item) for item in data]  # Assuming the JSON is a list of items

        # Insert chunks into Pinecone
        vectorstore_from_texts = PineconeVectorStore.from_texts(
            texts,
            hf_embeddings,
            index_name="json",
            namespace="review-documents"
        )
        
        # Remove temporary file
        os.remove(temp_file_path)
        print(f"Temporary file {temp_file_path} removed.")
        
        return {"message": f"Successfully ingested JSON: {file.filename}"}
    except Exception as e:
        print(f"Error in /ingest_json endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))
