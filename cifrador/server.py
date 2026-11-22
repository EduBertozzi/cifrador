"""Servidor local: recebe arquivo ou link, processa em fila e serve a interface."""

import json
import logging
import os
import shutil
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .shapes import shape_table

log = logging.getLogger("cifrador")

# a IA (PyTorch etc.) é pesada pra carregar: o site abre na hora e ela carrega em segundo plano
_pipeline = {}
_pipeline_ready = threading.Event()


def _load_pipeline() -> None:
    try:
        from . import pipeline
        from .recognizers import load_recognizers

        _pipeline["module"] = pipeline
        load_recognizers()
    except Exception:  # noqa: BLE001
        log.error(traceback.format_exc())
    finally:
        _pipeline_ready.set()
        print("  IA carregada, pode mandar a música.", flush=True)




def _start_loading() -> None:
    # espera a página abrir no navegador antes de começar a carregar a IA
    time.sleep(4)
    _load_pipeline()


ROOT = Path(__file__).resolve().parent
# o Cifrador.exe manda guardar as músicas fora da pasta do código
JOBS_DIR = Path(os.environ.get("CIFRADOR_MUSICAS", ROOT.parent / "musicas"))
JOBS_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Cifrador")


@app.on_event("startup")
def _startup() -> None:
    threading.Thread(target=_start_loading, daemon=True).start()

# modelos pesados: uma música por vez
executor = ThreadPoolExecutor(max_workers=1)
jobs: dict[str, dict] = {}
lock = threading.Lock()


def _set(job_id: str, **fields) -> None:
    with lock:
        jobs[job_id].update(fields)


def _run(job_id: str, upload: Path | None, url: str | None, quality: str, lyrics: bool) -> None:
    folder = JOBS_DIR / job_id
    try:
        if not _pipeline_ready.is_set():
            _set(job_id, status="running", stage="Carregando a IA (só na primeira música)", progress=0.01)
            _pipeline_ready.wait()
        pipeline = _pipeline.get("module")
        if pipeline is None:
            from . import pipeline
        options = pipeline.Options(quality=quality, lyrics=lyrics)
        _set(job_id, status="running", stage="Começando", progress=0.01)
        if url:
            _set(job_id, stage="Baixando do link", progress=0.02)
            from .audio import download_from_link

            upload = download_from_link(url, folder / "entrada")

        def report(stage: str, value: float) -> None:
            _set(job_id, stage=stage, progress=round(value, 3))

        result = pipeline.analyze(upload, folder, options, report)
        _set(job_id, status="done", result=result, title=result["title"])
    except Exception as error:  # noqa: BLE001
        log.error(traceback.format_exc())
        _set(job_id, status="error", error=str(error))


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.post("/api/jobs")
async def create_job(
    file: UploadFile | None = File(None),
    url: str = Form(""),
    quality: str = Form("rapido"),
    lyrics: bool = Form(True),
):
    url = url.strip()
    if file is None and not url:
        raise HTTPException(400, "Mande um arquivo de áudio ou um link.")

    job_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    folder = JOBS_DIR / job_id / "entrada"
    folder.mkdir(parents=True)

    upload_path = None
    title = url
    if file is not None and file.filename:
        suffix = Path(file.filename).suffix or ".audio"
        upload_path = folder / f"original{suffix}"
        with upload_path.open("wb") as target:
            shutil.copyfileobj(file.file, target)
        title = Path(file.filename).stem
        (folder / "title.txt").write_text(title, encoding="utf-8")
        url = ""

    with lock:
        jobs[job_id] = {"id": job_id, "status": "queued", "stage": "Na fila", "progress": 0.0, "title": title, "created": time.time()}
    executor.submit(_run, job_id, upload_path, url or None, quality, lyrics)
    return {"id": job_id}


@app.get("/api/jobs")
def list_jobs():
    """Músicas já analisadas (inclusive de outras sessões, lidas do disco)."""
    items = {}
    for folder in sorted(JOBS_DIR.iterdir(), reverse=True):
        result_file = folder / "result.json"
        if result_file.exists():
            title_file = folder / "entrada" / "title.txt"
            title = title_file.read_text(encoding="utf-8") if title_file.exists() else folder.name
            items[folder.name] = {"id": folder.name, "status": "done", "title": title}
    with lock:
        for job_id, job in jobs.items():
            if job["status"] != "done":
                items[job_id] = {k: job[k] for k in ("id", "status", "title", "stage", "progress")}
    return sorted(items.values(), key=lambda item: item["id"], reverse=True)[:30]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    with lock:
        job = jobs.get(job_id)
        if job is not None:
            return {k: v for k, v in job.items()}
    result_file = JOBS_DIR / job_id / "result.json"
    if result_file.exists():
        return {"id": job_id, "status": "done", "result": json.loads(result_file.read_text(encoding="utf-8"))}
    raise HTTPException(404, "Música não encontrada.")


@app.get("/api/jobs/{job_id}/audio")
def get_audio(job_id: str):
    path = JOBS_DIR / job_id / "audio.wav"
    if not path.exists():
        raise HTTPException(404, "Áudio não encontrado.")
    return FileResponse(path, media_type="audio/wav")


@app.get("/api/shapes")
def shapes():
    return shape_table()
