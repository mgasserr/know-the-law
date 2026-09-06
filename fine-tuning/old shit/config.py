"""
Centralized configuration for the Arabic legal-domain Qwen2.5-7B-Instruct
fine-tuning pipeline.

Every script imports from here. Nothing training/OCR-related should be
hard-coded elsewhere.
"""

import os
from dataclasses import dataclass, field
from typing import List


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

PDF_DIR = os.path.join(ROOT_DIR, "..", "data")
OCR_DIR = os.path.join(ROOT_DIR, "data", "ocr")            # raw per-page OCR jsonl
PROCESSED_DIR = os.path.join(ROOT_DIR, "data", "processed")  # cleaned/structured corpus
SFT_DIR = os.path.join(ROOT_DIR, "data", "sft")             # final train/val jsonl
MODELS_DIR = os.path.join(ROOT_DIR, "models")
SFT_OUTPUT_DIR = os.path.join(MODELS_DIR, "sft")
LOG_DIR = os.path.join(ROOT_DIR, "logs")

for d in [PDF_DIR, OCR_DIR, PROCESSED_DIR, SFT_DIR, SFT_OUTPUT_DIR, LOG_DIR]:
    os.makedirs(d, exist_ok=True)


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
BASE_MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"
SEED = 42


# --------------------------------------------------------------------------
# OCR settings
# --------------------------------------------------------------------------
@dataclass
class OCRConfig:
    render_dpi: int = 300              # good balance of accuracy vs. speed/VRAM for scanned books
    lang: str = "ar"                   # PaddleOCR Arabic model
    use_gpu: bool = True               # OCR on GPU is fine, it's cheap; done once, not repeated
    use_structure: bool = False         # PP-Structure layout analysis (tables, columns, headings)
    min_chars_per_page: int = 20       # pages below this are flagged as "empty/failed"
    max_workers: int = 1               # PaddleOCR GPU context isn't safely multi-processed


OCR_CFG = OCRConfig()


# --------------------------------------------------------------------------
# Cleaning / quality-control thresholds
# --------------------------------------------------------------------------
@dataclass
class QualityConfig:
    min_page_chars: int = 40
    min_arabic_char_ratio: float = 0.55   # (arabic chars) / (all letters) on the page
    max_repeated_char_run: int = 8        # e.g. "،،،،،،،،" garbage runs
    max_punct_ratio: float = 0.35
    near_dup_similarity: float = 0.92     # difflib ratio threshold for near-duplicate pages
    min_fragment_chars: int = 15          # discard structural fragments shorter than this


QUALITY_CFG = QualityConfig()


# --------------------------------------------------------------------------
# LoRA / QLoRA (SFT)
# --------------------------------------------------------------------------
@dataclass
class LoRAConfig:
    r: int = 16
    alpha: int = 32
    dropout: float = 0.05
    bias: str = "none"
    task_type: str = "CAUSAL_LM"
    # Attention-only (q/k/v/o) is not enough for genuine domain-vocabulary/style
    # adaptation; MLP projections carry most of the "knowledge" capacity in
    # transformer blocks, so we include them too, at a modest rank to keep
    # VRAM and overfitting risk in check on a 3-document corpus.
    target_modules: List[str] = field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]
    )


LORA_CFG = LoRAConfig()


# --------------------------------------------------------------------------
# Training (single-stage SFT / domain-adaptation)
# --------------------------------------------------------------------------
@dataclass
class TrainConfig:
    # VRAM-sensitive - tuned for an 8GB RTX 5060. Lower these first if you OOM.
    max_seq_length: int = 400
    per_device_train_batch_size: int = 1
    per_device_eval_batch_size: int = 1
    gradient_accumulation_steps: int = 16     # effective batch size = 16
    gradient_checkpointing: bool = True

    learning_rate: float = 1.5e-4
    lr_scheduler_type: str = "cosine"
    warmup_ratio: float = 0.03
    weight_decay: float = 0.0
    num_train_epochs: float = 1.0        # was 3.0 — less phrasing-memorization risk
    max_grad_norm: float = 0.3

    optim: str = "adamw_8bit"
    bf16: bool = True                         # RTX 50-series (Blackwell) supports bf16 natively
    fp16: bool = False

    eval_strategy: str = "steps"
    eval_steps: int = 5
    save_strategy: str = "steps"
    save_steps: int = 25
    save_total_limit: int = 3
    load_best_model_at_end: bool = True
    metric_for_best_model: str = "eval_loss"
    greater_is_better: bool = False
    logging_steps: int = 5

    val_split_ratio: float = 0.1
    packing: bool = False   # packing complicates assistant-only loss masking; skip on a small dataset

    # 4-bit QLoRA quantization
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True
    bnb_4bit_compute_dtype: str = "bfloat16"


TRAIN_CFG = TrainConfig()


# --------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------
@dataclass
class InferenceConfig:
    max_new_tokens: int = 512
    temperature: float = 0.3
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    system_prompt: str = (
        "أنت مساعد قانوني متخصص في القانون. أجب بدقة استنادًا إلى المعرفة القانونية "
        "التي تم تدريبك عليها، واذكر رقم المادة عند الإمكان."
    )


INFER_CFG = InferenceConfig()
