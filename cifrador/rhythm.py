"""Batidas, andamento e compassos."""

import librosa
import numpy as np


def track_beats(y: np.ndarray, sr: int, drums: np.ndarray | None = None) -> tuple[float, np.ndarray]:
    """Devolve (bpm, tempos das batidas em segundos).

    Se tiver o stem de bateria, usa ele: as batidas ficam bem mais firmes.
    """
    if drums is not None and np.abs(drums).mean() > 1e-3:
        source = drums
    else:
        source = librosa.effects.percussive(y)

    onset = librosa.onset.onset_strength(y=source, sr=sr, aggregate=np.median)
    tempo, frames = librosa.beat.beat_track(onset_envelope=onset, sr=sr, tightness=120, units="frames")
    beats = librosa.frames_to_time(frames, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])
    return bpm, beats


def fill_grid(beats: np.ndarray, duration: float, bpm: float) -> np.ndarray:
    """Completa a grade de batidas do início ao fim da música (intro e final sem bateria)."""
    if len(beats) >= 2:
        period = float(np.median(np.diff(beats)))
    else:
        period = 60.0 / max(bpm, 40.0)
        beats = np.array([0.0])

    grid = list(beats)

    # para trás, até o zero
    first = grid[0]
    while first - period > -period * 0.5:
        first = first - period
        grid.insert(0, max(first, 0.0))

    # para frente, até o fim
    last = grid[-1]
    while last + period < duration:
        last = last + period
        grid.append(last)

    grid = np.array(sorted(set(round(t, 4) for t in grid)))

    # batida colada no zero vira o próprio zero (sem célula minúscula)
    if grid[0] < 0.35 * period:
        grid[0] = 0.0
    else:
        grid = np.insert(grid, 0, 0.0)

    # mesma coisa no final
    if duration - grid[-1] < 0.35 * period:
        grid[-1] = duration
    else:
        grid = np.append(grid, duration)
    return grid


def subdivide(grid: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Divide cada batida em duas metades. Devolve (bordas das células, índice da batida de cada célula)."""
    edges = []
    owner = []
    for index in range(len(grid) - 1):
        start = grid[index]
        middle = (grid[index] + grid[index + 1]) / 2
        edges.append(start)
        owner.append(index)
        edges.append(middle)
        owner.append(index)
    edges.append(grid[-1])
    return np.array(edges), np.array(owner)


def choose_meter(change_beats: list[int], total_beats: int) -> tuple[int, int]:
    """Escolhe compasso (3 ou 4) e qual batida é o "1", vendo onde os acordes mais trocam.

    Na música popular os acordes trocam quase sempre no tempo forte.
    """
    if not change_beats:
        return 4, 0

    best = (4, 0)
    best_score = -1.0
    for meter in (4, 3):
        for phase in range(meter):
            hits = sum(1 for beat in change_beats if (beat - phase) % meter == 0)
            score = hits / len(change_beats)
            # 4/4 é bem mais comum: só troca para 3/4 se for claramente melhor
            if meter == 3:
                score = score - 0.12
            if score > best_score:
                best_score = score
                best = (meter, phase)
    return best
