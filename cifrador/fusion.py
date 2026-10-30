"""Votação entre modelos, alinhada nas batidas, e decodificação final (Viterbi).

Como funciona:
1. A música é dividida em células de meia batida.
2. Cada modelo (em cada versão do áudio) vota no acorde que ouviu em cada célula,
   proporcional ao tempo que o acorde ocupa ali.
3. Votos "parciais": quem disse C7M também conta meio voto para C. Assim uma
   extensão (7M, 9, inversão) só aparece quando os modelos concordam nela.
4. O Viterbi escolhe a sequência mais provável, cobrando caro para trocar de
   acorde no contratempo e barato no tempo forte do compasso.
"""

from dataclasses import dataclass

import numpy as np

from .theory import Chord, Key, chord_from_key, parse_harte

NO_CHORD = "N"


@dataclass
class Vote:
    """Saída de um modelo numa versão do áudio, já na linha do tempo original."""

    source: str
    weight: float
    segments: list  # lista de (início, fim, rótulo Harte)


def related_keys(label: str) -> dict[str, float]:
    """Para onde vai o voto de um rótulo: ele mesmo (1.0) e versões mais simples (parcial)."""
    chord = parse_harte(label)
    if chord is None:
        return {NO_CHORD: 1.0}
    keys = {chord.key: 1.0}
    if chord.bass is not None:
        plain = Chord(chord.root, chord.family)
        keys[plain.key] = max(keys.get(plain.key, 0.0), 0.6)
    if chord.triad_key not in keys:
        keys[chord.triad_key] = 0.5
    return keys


def build_votes(votes: list[Vote], edges: np.ndarray) -> tuple[list[str], np.ndarray]:
    """Matriz [células x acordes] com a fração de voto de cada acorde em cada célula."""
    starts = edges[:-1]
    ends = edges[1:]
    lengths = np.maximum(ends - starts, 1e-6)

    vocabulary: dict[str, int] = {NO_CHORD: 0}

    for vote in votes:
        for seg_start, seg_end, label in vote.segments:
            for key in related_keys(label):
                if key not in vocabulary:
                    vocabulary[key] = len(vocabulary)

    matrix = np.zeros((len(starts), len(vocabulary)))
    coverage = np.zeros(len(starts))

    for vote in votes:
        for seg_start, seg_end, label in vote.segments:
            # células que esse segmento toca
            first = np.searchsorted(ends, seg_start, side="right")
            last = np.searchsorted(starts, seg_end, side="left")
            if last <= first:
                continue
            cell_index = np.arange(first, last)
            overlap = np.minimum(ends[cell_index], seg_end) - np.maximum(starts[cell_index], seg_start)
            overlap = np.clip(overlap, 0.0, None) / lengths[cell_index]
            for key, credit in related_keys(label).items():
                matrix[cell_index, vocabulary[key]] += vote.weight * credit * overlap
            coverage[cell_index] += vote.weight * overlap

    matrix = matrix / np.maximum(coverage, 1e-6)[:, None]
    keys = sorted(vocabulary, key=vocabulary.get)
    return keys, matrix


def key_bonus(keys: list[str], song_key: Key | None) -> np.ndarray:
    """Pequeno empurrão para acordes do campo harmônico (só desempata)."""
    bonus = np.zeros(len(keys))
    if song_key is None:
        return bonus
    diatonic = song_key.diatonic_chords()
    for index, key in enumerate(keys):
        chord = chord_from_key(key)
        if chord is not None and chord.triad_key in diatonic:
            bonus[index] = 0.06
    return bonus


def viterbi(emission: np.ndarray, change_cost: np.ndarray) -> np.ndarray:
    """Melhor caminho. change_cost[t] = custo de trocar de acorde ao entrar na célula t."""
    log_emission = np.log(emission + 0.02)
    cells, states = log_emission.shape
    score = log_emission[0].copy()
    back = np.zeros((cells, states), dtype=np.int32)

    for t in range(1, cells):
        best_prev = int(np.argmax(score))
        switch = score[best_prev] - change_cost[t]
        stay_better = score >= switch
        back[t] = np.where(stay_better, np.arange(states), best_prev)
        score = np.where(stay_better, score, switch) + log_emission[t]

    path = np.zeros(cells, dtype=np.int32)
    path[-1] = int(np.argmax(score))
    for t in range(cells - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return path


def change_costs(cell_owner: np.ndarray, downbeats: set[int] | None) -> np.ndarray:
    """Custo de troca por posição: tempo forte < batida < contratempo."""
    costs = np.zeros(len(cell_owner))
    for t in range(1, len(cell_owner)):
        on_beat = cell_owner[t] != cell_owner[t - 1]
        if not on_beat:
            costs[t] = 3.5
        elif downbeats is None:
            costs[t] = 1.8
        elif cell_owner[t] in downbeats:
            costs[t] = 1.1
        else:
            costs[t] = 2.3
    return costs


def decode(
    keys: list[str],
    matrix: np.ndarray,
    edges: np.ndarray,
    cell_owner: np.ndarray,
    song_key: Key | None = None,
    downbeats: set[int] | None = None,
) -> list[dict]:
    """Roda o Viterbi e junta as células em segmentos com confiança."""
    emission = matrix + key_bonus(keys, song_key)[None, :]
    path = viterbi(emission, change_costs(cell_owner, downbeats))

    segments = []
    start_cell = 0
    for t in range(1, len(path) + 1):
        if t < len(path) and path[t] == path[start_cell]:
            continue
        state = path[start_cell]
        confidence = float(matrix[start_cell:t, state].mean())
        segments.append({
            "start": float(edges[start_cell]),
            "end": float(edges[t]),
            "key": keys[state],
            "confidence": round(min(confidence, 1.0), 3),
            "first_beat": int(cell_owner[start_cell]),
            "on_beat": bool(start_cell == 0 or cell_owner[start_cell] != cell_owner[start_cell - 1]),
        })
        start_cell = t
    return segments


def chord_seconds(segments: list[dict]) -> dict[str, float]:
    """Quanto tempo cada acorde (sem o baixo) soa na música."""
    totals: dict[str, float] = {}
    for segment in segments:
        chord = chord_from_key(segment["key"])
        if chord is None:
            continue
        plain = Chord(chord.root, chord.family).key
        totals[plain] = totals.get(plain, 0.0) + segment["end"] - segment["start"]
    return totals
