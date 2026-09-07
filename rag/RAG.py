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
BASE_DIR = Path(__file__).resolve().parent

# Define all PDF paths in a list
PDF_PATHS = [
    str(BASE_DIR.parent / "data" / "qanoon el madany summarized.pdf"),
    str(BASE_DIR.parent / "data" / "mo5tarat mn a7kam el naqd.pdf"),
    str(BASE_DIR.parent / "data" / "mabade2 qanoneya sadera 3n ma7kamet el naqd.pdf")
]

VECTOR_DB_DIR = "./qanoon_chroma_db"
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
EMBEDDING_MODEL_ID = "BAAI/bge-m3"

SYSTEM_PROMPT = (
    "أنت مساعد قانوني مصري خبير، ومهمتك هي الإجابة على أسئلة المستخدم بالاعتماد حصرياً "
    "على المقتطفات المقدمة.\n"
    "أجب باللغة العربية بناءً على السياق فقط واذكر رقم المادة القانونية متى أمكن.\n"
    "إذا كان السياق لا يحتوي على معلومات كافية للإجابة، فقل بصراحة أن الموضوع غير مغطى."
)

USER_TEMPLATE = "السياق من القانون المصري:\n{context}\n\nالسؤال: {question}"

rag_chain = None
tokenizer_global = None


# --------------------------------------------------------------------------- #
# Component Builders
# --------------------------------------------------------------------------- #
def get_embedding_model() -> HuggingFaceEmbeddings:
    print(f"[*] Initializing embeddings ({EMBEDDING_MODEL_ID}) on CPU...")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_ID,
        model_kwargs={"device": "cpu"},
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

    raw_docs = []
    for pdf_path in PDF_PATHS:
        if not Path(pdf_path).exists():
            print(f"[!] Warning: '{pdf_path}' not found. Skipping.")
            continue
            
        print(f"[*] Ingesting '{pdf_path}' via PyMuPDF...")
        loader = PyMuPDFLoader(pdf_path)
        raw_docs.extend(loader.load())

    if not raw_docs:
        raise FileNotFoundError("None of the specified PDF files were found in the project directory.")

    print(f"[+] Ingested a total of {len(raw_docs)} pages.")
    print("[*] Scrubbing OCR artifacts via Regex...")
    
    for doc in raw_docs:
        doc.page_content = re.sub(r'مادة\s*\$\((\d+)\)-(\d+)\$?', r'مادة \2 (\1)', doc.page_content)
        doc.page_content = re.sub(r'مادة\s*\$?[a-zA-Z]?\s*-?\s*(\d+)', r'مادة \1', doc.page_content)
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
        print(f"[*] No CUDA device found. Loading LLM ({MODEL_ID}) on CPU in float32.")
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
        
        # Optionally extract source document name for better context referencing
        source = doc.metadata.get("source", "Unknown Document")
        source_name = Path(source).name
        
        formatted.append(f"--- [مقتطف {i} | المصدر: {source_name} | صفحة {page_display}] ---\n{doc.page_content.strip()}")
    return "\n\n".join(formatted)


def extract_answer(full_text: str) -> str:
    """Slices the raw LLM output to isolate the assistant response and drops over-generation."""
    marker = "<|im_start|>assistant"
    
    # 1. Isolate the assistant's part
    if marker in full_text:
        output = full_text.split(marker)[-1]
    else:
        output = full_text
        
    # 2. Hard cutoff at the end-of-turn token to eliminate hallucinated text
    stop_token = "<|im_end|>"
    if stop_token in output:
        output = output.split(stop_token)[0]
        
    return output.strip()


# --------------------------------------------------------------------------- #
# FastAPI App & Lifecycle
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    global rag_chain, tokenizer_global
    print("\n" + "=" * 60)
    print("Initializing Egyptian Law RAG System...")
    print("=" * 60)
    try:
        embedding_model = get_embedding_model()
        vector_store = initialize_vector_store(embedding_model)
        retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 5})
        llm, tokenizer_global = load_llm_pipeline()

        custom_prompt = build_prompt_runnable(tokenizer_global)
        rag_chain = (
            {"context": retriever | format_docs, "question": RunnablePassthrough()}
            | custom_prompt
            | llm
            | StrOutputParser()
            | RunnableLambda(extract_answer)
        )
        print("\n[+] RAG Chain successfully compiled and active.\n")
    except Exception as exc:
        print(f"\n[FATAL] Error initializing RAG pipeline: {exc}\n", file=sys.stderr)

    yield
    print("Shutting down RAG System...")


app = FastAPI(title="Egyptian Law RAG API", lifespan=lifespan)

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
    question: str = Field(..., description="User query regarding Egyptian Law")


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
            clean_output = "عذراً، المقتطفات المقدمة لا تحتوي على معلومات كافية."
        return ChatResponse(answer=clean_output)
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Inference pipeline failure: {err}") from err