"""Biblioteca de formas de acorde no violão e o otimizador de capotraste.

Cada forma é uma lista de 6 casas, da 6ª corda (Mi grave) para a 1ª (Mi agudo).
None = corda abafada, 0 = corda solta.
"""

from functools import lru_cache

from .theory import FAMILY_INTERVALS, Chord, chord_from_key

# afinação padrão, da 6ª para a 1ª corda (Mi Lá Ré Sol Si Mi)
TUNING = [4, 9, 2, 7, 11, 4]

# formas abertas clássicas: (nota da raiz, casas)
OPEN_SHAPES = {
    "maj": [
        (0, [None, 3, 2, 0, 1, 0]),
        (9, [None, 0, 2, 2, 2, 0]),
        (7, [3, 2, 0, 0, 0, 3]),
        (4, [0, 2, 2, 1, 0, 0]),
        (2, [None, None, 0, 2, 3, 2]),
        (5, [None, None, 3, 2, 1, 1]),
    ],
    "min": [
        (9, [None, 0, 2, 2, 1, 0]),
        (4, [0, 2, 2, 0, 0, 0]),
        (2, [None, None, 0, 2, 3, 1]),
    ],
    "7": [
        (0, [None, 3, 2, 3, 1, 0]),
        (9, [None, 0, 2, 0, 2, 0]),
        (7, [3, 2, 0, 0, 0, 1]),
        (4, [0, 2, 0, 1, 0, 0]),
        (2, [None, None, 0, 2, 1, 2]),
        (11, [None, 2, 1, 2, 0, 2]),
    ],
    "maj7": [
        (0, [None, 3, 2, 0, 0, 0]),
        (9, [None, 0, 2, 1, 2, 0]),
        (7, [3, 2, 0, 0, 0, 2]),
        (4, [0, 2, 1, 1, 0, 0]),
        (2, [None, None, 0, 2, 2, 2]),
        (5, [None, None, 3, 2, 1, 0]),
    ],
    "min7": [
        (9, [None, 0, 2, 0, 1, 0]),
        (4, [0, 2, 0, 0, 0, 0]),
        (2, [None, None, 0, 2, 1, 1]),
        (11, [None, 2, 0, 2, 0, 2]),
    ],
    "sus2": [
        (9, [None, 0, 2, 2, 0, 0]),
        (2, [None, None, 0, 2, 3, 0]),
        (0, [None, 3, 0, 0, 1, 3]),
    ],
    "sus4": [
        (9, [None, 0, 2, 2, 3, 0]),
        (2, [None, None, 0, 2, 3, 3]),
        (4, [0, 2, 2, 2, 0, 0]),
        (0, [None, 3, 3, 0, 1, 1]),
        (7, [3, 3, 0, 0, 1, 3]),
    ],
    "7sus4": [
        (9, [None, 0, 2, 0, 3, 0]),
        (2, [None, None, 0, 2, 1, 3]),
        (4, [0, 2, 0, 2, 0, 0]),
    ],
    "maj6": [
        (0, [None, 3, 2, 2, 1, 0]),
        (9, [None, 0, 2, 2, 2, 2]),
        (7, [3, 2, 0, 0, 0, 0]),
        (2, [None, None, 0, 2, 0, 2]),
        (4, [0, 2, 2, 1, 2, 0]),
    ],
    "min6": [
        (9, [None, 0, 2, 2, 1, 2]),
        (4, [0, 2, 2, 0, 2, 0]),
        (2, [None, None, 0, 2, 0, 1]),
    ],
    "dim7": [
        (2, [None, None, 0, 1, 0, 1]),
    ],
    "hdim7": [
        (11, [None, 2, 3, 2, 3, None]),
        (4, [0, 1, 2, 0, 3, 0]),
        (2, [None, None, 0, 1, 1, 1]),
    ],
    "dim": [
        (11, [None, 2, 3, 4, 3, None]),
        (2, [None, None, 0, 1, 3, 1]),
    ],
    "aug": [
        (0, [None, 3, 2, 1, 1, 0]),
        (4, [0, 3, 2, 1, 1, 0]),
        (9, [None, 0, 3, 2, 2, 1]),
    ],
    "minmaj7": [
        (9, [None, 0, 2, 1, 1, 0]),
        (4, [0, 2, 1, 0, 0, 0]),
        (2, [None, None, 0, 2, 2, 1]),
    ],
    "add9": [
        (0, [None, 3, 2, 0, 3, 0]),
        (7, [3, 0, 0, 2, 0, 3]),
        (9, [None, 0, 2, 4, 2, 0]),
        (4, [0, 2, 2, 1, 0, 2]),
    ],
    "9": [
        (4, [0, 2, 0, 1, 3, 2]),
        (9, [None, 0, 2, 4, 2, 3]),
    ],
}

# formas móveis com a raiz na 6ª corda (f = casa da raiz)
E_SHAPE = {
    "maj": lambda f: [f, f + 2, f + 2, f + 1, f, f],
    "min": lambda f: [f, f + 2, f + 2, f, f, f],
    "7": lambda f: [f, f + 2, f, f + 1, f, f],
    "min7": lambda f: [f, f + 2, f, f, f, f],
    "maj7": lambda f: [f, None, f + 1, f + 1, f, None],
    "sus4": lambda f: [f, f + 2, f + 2, f + 2, f, f],
    "7sus4": lambda f: [f, f + 2, f, f + 2, f, f],
    "maj6": lambda f: [f, None, f - 1, f + 1, f, None],
    "min6": lambda f: [f, None, f - 1, f, f, None],
    "hdim7": lambda f: [f, None, f, f, f - 1, None],
    "dim7": lambda f: [f, None, f - 1, f, f - 1, None],
    "minmaj7": lambda f: [f, None, f + 1, f, f, None],
    "aug": lambda f: [f, None, f + 2, f + 1, f + 1, None],
    "9": lambda f: [f, None, f, f + 1, f, f + 2],
}

# formas móveis com a raiz na 5ª corda
A_SHAPE = {
    "maj": lambda f: [None, f, f + 2, f + 2, f + 2, f],
    "min": lambda f: [None, f, f + 2, f + 2, f + 1, f],
    "7": lambda f: [None, f, f + 2, f, f + 2, f],
    "min7": lambda f: [None, f, f + 2, f, f + 1, f],
    "maj7": lambda f: [None, f, f + 2, f + 1, f + 2, f],
    "sus2": lambda f: [None, f, f + 2, f + 2, f, f],
    "sus4": lambda f: [None, f, f + 2, f + 2, f + 3, f],
    "7sus4": lambda f: [None, f, f + 2, f, f + 3, f],
    "maj6": lambda f: [None, f, f + 2, f + 2, f + 2, f + 2],
    "min6": lambda f: [None, f, f + 2, f - 1, f + 1, None],
    "hdim7": lambda f: [None, f, f + 1, f, f + 1, None],
    "dim7": lambda f: [None, f, f + 1, f - 1, f + 1, None],
    "dim": lambda f: [None, f, f + 1, f + 2, f + 1, None],
    "aug": lambda f: [None, f, f + 3, f + 2, f + 2, None],
    "minmaj7": lambda f: [None, f, f + 2, f + 1, f + 1, f],
    "add9": lambda f: [None, f, f + 2, f + 4, f + 2, f],
    "9": lambda f: [None, f, f - 1, f, f, f],
}

# formas pequenas com a raiz na 4ª corda (sem pestana, som mais fino)
D_SHAPE = {
    "maj": lambda f: [None, None, f, f + 2, f + 3, f + 2],
    "min": lambda f: [None, None, f, f + 2, f + 3, f + 1],
    "7": lambda f: [None, None, f, f + 2, f + 1, f + 2],
}


def pitch_classes(frets: list) -> list[int]:
    """Notas que soam, da mais grave para a mais aguda."""
    notes = []
    for string_index, fret in enumerate(frets):
        if fret is None:
            continue
        notes.append((TUNING[string_index] + fret) % 12)
    return notes


def is_valid(frets: list, root: int, family: str) -> bool:
    """Confere se a forma realmente forma o acorde (pode faltar só a quinta)."""
    if any(fret is not None and fret < 0 for fret in frets):
        return False
    notes = pitch_classes(frets)
    if not notes or notes[0] != root:
        return False
    tones = {(root + i) % 12 for i in FAMILY_INTERVALS[family]}
    if not set(notes) <= tones:
        return False
    required = tones - {(root + 7) % 12}
    return required <= set(notes)


def shape_cost(frets: list) -> float:
    """Quanto menor, mais fácil e mais bonito (cordas soltas soando)."""
    fretted = [f for f in frets if f is not None and f > 0]
    played = [f for f in frets if f is not None]
    open_count = sum(1 for f in frets if f == 0)

    # só corda solta
    if not fretted:
        return -0.5

    lowest = min(fretted)
    highest = max(fretted)
    span = highest - lowest

    # mais de 4 casas presas exige pestana
    barre = len(fretted) > 4
    if barre:
        fingers = 1 + sum(1 for f in fretted if f > lowest)
    else:
        fingers = len(fretted)

    # mão humana tem 4 dedos
    if fingers > 4:
        return 99.0

    cost = 0.55 * fingers
    if barre:
        cost = cost + 2.6
    if span > 2:
        cost = cost + 0.6 * (span - 2)
    # casas altas são menos confortáveis
    if lowest > 4:
        cost = cost + 0.2 * (lowest - 4)

    # cordas soltas ressoam: é isso que deixa o violão "lindo"
    cost = cost - 0.35 * open_count

    # acorde cheio soa melhor que acorde de 4 cordas
    if len(played) >= 5:
        cost = cost - 0.2
    if len(played) <= 4:
        cost = cost + 1.0
    return round(cost, 3)


def _candidates(root: int, family: str) -> list[dict]:
    found = []

    # formas abertas que batem com a raiz
    for open_root, frets in OPEN_SHAPES.get(family, []):
        if open_root == root:
            found.append({"frets": frets, "kind": "aberta"})

    # formas móveis
    for kind, table, string_note in (("pestana na 6ª", E_SHAPE, 4), ("pestana na 5ª", A_SHAPE, 9), ("forma de Ré", D_SHAPE, 2)):
        builder = table.get(family)
        if builder is None:
            continue
        base = (root - string_note) % 12
        for fret in (base, base + 12):
            # nada acima da 12ª casa
            if fret > 12:
                continue
            frets = builder(fret)
            found.append({"frets": frets, "kind": "aberta" if fret == 0 else kind})

    valid = []
    seen = set()
    for item in found:
        signature = tuple(item["frets"])
        if signature in seen:
            continue
        if not is_valid(item["frets"], root, family):
            continue
        seen.add(signature)
        item["cost"] = shape_cost(item["frets"])
        # forma de Ré é pouco usada fora da posição aberta
        if item["kind"] == "forma de Ré":
            item["cost"] = round(item["cost"] + 0.6, 3)
        valid.append(item)

    valid.sort(key=lambda item: item["cost"])
    return valid


@lru_cache(maxsize=None)
def shape_table() -> dict:
    """Melhores formas de cada acorde: {'7:maj': [forma1, forma2, ...]}."""
    table = {}
    for root in range(12):
        for family in FAMILY_INTERVALS:
            options = _candidates(root, family)
            table[f"{root}:{family}"] = options[:3]
    return table


def best_shape(chord: Chord) -> dict:
    options = shape_table()[f"{chord.root}:{chord.family}"]
    return options[0]


def capo_penalty(capo: int) -> float:
    """Capo muito alto deixa o som fino e agudo demais."""
    penalty = 0.04 * capo
    if capo > 5:
        penalty = penalty + 0.3 * (capo - 5)
    return penalty


def rank_capos(chord_seconds: dict[str, float], max_capo: int = 9) -> list[dict]:
    """Testa cada casa do capo e devolve da melhor para a pior.

    chord_seconds: {'3:maj': 42.5, ...} quanto tempo cada acorde soa na música.
    """
    total = sum(chord_seconds.values()) or 1.0
    ranking = []
    for capo in range(0, max_capo + 1):
        weighted = 0.0
        worst = 0.0
        shapes = {}
        for key, seconds in chord_seconds.items():
            chord = chord_from_key(key)
            if chord is None:
                continue
            # forma que a mão faz = acorde real descido "capo" semitons
            hand = chord.transpose(-capo)
            shape = best_shape(hand)
            weighted = weighted + shape["cost"] * seconds / total
            worst = max(worst, shape["cost"])
            shapes[key] = {"shape_chord": hand.name(), "frets": shape["frets"], "kind": shape["kind"]}
        score = weighted + 0.12 * worst + capo_penalty(capo)
        ranking.append({"capo": capo, "score": round(score, 3), "shapes": shapes})
    ranking.sort(key=lambda item: item["score"])
    return ranking
