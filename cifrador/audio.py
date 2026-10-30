"""Entrada de áudio: download por link, conversão e correção de afinação."""

import shutil
import subprocess
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

# taxa usada pelos modelos de acorde
ANALYSIS_SR = 22050


def download_from_link(url: str, folder: Path) -> Path:
    """Baixa o áudio de YouTube, SoundCloud etc. usando o yt-dlp."""
    import yt_dlp

    folder.mkdir(parents=True, exist_ok=True)
    options = {
        "format": "bestaudio/best",
        "outtmpl": str(folder / "original.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
    }
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=True)
    title = info.get("title") or "Música"
    path = folder / "original.wav"
    (folder / "title.txt").write_text(title, encoding="utf-8")
    return path


def to_wav(source: Path, target: Path) -> Path:
    """Converte qualquer formato para WAV 44.1 kHz estéreo (precisa do ffmpeg)."""
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg não encontrado. Instale e tente de novo (veja o README).")
    command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(source),
        "-ac", "2",
        "-ar", "44100",
        str(target),
    ]
    subprocess.run(command, check=True)
    return target


def estimate_tuning(y: np.ndarray, sr: int) -> float:
    """Desvio da afinação em semitons (ex.: -0.18 = 18 cents abaixo do A440)."""
    harmonic = librosa.effects.harmonic(y)
    # com 12 bins por oitava o resultado já vem em fração de semitom (-0.5 a 0.5)
    return float(librosa.estimate_tuning(y=harmonic, sr=sr, bins_per_octave=12))


def retune(y: np.ndarray, sr: int, tuning: float) -> tuple[np.ndarray, float]:
    """Corrige a afinação por reamostragem (sem artefato de phase vocoder).

    Devolve o áudio corrigido e o fator de tempo: tempo_original = tempo_corrigido * fator.
    Isso importa porque músicas gravadas fora do 440 Hz confundem os modelos.
    """
    if abs(tuning) < 0.08:
        return y, 1.0
    factor = 2.0 ** (-tuning / 12.0)
    fixed = librosa.resample(y, orig_sr=sr * factor, target_sr=sr, res_type="soxr_hq")
    return fixed, factor


def save_mono(path: Path, y: np.ndarray, sr: int) -> Path:
    sf.write(str(path), y.astype(np.float32), sr)
    return path
