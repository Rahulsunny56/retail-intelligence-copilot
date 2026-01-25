import os
import shutil
import pandas as pd

import chromadb
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma

DOCS_PATH = "rag/docs_products.parquet"
CHROMA_DIR = "rag/chroma_products"
COLLECTION = "products"

def main():
    print("Reading docs:", DOCS_PATH)
    df = pd.read_parquet(DOCS_PATH)
    print("Docs rows:", len(df))

    docs = [
        Document(page_content=row["text"], metadata={"product_id": int(row["product_id"])})
        for _, row in df.iterrows()
    ]
    print("Built Document objects:", len(docs))

    print("Loading embeddings model...")
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    if os.path.exists(CHROMA_DIR):
        print("Removing existing index dir:", CHROMA_DIR)
        shutil.rmtree(CHROMA_DIR)

    print("Building Chroma index...")
    vectordb = Chroma.from_documents(
        documents=docs,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name=COLLECTION,
    )
    vectordb.persist()
    print("Persisted to:", CHROMA_DIR)

    # Verify count via chromadb directly
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    col = client.get_collection(COLLECTION)
    print("✅ Collection count:", col.count())

if __name__ == "__main__":
    main()
