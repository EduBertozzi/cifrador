"""Letra com tempo de cada palavra (faster-whisper rodando no stem de voz)."""

from pathlib import Path

import librosa
import numpy as np
import torch

_MODEL = None


def transcribe(vocals_path: Path, language: str | None = None) -> dict:
    """Devolve {'language': 'pt', 'lines': [{'start', 'end', 'words': [{'text', 'start', 'end'}]}]}."""
    global _MODEL
    from faster_whisper import WhisperModel

    if _MODEL is None:
        if torch.cuda.is_available():
            try:
                # GTX 10xx não tem float16 rápido, int8 vai melhor
                _MODEL = WhisperModel("medium", device="cuda", compute_type="int8_float32")
            except Exception:  # noqa: BLE001
                _MODEL = None
        if _MODEL is None:
            _MODEL = WhisperModel("small", device="cpu", compute_type="int8")

    try:
        lines, language = _run(_MODEL, vocals_path, language)
    except Exception:  # noqa: BLE001
        # sem cuDNN na máquina: cai para a CPU
        _MODEL = WhisperModel("small", device="cpu", compute_type="int8")
        lines, language = _run(_MODEL, vocals_path, language)
    return {"language": language, "lines": lines}


def _run(model, vocals_path: Path, language: str | None) -> tuple[list, str]:
    # carrega o áudio aqui (16 kHz mono) em vez de deixar o Whisper abrir o arquivo:
    # versões novas do PyAV quebram o leitor interno dele
    audio, _ = librosa.load(str(vocals_path), sr=16000, mono=True)
    segments, info = model.transcribe(
        audio.astype(np.float32),
        language=language,
        word_timestamps=True,
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,
    )
    lines = []
    for segment in segments:
        words = []
        for word in segment.words or []:
            text = word.word.strip()
            if not text:
                continue
            words.append({"text": text, "start": round(word.start, 3), "end": round(word.end, 3)})
        if words:
            lines.append({"start": words[0]["start"], "end": words[-1]["end"], "words": words})
    return lines, info.language
