# Marker Installation Cheatsheet

## Προϋποθέσεις (Prerequisites)

- Python 3.10+
- PyTorch (CPU/GPU/MPS) - [Δείτε οδηγίες εγκατάστασης PyTorch](https://pytorch.org/get-started/locally/)

## Βασική Εγκατάσταση (Basic Installation)

Για μετατροπή μόνο PDF αρχείων:

```shell
pip install marker-pdf
```

## Πλήρης Εγκατάσταση (Full Installation)

Για υποστήριξη όλων των τύπων αρχείων (PDF, DOCX, PPTX, XLSX, HTML, EPUB):

```shell
pip install marker-pdf[full]
```
or for development mode:

```shell
pip install -e .[full]
```

## Εγκατάσταση για Διαδραστική Εφαρμογή (Interactive App)

```shell
pip install streamlit
marker_gui
```

## Εγκατάσταση για API Server

```shell
pip install -U uvicorn fastapi python-multipart
marker_server --port 8001
```

## Εγκατάσταση από Πηγαίο Κώδικα (Source Code)

Για benchmarks ή development:

```shell
git clone https://github.com/VikParuchuri/marker.git
poetry install
```

## Προαιρετικές Ρυθμίσεις Περιβάλλοντος (Optional Environment Settings)

- `TORCH_DEVICE=cuda` - Καθορισμός συσκευής για PyTorch
- `GOOGLE_API_KEY` - Απαιτείται όταν χρησιμοποιείτε τη σημαία `--use_llm` με το Gemini API

## Υποστηριζόμενες Πλατφόρμες (Supported Platforms)

- GPU (NVIDIA)
- CPU
- MPS (Mac)

## Απαιτήσεις Μνήμης (Memory Requirements)

- 5GB VRAM ανά worker στο peak
- 3.5GB VRAM ανά worker κατά μέσο όρο