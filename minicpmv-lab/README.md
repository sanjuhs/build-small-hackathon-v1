# MiniCPM-V Lab

Local MiniCPM-V 4.6 playground for image chat, PDF transcription, and timing measurements.

## Requirements

- Ollama `0.30.0` or newer
- MiniCPM-V 4.6 GGUF pulled locally:

```bash
ollama pull hf.co/ggml-org/MiniCPM-V-4.6-GGUF:Q4_K_M
```

## Run

```bash
./minicpmv-lab/start.sh
```

Open:

```text
http://127.0.0.1:65446
```

The app runs fully locally against:

```text
http://127.0.0.1:11434/api/chat
```

## What It Measures

- wall-clock time to first streamed content token
- wall-clock total time
- Ollama `load_duration`
- Ollama `prompt_eval_duration`
- Ollama `eval_duration`
- prompt/eval token counts

For PDFs, timings are captured per page and for the whole document.

## Notes

MiniCPM-V can transcribe and describe handwriting, stamps, signatures, page numbers, and layout, but no OCR model can guarantee complete accuracy on all documents. The default prompt asks the model to mark uncertain text with `[unclear]` instead of inventing content.

