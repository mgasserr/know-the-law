# اعرف القانون (Know the Law)

An Egyptian legal assistant: a RAG-powered FastAPI backend (Qwen2.5-7B-Instruct +
ChromaDB, grounded in 3 Egyptian legal PDFs) with a React chat frontend, plus an
optional QLoRA fine-tuning pipeline.

This guide assumes **zero prior setup** on your machine. Follow it top to bottom.

---

## 0. Project structure

```
know-the-law/
├── requirements.txt        <- Python deps for BOTH rag/ and fine-tuning/
├── data/                   <- the 3 legal PDFs (already provided)
│   ├── qanoon el madany summarized.pdf
│   ├── mo5tarat mn a7kam el naqd.pdf
│   └── mabade2 qanoneya sadera 3n ma7kamet el naqd.pdf
├── rag/
│   └── RAG.py              <- FastAPI backend
├── frontend/                <- React + Vite chat UI
│   ├── package.json
│   └── src/App.jsx
└── fine-tuning/             <- optional QLoRA training pipeline
    ├── data_prep.py
    ├── train_qlora.py
    ├── inference_test.py
    └── merge_lora.py
```

---

## 1. Install everything you need on your machine (one-time)

Do all of this **before** touching the project folder. Skip anything you can
already confirm is installed (check with the verification command shown).

### 1.1 An NVIDIA GPU driver

You need an NVIDIA GPU with at least 8GB VRAM. If your card is an RTX 50-series
(5060/5070/5080/5090 — "Blackwell"), you specifically need a **recent driver**
that supports CUDA 12.8+.

1. Download the latest driver for your card from
   [nvidia.com/drivers](https://www.nvidia.com/Download/index.aspx) and install it.
2. Reboot.
3. Verify: open PowerShell and run:
   ```powershell
   nvidia-smi
   ```
   You should see your GPU listed with a driver version and a CUDA version
   number in the top-right of the table. You do **not** need to separately
   install the "CUDA Toolkit" — PyTorch ships its own CUDA runtime.

### 1.2 Python 3.11 or 3.12

Some libraries used here (`peft`, `trl`) require **Python 3.10 or newer**.
3.11 or 3.12 is the safest choice for compatibility with everything else in
this stack as of today.

1. Download from [python.org/downloads](https://www.python.org/downloads/)
   (get 3.11.x or 3.12.x — **not** 3.13+, some ML packages lag behind on
   brand-new Python versions).
2. During install, **check the box "Add python.exe to PATH"** — this is the
   #1 most common setup mistake.
3. Verify:
   ```powershell
   python --version
   ```
   Should print `Python 3.11.x` or `3.12.x`.

### 1.3 Node.js (for the frontend)

The frontend uses Vite 8, which requires **Node.js 20.19+ or 22.12+**.

1. Download the **LTS** version from [nodejs.org](https://nodejs.org/) (as of
   now this is Node 22.x — that satisfies the requirement).
2. Verify:
   ```powershell
   node --version
   npm --version
   ```
   Should show `v22.x.x` (or at least `v20.19+`) and an `npm` version.

### 1.4 (Optional) Git

Only needed if you're cloning from GitHub instead of downloading a zip.
Get it from [git-scm.com](https://git-scm.com/downloads).

### 1.5 Windows PowerShell script permissions

Windows blocks running the virtual environment's activation script by
default. Fix this once, in an **Administrator PowerShell window**:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Type `Y` if prompted. You only need to do this once per machine.

---

## 2. Get the project onto your machine

**Option A — Git:**
```powershell
git clone https://github.com/<your-username>/know-the-law.git
cd know-the-law
```

**Option B — Zip:** download/extract the zip, then open PowerShell inside the
extracted `know-the-law` folder.

Make sure `requirements.txt` sits at the project root (`know-the-law/requirements.txt`),
alongside `data/`, `rag/`, `frontend/`, and `fine-tuning/` — not inside one of
the subfolders.

---

## 3. Set up the Python environment (used by both `rag/` and `fine-tuning/`)

Run these from the **project root** (`know-the-law/`):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Your prompt should now start with `(.venv)`. **Every time you open a new
terminal to work on this project, re-run the activate line above first.**

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This will download several GB (PyTorch with CUDA support, transformers,
bitsandbytes, langchain, chromadb, etc.) — it can take a while depending on
your internet connection. Make sure you have **at least 15GB of free disk
space** just for these packages.

**Verify PyTorch sees your GPU:**
```powershell
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```
This must print `True` and your GPU's name. If it prints `False`, stop here
and recheck step 1.1 — nothing downstream will work correctly otherwise.

---

## 4. Run the backend

Still inside the activated `.venv`:

```powershell
cd rag
uvicorn RAG:app --reload
```

**The first time you run this**, it will download the two AI models it needs
straight from Hugging Face:
- `Qwen/Qwen2.5-7B-Instruct` (~15GB)
- `BAAI/bge-m3` (~2GB)

This requires a stable internet connection and can take a long time
depending on your connection speed. It also builds a local vector index
(ChromaDB) from the 3 PDFs on first run — subsequent runs skip this and
start much faster.

You'll know it's ready when you see in the terminal:
```
[+] RAG Chain successfully compiled and active.
INFO:     Application startup complete.
```

Leave this terminal running. The backend is now live at `http://127.0.0.1:8000`.

---

## 5. Run the frontend

Open a **second** terminal (leave the backend running in the first one).
No need to activate the Python venv here — this is a separate Node.js project.

```powershell
cd know-the-law\frontend
npm install
npm run dev
```

`npm install` reads `package.json` and installs React, `lucide-react`, Vite,
etc. automatically. Once it finishes, `npm run dev` prints a local URL —
usually:

```
Local:   http://localhost:5173/
```

Open that URL in your browser. You should see the "اعرف القانون" interface
with a green "متصل بالخادم" status dot, confirming it can reach the backend.

---

## 6. Using it day-to-day (after the one-time setup above)

Every time you want to work on this project again, you only need:

**Terminal 1 (backend):**
```powershell
cd know-the-law
.venv\Scripts\Activate.ps1
cd rag
uvicorn RAG:app --reload
```

**Terminal 2 (frontend):**
```powershell
cd know-the-law\frontend
npm run dev
```

(You don't need to repeat `pip install` / `npm install` unless dependencies
change.)

---

## 7. (Optional) Fine-tuning

The `fine-tuning/` folder trains a QLoRA adapter on the same 3 PDFs. It uses
the same `.venv` you already set up in step 3 — no separate installation.

```powershell
cd know-the-law
.venv\Scripts\Activate.ps1
cd fine-tuning
python data_prep.py
python train_qlora.py
python inference_test.py
```

This is optional and unrelated to getting the chatbot running — see
`fine-tuning/README.md` for details, VRAM tuning knobs, and what each script
does.

---

## 8. Troubleshooting

**`Error loading ASGI app. Could not import module "main"` (or similar)**
The filename after `uvicorn` must match the actual `.py` filename (without
`.py`), and the FastAPI variable name after the colon must match what's
inside that file (`app = FastAPI(...)`). For this project: `uvicorn RAG:app --reload`,
run from inside the `rag/` folder.

**`CUDA out of memory`**
1. Run `nvidia-smi` and check the process list at the bottom. If a leftover
   Python process from a previous run is already holding several GB of VRAM,
   kill it: `taskkill /F /PID <pid>`.
2. Make sure nothing else GPU-heavy is running (games, other training jobs).
3. If it's genuinely tight even on a clean GPU, that's expected on an 8GB
   card running a 7B model — see the tuning notes in `fine-tuning/README.md`.

**`torch.cuda.is_available()` prints `False`**
Your PyTorch build doesn't match your GPU/driver. Reinstall torch specifically:
```powershell
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cu128
```

**PowerShell says running scripts is disabled**
Run step 1.5 above (`Set-ExecutionPolicy`) in an Administrator PowerShell window.

**`npm install` fails or the frontend won't start**
Check `node --version` — must be 20.19+ or 22.12+. Older Node versions are
silently incompatible with Vite 8 and produce confusing errors.

**Frontend shows "غير متصل بالخادم" (not connected)**
The backend either isn't running, is still starting up (model loading can
take a minute), or crashed — check Terminal 1 for errors.

**Warning: `Both max_new_tokens and max_length seem to have been set...`**
Harmless. It's just Transformers telling you it resolved a config conflict
in `max_new_tokens`'s favor, which is what you want. Not an error.

---

## 9. Requirements summary (for reference)

| Component        | Minimum version                    |
|-------------------|-------------------------------------|
| Python             | 3.10 (3.11/3.12 recommended)        |
| Node.js            | 20.19+ or 22.12+                    |
| NVIDIA driver      | supports CUDA 12.8+ (for RTX 50-series) |
| GPU VRAM           | 8GB (tight for a 7B model — see fine-tuning/README.md) |
| Free disk space    | ~20-30GB (models + dependencies)    |
| Internet           | required for first run (model downloads) |