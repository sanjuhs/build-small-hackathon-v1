from __future__ import annotations

import asyncio
import base64
import json
import os
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, AsyncIterator

import fitz
import httpx
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
OLLAMA_URL = os.getenv("MINICPMV_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("MINICPMV_MODEL", "hf.co/ggml-org/MiniCPM-V-4.6-GGUF:Q4_K_M")
PORT = int(os.getenv("MINICPMV_PORT", "65446"))

app = FastAPI(title="MiniCPM-V Lab")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@dataclass
class StreamStats:
    started: float
    first_token: float | None = None
    content: list[str] | None = None
    ollama_done: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.content is None:
            self.content = []

    def note_token(self, text: str) -> None:
        if self.first_token is None:
            self.first_token = time.perf_counter()
        self.content.append(text)

    def summary(self) -> dict[str, Any]:
        ended = time.perf_counter()
        total_text = "".join(self.content or [])
        done = self.ollama_done or {}
        return {
            "ttftMs": elapsed_ms(self.started, self.first_token) if self.first_token else None,
            "totalMs": elapsed_ms(self.started, ended),
            "chars": len(total_text),
            "promptEvalCount": done.get("prompt_eval_count"),
            "evalCount": done.get("eval_count"),
            "loadMs": ns_to_ms(done.get("load_duration")),
            "promptEvalMs": ns_to_ms(done.get("prompt_eval_duration")),
            "evalMs": ns_to_ms(done.get("eval_duration")),
            "ollamaTotalMs": ns_to_ms(done.get("total_duration")),
            "doneReason": done.get("done_reason"),
        }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/status")
async def status() -> JSONResponse:
    async with httpx.AsyncClient(timeout=5) as client:
        version = await safe_get_json(client, f"{OLLAMA_URL}/api/version")
        tags = await safe_get_json(client, f"{OLLAMA_URL}/api/tags")
        ps = await safe_get_json(client, f"{OLLAMA_URL}/api/ps")
    return JSONResponse({
        "ollamaUrl": OLLAMA_URL,
        "defaultModel": DEFAULT_MODEL,
        "version": version,
        "tags": tags,
        "ps": ps,
    })


@app.post("/api/chat")
async def chat(
    message: str = Form("Describe this image in detail."),
    model: str = Form(DEFAULT_MODEL),
    temperature: float = Form(0.1),
    max_tokens: int = Form(700),
    image: UploadFile | None = File(None),
) -> StreamingResponse:
    image_b64 = await upload_to_base64(image) if image else None
    messages = [{"role": "user", "content": message.strip() or "Describe this image."}]
    if image_b64:
        messages[0]["images"] = [image_b64]
    payload = ollama_payload(model, messages, temperature=temperature, max_tokens=max_tokens)
    return ndjson_response(stream_ollama(payload, request_type="chat"))


@app.post("/api/pdf")
async def pdf(
    file: UploadFile = File(...),
    model: str = Form(DEFAULT_MODEL),
    prompt: str = Form(""),
    dpi: int = Form(144),
    max_pages: int = Form(10),
    temperature: float = Form(0.0),
    max_tokens: int = Form(1400),
) -> StreamingResponse:
    pdf_bytes = await file.read()
    return ndjson_response(
        stream_pdf_transcription(
            pdf_bytes=pdf_bytes,
            filename=file.filename or "document.pdf",
            model=model,
            prompt=prompt,
            dpi=max(72, min(int(dpi), 220)),
            max_pages=max(1, min(int(max_pages), 50)),
            temperature=temperature,
            max_tokens=max(200, min(int(max_tokens), 4096)),
        )
    )


async def stream_pdf_transcription(
    *,
    pdf_bytes: bytes,
    filename: str,
    model: str,
    prompt: str,
    dpi: int,
    max_pages: int,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[dict[str, Any]]:
    started = time.perf_counter()
    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        yield {"type": "error", "message": f"Could not open PDF: {exc}"}
        return

    page_count = min(document.page_count, max_pages)
    yield {
        "type": "pdf_start",
        "filename": filename,
        "pagesTotal": document.page_count,
        "pagesPlanned": page_count,
        "dpi": dpi,
        "model": model,
    }

    full_text: list[str] = []
    page_stats: list[dict[str, Any]] = []
    for page_index in range(page_count):
        render_start = time.perf_counter()
        try:
            image = render_pdf_page(document, page_index, dpi=dpi)
        except Exception as exc:
            yield {"type": "page_error", "page": page_index + 1, "message": str(exc)}
            continue

        render_ms = elapsed_ms(render_start, time.perf_counter())
        preview_url = data_url_from_bytes(image["previewBytes"], "image/jpeg")
        yield {
            "type": "page_start",
            "page": page_index + 1,
            "width": image["width"],
            "height": image["height"],
            "preview": preview_url,
            "renderMs": render_ms,
        }

        page_prompt = ocr_prompt(prompt, page_index + 1, document.page_count)
        messages = [{"role": "user", "content": page_prompt, "images": [image["modelB64"]]}]
        payload = ollama_payload(model, messages, temperature=temperature, max_tokens=max_tokens)
        text_parts: list[str] = []
        async for event in stream_ollama(payload, request_type="pdf_page", page=page_index + 1):
            if event.get("type") == "token":
                text_parts.append(event.get("text", ""))
            yield event
        page_text = "".join(text_parts).strip()
        full_text.append(f"\n\n--- Page {page_index + 1} ---\n{page_text}")
        stats = {"page": page_index + 1, "chars": len(page_text), "renderMs": render_ms}
        page_stats.append(stats)
        yield {"type": "page_done", "page": page_index + 1, "text": page_text, "stats": stats}

    yield {
        "type": "pdf_done",
        "totalMs": elapsed_ms(started, time.perf_counter()),
        "pages": page_stats,
        "text": "".join(full_text).strip(),
    }


async def stream_ollama(
    payload: dict[str, Any],
    *,
    request_type: str,
    page: int | None = None,
) -> AsyncIterator[dict[str, Any]]:
    stats = StreamStats(started=time.perf_counter())
    meta = {"type": "start", "requestType": request_type, "model": payload.get("model")}
    if page is not None:
        meta["page"] = page
    yield meta

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    text = (data.get("message") or {}).get("content") or ""
                    if text:
                        stats.note_token(text)
                        event = {
                            "type": "token",
                            "text": text,
                            "ttftMs": elapsed_ms(stats.started, stats.first_token),
                            "elapsedMs": elapsed_ms(stats.started, time.perf_counter()),
                        }
                        if page is not None:
                            event["page"] = page
                        yield event
                    if data.get("done"):
                        stats.ollama_done = data
                        done = {"type": "done", "stats": stats.summary()}
                        if page is not None:
                            done["page"] = page
                        yield done
                        return
    except Exception as exc:
        yield {"type": "error", "message": str(exc), "page": page}


def ollama_payload(
    model: str,
    messages: list[dict[str, Any]],
    *,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    return {
        "model": model or DEFAULT_MODEL,
        "messages": messages,
        "think": False,
        "stream": True,
        "keep_alive": "10m",
        "options": {
            "temperature": float(temperature),
            "num_predict": int(max_tokens),
            "num_ctx": int(os.getenv("MINICPMV_NUM_CTX", "4096")),
        },
    }


def ocr_prompt(custom: str, page: int, total_pages: int) -> str:
    base = custom.strip() or (
        "You are a meticulous local OCR and document transcription engine. "
        "Transcribe every visible detail on this page in natural reading order. "
        "Include printed text, handwriting, stamps, signatures, dates, page numbers, "
        "checkboxes, table cells, marginal notes, headers, footers, and visible marks. "
        "Preserve line breaks where helpful. Do not summarize. "
        "If text is uncertain, write [unclear] instead of inventing it."
    )
    return f"{base}\n\nThis is page {page} of {total_pages}. Start with a heading: Page {page}."


def render_pdf_page(document: fitz.Document, page_index: int, *, dpi: int) -> dict[str, Any]:
    page = document.load_page(page_index)
    scale = dpi / 72
    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    image = Image.open(BytesIO(pixmap.tobytes("png"))).convert("RGB")
    model_image = contain_image(image, max_side=1800)
    preview_image = contain_image(image, max_side=1000)
    model_bytes = image_to_jpeg_bytes(model_image, quality=88)
    preview_bytes = image_to_jpeg_bytes(preview_image, quality=78)
    return {
        "width": model_image.width,
        "height": model_image.height,
        "modelB64": base64.b64encode(model_bytes).decode("ascii"),
        "previewBytes": preview_bytes,
    }


def contain_image(image: Image.Image, *, max_side: int) -> Image.Image:
    clone = image.copy()
    clone.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return clone


def image_to_jpeg_bytes(image: Image.Image, *, quality: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


async def upload_to_base64(upload: UploadFile) -> str:
    data = await upload.read()
    return base64.b64encode(data).decode("ascii")


def data_url_from_bytes(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def ndjson_response(events: AsyncIterator[dict[str, Any]]) -> StreamingResponse:
    async def body() -> AsyncIterator[bytes]:
        async for event in events:
            yield (json.dumps(event, ensure_ascii=True, separators=(",", ":")) + "\n").encode("utf-8")
            await asyncio.sleep(0)

    return StreamingResponse(body(), media_type="application/x-ndjson")


async def safe_get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def elapsed_ms(start: float, end: float | None) -> int | None:
    if end is None:
        return None
    return int(round((end - start) * 1000))


def ns_to_ms(value: Any) -> int | None:
    try:
        return int(round(float(value) / 1_000_000))
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=PORT, reload=False)

