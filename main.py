from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel
from typing import List, Optional
import uuid
import subprocess
import os
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import fitz  # PyMuPDF for PDF processing
import json

# Install python-multipart
# Ensure to install the required library
try:
    import multipart
except ImportError:
    raise RuntimeError("Form data requires 'python-multipart'. Install it with 'pip install python-multipart'.")

# Qdrant client setup
qdrant_client = QdrantClient(
    "https://fb8eb5f5-ed8f-46ba-92be-012584859271.eu-west-1-0.aws.cloud.qdrant.io:6333", 
    api_key=os.getenv("QDRANT_API_KEY", None),
)

collection_name = "rag_documents"

# Ensure the collection exists
if not qdrant_client.collection_exists(collection_name):
    qdrant_client.create_collection(
        collection_name=collection_name,
        vectors_config={"size": 768, "distance": "Cosine"}  # Updated size for embedding model
    )

# Function to generate embeddings using local Ollama model
def generate_embedding(content: str) -> List[float]:
    try:
        # Call Ollama embedding model with specific prompt
        process = subprocess.run(
            ["ollama", "embeddings", "--model", "nomic-embed-text", "--prompt", content],
            capture_output=True,
            text=True,
            check=True
        )
        embedding = json.loads(process.stdout)
        return embedding["vector"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Embedding generation failed: {str(e)}")

# Function to extract text from a PDF file
def extract_text_from_pdf(file_path: str) -> str:
    try:
        pdf_document = fitz.open(file_path)
        text = ""
        for page in pdf_document:
            text += page.get_text()
        return text
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process PDF file: {str(e)}")

# Index all PDFs in a folder
def index_pdfs_from_folder(folder_path: str):
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if file_name.lower().endswith(".pdf"):
            try:
                content = extract_text_from_pdf(file_path)
                doc_id = str(uuid.uuid4())
                vector = generate_embedding(content)

                # Add document to Qdrant
                qdrant_client.upsert(
                    collection_name=collection_name,
                    points=[PointStruct(id=doc_id, payload={"content": content}, vector=vector)]
                )
                print(f"Indexed PDF: {file_name}")
            except Exception as e:
                print(f"Failed to index {file_name}: {e}")

# FastAPI app
app = FastAPI()

class Document(BaseModel):
    content: str

class SearchQuery(BaseModel):
    query: str

@app.post("/documents/", response_model=dict)
def add_document(document: Document):
    doc_id = str(uuid.uuid4())
    content = document.content
    vector = generate_embedding(content)
    
    # Add document to Qdrant
    qdrant_client.upsert(
        collection_name=collection_name,
        points=[PointStruct(id=doc_id, payload={"content": content}, vector=vector)]
    )
    return {"doc_id": doc_id}

@app.post("/documents/pdf/", response_model=dict)
def add_pdf_document(file: UploadFile):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_path = file.file.name
    content = extract_text_from_pdf(file_path)
    doc_id = str(uuid.uuid4())
    vector = generate_embedding(content)

    # Add document to Qdrant
    qdrant_client.upsert(
        collection_name=collection_name,
        points=[PointStruct(id=doc_id, payload={"content": content}, vector=vector)]
    )
    return {"doc_id": doc_id}

@app.get("/documents/{doc_id}", response_model=Optional[Document])
def get_document(doc_id: str):
    # Retrieve document from Qdrant
    results = qdrant_client.scroll(
        collection_name=collection_name,
        scroll_filter={"must": [{"key": "_id", "match": {"value": doc_id}}]},
        limit=1
    )
    if not results or len(results.points) == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    content = results.points[0].payload["content"]
    return {"content": content}

@app.post("/search/", response_model=List[str])
def search_documents(query: SearchQuery):
    query_vector = generate_embedding(query.query)

    # Search in Qdrant
    search_results = qdrant_client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        limit=10  # Return top 10 results
    )
    return [result.id for result in search_results]

@app.post("/index-folder/")
def index_folder(folder_path: str):
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=400, detail="Invalid folder path")
    index_pdfs_from_folder(folder_path)
    return {"message": f"Indexed all PDFs from folder: {folder_path}"}
