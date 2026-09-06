"""
Egyptian Civil Code RAG QA API
-------------------------------
FastAPI backend serving a retrieval-augmented Q&A system grounded in
'qanoon el madany summarized.pdf'.

Pipeline: PyMuPDF -> TextSplitter + Regex Cleaning -> BGE-M3 (Multilingual) 
          -> ChromaDB -> Qwen2.5-7B-Instruct (4-bit NF4)
"""

import sys
import re
from pathlib import Path
from contextlib import asynccontextmanager

import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# LangChain Imports
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough

# Hugging Face & Quantization
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    pipeline,
)

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Resolve the directory where this python script is located
BASE_DIR = Path(__file__).resolve().parent
# Go one level up (.parent), into the 'data' folder, to the PDF
PDF_PATH = str(BASE_DIR.parent / "data" / "qanoon el madany summarized.pdf")

VECTOR_DB_DIR = "./qanoon_chroma_db"
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"

# Swapped to a multilingual embedding model capable of understanding Arabic
EMBEDDING_MODEL_ID = "BAAI/bge-m3"

SYSTEM_PROMPT = (
    "أنت مساعد قانوني مصري خبير، ومهمتك هي الإجابة على أسئلة المستخدم بالاعتماد حصرياً "
    "على المقتطفات المقدمة من 'القانون المدني المصري'.\n"
    "أجب باللغة العربية (أو بأسلوب مصري مهني وواضح) بناءً على السياق فقط واذكر رقم المادة القانونية متى أمكن.\n"
    "إذا كان السياق لا يحتوي على معلومات كافية للإجابة، فقل بصراحة أن الموضوع غير مغطى "
    "في المقتطفات المقدمة ولا تخترع إجابة من عندك أو تستخدم معلومات خارجية."
)

USER_TEMPLATE = "السياق من القانون المدني:\n{context}\n\nالسؤال: {question}"

rag_chain = None
tokenizer_global = None


# --------------------------------------------------------------------------- #
# Component builders
# --------------------------------------------------------------------------- #
def get_embedding_model() -> HuggingFaceEmbeddings:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[*] Initializing embeddings ({EMBEDDING_MODEL_ID}) on {device}...")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_ID,
        model_kwargs={"device": device},
        encode_kwargs={"normalize_embeddings": True},
    )


def initialize_vector_store(embedding_model: HuggingFaceEmbeddings) -> Chroma:
    db_path = Path(VECTOR_DB_DIR)

    if db_path.exists() and any(db_path.iterdir()):
        print(f"[*] Found persisted Chroma vector index at '{VECTOR_DB_DIR}'. Loading...")
        return Chroma(
            persist_directory=VECTOR_DB_DIR,
            embedding_function=embedding_model,
        )

    if not Path(PDF_PATH).exists():
        raise FileNotFoundError(
            f"'{PDF_PATH}' not found in project directory. Please provide the correct PDF file."
        )

    print(f"[*] Ingesting '{PDF_PATH}' via PyMuPDF...")
    loader = PyMuPDFLoader(PDF_PATH)
    raw_docs = loader.load()
    print(f"[+] Ingested {len(raw_docs)} pages.")

    print("[*] Scrubbing OCR artifacts via Regex...")
    for doc in raw_docs:
        # Fix inverted brackets with dollar signs (e.g., "مادة $(1)-13$" -> "مادة 13 (1)")
        doc.page_content = re.sub(r'مادة\s*\$\((\d+)\)-(\d+)\$?', r'مادة \2 (\1)', doc.page_content)
        
        # Strip rogue Latin letters/dollar signs in simple headers (e.g., "مادة $Y-28$" -> "مادة 28")
        doc.page_content = re.sub(r'مادة\s*\$?[a-zA-Z]?\s*-?\s*(\d+)', r'مادة \1', doc.page_content)
        
        # Remove any remaining stray dollar signs
        doc.page_content = doc.page_content.replace('$', '')

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=900,
        chunk_overlap=150,
        separators=["\n\n", "\n", " ", ""],
    )
    
    chunks = text_splitter.split_documents(raw_docs)
    print(f"[+] Generated {len(chunks)} semantic chunks.")

    print(f"[*] Creating Chroma index and writing to disk at '{VECTOR_DB_DIR}'...")
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=VECTOR_DB_DIR,
    )
    print("[+] Vector store indexed successfully.")
    return vector_store


def load_llm_pipeline() -> tuple[HuggingFacePipeline, AutoTokenizer]:
    cuda_available = torch.cuda.is_available()
    bf16_ok = cuda_available and torch.cuda.is_bf16_supported()
    compute_dtype = torch.bfloat16 if bf16_ok else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)

    if cuda_available:
        print(f"[*] Loading LLM ({MODEL_ID}) under 4-bit NF4 precision (Dtype: {compute_dtype})...")
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=compute_dtype,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            quantization_config=bnb_config,
            device_map="auto",
            dtype=compute_dtype,
            trust_remote_code=True,
        )
    else:
        print(f"[*] No CUDA device found. Loading LLM ({MODEL_ID}) on CPU in float32. "
              "This will be slow.")
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            device_map="cpu",
            dtype=torch.float32,
            trust_remote_code=True,
        )

    pipe = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        max_new_tokens=512,
        temperature=0.2,
        top_p=0.9,
        repetition_penalty=1.1,
        return_full_text=False,
    )

    return HuggingFacePipeline(pipeline=pipe), tokenizer


def build_prompt_runnable(tokenizer: AutoTokenizer) -> RunnableLambda:
    def render(inputs: dict) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(
                    context=inputs["context"], question=inputs["question"]
                ),
            },
        ]
        return tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )

    return RunnableLambda(render)


def format_docs(docs) -> str:
    formatted = []
    for i, doc in enumerate(docs, 1):
        raw_page = doc.metadata.get("page")
        page_display = raw_page + 1 if isinstance(raw_page, int) else "Unknown"
        # Adjusted formatting for Arabic right-to-left flow
        formatted.append(f"--- [مقتطف {i} | صفحة {page_display}] ---\n{doc.page_content.strip()}")
    return "\n\n".join(formatted)


# --------------------------------------------------------------------------- #
# FastAPI app + lifecycle
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_chain, tokenizer_global
    print("\n" + "=" * 60)
    print("Initializing Egyptian Civil Code RAG System...")
    print("=" * 60)
    try:
        embedding_model = get_embedding_model()
        vector_store = initialize_vector_store(embedding_model)
        retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 4})
        llm, tokenizer_global = load_llm_pipeline()

        custom_prompt = build_prompt_runnable(tokenizer_global)
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | custom_prompt
            | llm
            | StrOutputParser()
        )
        print("\n[+] RAG Chain successfully compiled and active.\n")
    except Exception as exc:
        print(f"\n[FATAL] Error initializing RAG pipeline: {exc}\n", file=sys.stderr)

    yield
    print("Shutting down RAG System...")


app = FastAPI(title="Egyptian Civil Code RAG API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(..., description="User query regarding the Egyptian Civil Code")


class ChatResponse(BaseModel):
    answer: str


@app.get("/")
def health():
    return {"status": "ok", "rag_ready": rag_chain is not None}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    if rag_chain is None:
        raise HTTPException(status_code=503, detail="RAG system not initialized.")

    try:
        raw_output = rag_chain.invoke(question)
        clean_output = raw_output.strip()
        if not clean_output:
            # Replaced the fallback message with an Arabic equivalent
            clean_output = "عذراً، المقتطفات المقدمة من القانون المدني لا تحتوي على معلومات كافية للإجابة على هذا السؤال."
        return ChatResponse(answer=clean_output)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Inference pipeline failure: {err}") from err