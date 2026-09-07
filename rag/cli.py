import sys
import re
from pathlib import Path
import torch

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings, HuggingFacePipeline
from langchain_chroma import Chroma
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig, pipeline

import arabic_reshaper
from bidi.algorithm import get_display


# --- Configuration ---
BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = str(BASE_DIR.parent / "data" / "qanoon el madany summarized.pdf")
VECTOR_DB_DIR = "./qanoon_chroma_db"
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
EMBEDDING_MODEL_ID = "BAAI/bge-m3"

SYSTEM_PROMPT = (
    "أنت مساعد قانوني مصري خبير، ومهمتك هي الإجابة على أسئلة المستخدم بالاعتماد حصرياً "
    "على المقتطفات المقدمة من 'القانون المدني المصري'.\n"
    "أجب باللغة العربية بناءً على السياق فقط واذكر رقم المادة القانونية متى أمكن.\n"
    "إذا كان السياق لا يحتوي على معلومات كافية للإجابة، فقل بصراحة أن الموضوع غير مغطى."
)

USER_TEMPLATE = "السياق من القانون المدني:\n{context}\n\nالسؤال: {question}"

# --- Component Builders ---
def get_embedding_model() -> HuggingFaceEmbeddings:
    # Run embeddings on CPU so it doesn't steal VRAM from Qwen!
    print(f"[*] Initializing embeddings ({EMBEDDING_MODEL_ID}) on CPU...")
    return HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL_ID,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

def initialize_vector_store(embedding_model: HuggingFaceEmbeddings) -> Chroma:
    db_path = Path(VECTOR_DB_DIR)
    if db_path.exists() and any(db_path.iterdir()):
        return Chroma(persist_directory=VECTOR_DB_DIR, embedding_function=embedding_model)

    if not Path(PDF_PATH).exists():
        raise FileNotFoundError(f"'{PDF_PATH}' not found.")

    loader = PyMuPDFLoader(PDF_PATH)
    raw_docs = loader.load()

    for doc in raw_docs:
        doc.page_content = re.sub(r'مادة\s*\$\((\d+)\)-(\d+)\$?', r'مادة \2 (\1)', doc.page_content)
        doc.page_content = re.sub(r'مادة\s*\$?[a-zA-Z]?\s*-?\s*(\d+)', r'مادة \1', doc.page_content)
        doc.page_content = doc.page_content.replace('$', '')

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks = text_splitter.split_documents(raw_docs)
    
    return Chroma.from_documents(chunks, embedding_model, persist_directory=VECTOR_DB_DIR)

def load_llm_pipeline():
    cuda_available = torch.cuda.is_available()
    bf16_ok = cuda_available and torch.cuda.is_bf16_supported()
    compute_dtype = torch.bfloat16 if bf16_ok else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    if cuda_available:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_use_double_quant=True,
            bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=compute_dtype,
        )
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, quantization_config=bnb_config, device_map="auto",
            dtype=compute_dtype, trust_remote_code=True,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID, device_map="cpu", dtype=torch.float32, trust_remote_code=True,
        )

    pipe = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=512, temperature=0.2)
    return HuggingFacePipeline(pipeline=pipe), tokenizer

def build_prompt_runnable(tokenizer) -> RunnableLambda:
    def render(inputs: dict) -> str:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(context=inputs["context"], question=inputs["question"])},
        ]
        return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    return RunnableLambda(render)

def format_docs(docs) -> str:
    return "\n\n".join(f"--- [مقتطف {i+1}] ---\n{doc.page_content.strip()}" for i, doc in enumerate(docs))


def print_arabic(text):
    """Reshapes and flips Arabic text so it renders correctly in the terminal."""
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    print(bidi_text)

def input_arabic(prompt_text):
    """Applies the same fix to the input prompt."""
    reshaped_text = arabic_reshaper.reshape(prompt_text)
    bidi_text = get_display(reshaped_text)
    return input(bidi_text)

def extract_answer(full_text: str) -> str:
    """Slices the raw LLM output to return only the assistant's response."""
    marker = "<|im_start|>assistant"
    if marker in full_text:
        # Split at the marker and return everything after it, minus the end tag
        return full_text.split(marker)[-1].replace("<|im_end|>", "").strip()
    return full_text.strip()


# --- Interactive Loop ---
# --- Interactive Loop ---
def main():
    print_arabic("جاري تهيئة النظام... (قد يستغرق بضع ثوانٍ)")
    embedding_model = get_embedding_model()
    vector_store = initialize_vector_store(embedding_model)
    retriever = vector_store.as_retriever(search_type="similarity", search_kwargs={"k": 10})
    
    llm, tokenizer = load_llm_pipeline()
    custom_prompt = build_prompt_runnable(tokenizer)
    
    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | custom_prompt
        | llm
        | StrOutputParser()
        | RunnableLambda(extract_answer)  # <--- Add this step at the end
    )
    
    print_arabic("\n[+] النظام جاهز! اكتب 'خروج' أو 'exit' للإنهاء.\n")
    
    while True:
        try:
            # Use the new input_arabic function
            question = input_arabic("\nأنت: ").strip()
            
            if question.lower() in ['exit', 'quit', 'خروج']:
                break
            if not question:
                continue
            
            print_arabic("جاري البحث والتفكير...")
            answer = rag_chain.invoke(question).strip()
            
            if not answer:
                answer = "عذراً، المقتطفات المقدمة لا تحتوي على معلومات كافية."
                
            # Print the final LLM response using the Arabic helper
            print_arabic(f"\nالمساعد القانوني:\n{answer}\n")
            print("-" * 50)
            
        except KeyboardInterrupt:
            print_arabic("\nإغلاق النظام...")
            break
        except Exception as e:
            print(f"\n[خطأ]: {e}")

if __name__ == "__main__":
    main()