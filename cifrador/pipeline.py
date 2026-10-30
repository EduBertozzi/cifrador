"""Junta tudo: áudio → stems → afinação → modelos → votação → tom → capo → letra."""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import librosa
import numpy as np

from . import audio, fusion, rhythm
from .recognizers import load_recognizers
from .shapes import rank_capos
from .theory import chord_from_key, estimate_key

log = logging.getLogger("cifrador")

# peso de cada versão do áudio na votação
SOURCE_WEIGHT = {"harmonico": 1.0, "mix": 0.9}


@dataclass
class Options:
    quality: str = "rapido"  # "rapido" ou "maximo"
    lyrics: bool = True
    separate: bool = True
    language: str | None = None


def analyze(
    input_path: Path,
    work_dir: Path,
    options: Options,
    progress: Callable[[str, float], None] = lambda stage, value: None,
) -> dict:
    started = time.time()
    # caminhos absolutos: o lv-chordia resolve caminho relativo a partir da pasta dele
    input_path = Path(input_path).resolve()
    work_dir = Path(work_dir).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)
    warnings = []

    # 1. converte para WAV
    progress("Preparando o áudio", 0.03)
    original = audio.to_wav(input_path, work_dir / "audio.wav")
    y_full, sr = librosa.load(str(original), sr=audio.ANALYSIS_SR, mono=True)
    duration = len(y_full) / sr

    # 2. separa os stems
    stems = {}
    if options.separate:
        progress("Separando instrumentos, voz e bateria", 0.08)
        try:
            from .separation import separate

            stems = separate(original, work_dir / "stems", options.quality)
        except Exception as error:  # noqa: BLE001
            log.exception("Falha na separação")
            warnings.append(f"Separação de stems falhou ({error}). Usei só a mixagem.")

    versions = {"mix": y_full}
    drums = None
    if stems:
        versions["harmonico"], _ = librosa.load(str(stems["harmonic"]), sr=sr, mono=True)
        drums, _ = librosa.load(str(stems["drums"]), sr=sr, mono=True)

    # 3. corrige a afinação (músicas fora do 440 Hz confundem os modelos)
    progress("Medindo a afinação", 0.35)
    reference = versions.get("harmonico", y_full)
    tuning = audio.estimate_tuning(reference, sr)
    tuned_paths = {}
    factor = 1.0
    tuned_audio = {}
    for name, y in versions.items():
        fixed, factor = audio.retune(y, sr, tuning)
        tuned_audio[name] = fixed
        tuned_paths[name] = audio.save_mono(work_dir / f"{name}_afinado.wav", fixed, sr)

    # 4. roda cada modelo em cada versão do áudio
    progress("Carregando os modelos de acorde", 0.4)
    models = load_recognizers()
    votes = []
    raw = {}
    steps = len(models) * len(tuned_paths)
    done = 0
    for model in models:
        for name, path in tuned_paths.items():
            done = done + 1
            progress(f"Ouvindo os acordes ({model.name}, {name})", 0.4 + 0.3 * done / steps)
            segments = model.predict(path)
            # volta para a linha do tempo original
            rescaled = [(s.start * factor, s.end * factor, s.label) for s in segments]
            source = f"{model.name}:{name}"
            raw[source] = rescaled
            votes.append(fusion.Vote(source, model.weight * SOURCE_WEIGHT[name], rescaled))

    # 5. batidas
    progress("Achando as batidas", 0.72)
    bpm, beats = rhythm.track_beats(y_full, sr, drums)
    grid = rhythm.fill_grid(beats, duration, bpm)
    edges, owner = rhythm.subdivide(grid)

    # 6. primeira votação, sem saber tom nem compasso
    progress("Votando entre os modelos", 0.76)
    keys, matrix = fusion.build_votes(votes, edges)
    first_pass = fusion.decode(keys, matrix, edges, owner)

    # 7. tonalidade (croma do áudio + acordes da primeira passada)
    chroma = librosa.feature.chroma_cqt(y=tuned_audio.get("harmonico", tuned_audio["mix"]), sr=sr, tuning=0.0)
    chroma_mean = chroma.mean(axis=1)
    song_key = estimate_key(chroma_mean, fusion.chord_seconds(first_pass))

    # 8. compasso: onde os acordes mais trocam é o tempo forte
    changes = [s["first_beat"] for s in first_pass[1:] if s["on_beat"]]
    meter, phase = rhythm.choose_meter(changes, len(grid) - 1)
    downbeats = set(range(phase, len(grid) - 1, meter))

    # 9. votação final com tom e compasso
    final = fusion.decode(keys, matrix, edges, owner, song_key, downbeats)
    seconds = fusion.chord_seconds(final)
    song_key = estimate_key(chroma_mean, seconds)

    # 10. capotraste
    progress("Escolhendo o capotraste", 0.82)
    capos = rank_capos(seconds)

    # 11. letra
    lyrics = None
    if options.lyrics and "vocals" in stems:
        progress("Transcrevendo a letra", 0.85)
        try:
            from .lyrics import transcribe

            lyrics = transcribe(stems["vocals"], options.language)
        except Exception as error:  # noqa: BLE001
            log.exception("Falha na letra")
            warnings.append(f"Não consegui transcrever a letra ({error}).")
    elif options.lyrics:
        warnings.append("Letra precisa da separação de stems ligada.")

    progress("Montando a cifra", 0.97)

    output_segments = []
    for segment in final:
        chord = chord_from_key(segment["key"])
        output_segments.append({
            "start": round(segment["start"], 3),
            "end": round(segment["end"], 3),
            "root": None if chord is None else chord.root,
            "family": None if chord is None else chord.family,
            "bass": None if chord is None else chord.bass,
            "confidence": segment["confidence"],
        })

    title_file = input_path.parent / "title.txt"
    title = title_file.read_text(encoding="utf-8") if title_file.exists() else input_path.stem

    result = {
        "title": title,
        "duration": round(duration, 3),
        "bpm": round(bpm, 1),
        "meter": meter,
        "beats": [round(float(t), 3) for t in grid],
        "downbeat_phase": phase,
        "tuning_cents": round(tuning * 100),
        "key": {"tonic": song_key.tonic, "mode": song_key.mode, "name": song_key.name(), "flats": song_key.uses_flats},
        "segments": output_segments,
        "capos": capos,
        "models": [v.source for v in votes],
        "lyrics": lyrics,
        "warnings": warnings,
        "seconds_taken": round(time.time() - started, 1),
    }
    (work_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    (work_dir / "raw_models.json").write_text(json.dumps(raw), encoding="utf-8")
    progress("Pronto", 1.0)
    return result
