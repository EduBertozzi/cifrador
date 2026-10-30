"""Separação de stems com Demucs (bateria, baixo, voz, resto).

A versão harmônica (baixo + instrumentos, sem voz e sem bateria) deixa os
modelos de acorde bem mais precisos. A bateria serve para achar as batidas
e a voz serve para transcrever a letra.
"""

from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import torch

# "rapido" usa o htdemucs; "maximo" usa o htdemucs_ft (4 modelos, ~4x mais lento, mais limpo)
MODELS = {"rapido": "htdemucs", "maximo": "htdemucs_ft"}


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def separate(wav_path: Path, out_dir: Path, quality: str = "rapido", device: str | None = None) -> dict[str, Path]:
    """Gera stems em out_dir e devolve {'drums': ..., 'bass': ..., 'other': ..., 'vocals': ..., 'harmonic': ...}."""
    # demucs-infer = Demucs oficial empacotado para PyTorch 2.x (mesmos pesos)
    try:
        from demucs_infer.apply import apply_model
        from demucs_infer.pretrained import get_model
    except ImportError:
        from demucs.apply import apply_model
        from demucs.pretrained import get_model

    device = device or pick_device()
    model = get_model(MODELS.get(quality, "htdemucs"))
    model.eval()

    # carrega estéreo na taxa do modelo
    audio, _ = librosa.load(str(wav_path), sr=model.samplerate, mono=False)
    if audio.ndim == 1:
        audio = np.stack([audio, audio])
    wav = torch.from_numpy(audio).float()

    # mesma normalização do "demucs" de linha de comando
    reference = wav.mean(0)
    mean = reference.mean()
    std = reference.std() + 1e-8
    wav = (wav - mean) / std

    with torch.no_grad():
        sources = apply_model(
            model,
            wav[None],
            device=device,
            shifts=1 if quality == "rapido" else 2,
            split=True,
            overlap=0.25,
            progress=False,
        )[0]
    sources = sources * std + mean

    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    stems = {}
    for name, source in zip(model.sources, sources):
        data = source.cpu().numpy().T
        stems[name] = data
        path = out_dir / f"{name}.wav"
        sf.write(str(path), data, model.samplerate)
        paths[name] = path

    # harmônico = tudo que tem nota, menos voz (melodia confunde o acorde)
    harmonic = np.zeros_like(stems["bass"])
    for name, data in stems.items():
        if name not in ("drums", "vocals"):
            harmonic = harmonic + data
    path = out_dir / "harmonic.wav"
    sf.write(str(path), harmonic, model.samplerate)
    paths["harmonic"] = path

    # libera a memória da GPU antes dos próximos modelos
    del model
    if device.startswith("cuda"):
        torch.cuda.empty_cache()
    return paths
