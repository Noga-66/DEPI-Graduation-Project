import os
import time

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS

os.environ["GOOGLE_API_KEY"] = "AQ.Ab8RN6KPbsPaW6fZyQp8N5jvdG_HM5cg_xnnmVH-XZBhQmKgSg"

CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

BATCH_SIZE = 90
SLEEP_SECONDS = 65
OUTPUT_PATH = "models/vector_store"


def build_and_save_db():
    print("Loading manuals")

    solar_docs = PyPDFLoader("Datasets/manuals/ABB_PVS800_Manual.pdf").load()
    wind_docs = PyPDFLoader("Datasets/manuals/wind_turbine_manual.pdf").load()
    all_docs = solar_docs + wind_docs
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(all_docs)
    print(f"Created {len(chunks)} chunks.")
    embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")

    vector_store = None

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]

        print(f"Embedding batch {start}-{start + len(batch) - 1} / {len(chunks)}")

        if vector_store is None:
            vector_store = FAISS.from_documents(
                batch,
                embeddings,
            )
        else:
            vector_store.add_documents(batch)

        if start + BATCH_SIZE < len(chunks):
            print(f"Sleeping {SLEEP_SECONDS} seconds...")
            time.sleep(SLEEP_SECONDS)

    vector_store.save_local(OUTPUT_PATH)
    print(f"Saved vector database to '{OUTPUT_PATH}'")


if __name__ == "__main__":
    build_and_save_db()