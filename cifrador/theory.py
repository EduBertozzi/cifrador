"""Teoria musical: leitura dos rótulos dos modelos, transposição, nomes e tonalidade."""

from dataclasses import dataclass

import numpy as np

# nomes com sustenido, índice 0 = Dó
SHARPS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# nomes com bemol, usados em tons "bemolizados"
FLATS = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

# valor de cada letra
LETTER_VALUE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# intervalos (em semitons) usados no baixo das inversões ("/3", "/b7"...)
DEGREE_SEMITONES = {
    "1": 0, "b2": 1, "2": 2, "#2": 3, "b3": 3, "3": 4, "4": 5, "#4": 6,
    "b5": 6, "5": 7, "#5": 8, "b6": 8, "6": 9, "bb7": 9, "b7": 10, "7": 11,
    "b9": 1, "9": 2, "#9": 3, "11": 5, "#11": 6, "b13": 8, "13": 9,
}

# famílias de acorde que o violão usa, com as notas (intervalos a partir da raiz)
FAMILY_INTERVALS = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "min7": (0, 3, 7, 10),
    "dim": (0, 3, 6),
    "dim7": (0, 3, 6, 9),
    "hdim7": (0, 3, 6, 10),
    "aug": (0, 4, 8),
    "sus2": (0, 2, 7),
    "sus4": (0, 5, 7),
    "7sus4": (0, 5, 7, 10),
    "maj6": (0, 4, 7, 9),
    "min6": (0, 3, 7, 9),
    "minmaj7": (0, 3, 7, 11),
    "add9": (0, 2, 4, 7),
    "9": (0, 4, 7, 10, 2),
}

# família "pai" de cada uma (a tríade por baixo dela)
PARENT = {
    "maj": "maj",
    "min": "min",
    "7": "maj",
    "maj7": "maj",
    "min7": "min",
    "dim": "dim",
    "dim7": "dim",
    "hdim7": "dim",
    "aug": "aug",
    "sus2": "sus2",
    "sus4": "sus4",
    "7sus4": "sus4",
    "maj6": "maj",
    "min6": "min",
    "minmaj7": "min",
    "add9": "maj",
    "9": "7",
}

# sufixo no padrão das cifras brasileiras
SUFFIX_BR = {
    "maj": "",
    "min": "m",
    "7": "7",
    "maj7": "7M",
    "min7": "m7",
    "dim": "°",
    "dim7": "°7",
    "hdim7": "m7(b5)",
    "aug": "+",
    "sus2": "sus2",
    "sus4": "sus4",
    "7sus4": "7sus4",
    "maj6": "6",
    "min6": "m6",
    "minmaj7": "m(7M)",
    "add9": "add9",
    "9": "7(9)",
}

# como cada qualidade do formato Harte cai numa família nossa
HARTE_TO_FAMILY = {
    "": "maj",
    "maj": "maj",
    "min": "min",
    "7": "7",
    "maj7": "maj7",
    "min7": "min7",
    "dim": "dim",
    "dim7": "dim7",
    "hdim7": "hdim7",
    "aug": "aug",
    "sus2": "sus2",
    "sus4": "sus4",
    "maj6": "maj6",
    "min6": "min6",
    "minmaj7": "minmaj7",
    "9": "9",
    "maj9": "maj7",
    "min9": "min7",
    "11": "7sus4",
    "min11": "min7",
    "13": "7",
    "maj13": "maj7",
    "min13": "min7",
    "5": "maj",
    "1": "maj",
    "maj(9)": "add9",
    "min(9)": "min",
    "sus4(b7)": "7sus4",
    "sus4(b7,9)": "7sus4",
    "7(b9)": "7",
    "7(#9)": "7",
    "7(#11)": "7",
    "7(b13)": "7",
    "min(b13)": "min",
    "aug(b7)": "7",
    "maj(11)": "maj",
    "maj(#11)": "maj",
}


@dataclass(frozen=True)
class Chord:
    """Um acorde: raiz (0 a 11), família e baixo (None quando é a própria raiz)."""

    root: int
    family: str
    bass: int | None = None

    @property
    def key(self) -> str:
        # identificador único, usado na votação
        if self.bass is None:
            return f"{self.root}:{self.family}"
        return f"{self.root}:{self.family}/{self.bass}"

    @property
    def triad_key(self) -> str:
        # mesma raiz, só a tríade
        return f"{self.root}:{PARENT[self.family]}"

    def transpose(self, semitones: int) -> "Chord":
        new_root = (self.root + semitones) % 12
        new_bass = None
        if self.bass is not None:
            new_bass = (self.bass + semitones) % 12
        return Chord(new_root, self.family, new_bass)

    def name(self, flats: bool = False) -> str:
        names = FLATS if flats else SHARPS
        text = names[self.root] + SUFFIX_BR[self.family]
        if self.bass is not None:
            text = text + "/" + names[self.bass]
        return text


def note_value(text: str) -> int:
    """'Bb' vira 10, 'F#' vira 6."""
    value = LETTER_VALUE[text[0].upper()]
    for symbol in text[1:]:
        if symbol == "#":
            value = value + 1
        elif symbol == "b":
            value = value - 1
    return value % 12


def parse_harte(label: str) -> Chord | None:
    """Lê 'C:maj7', 'A#', 'G:min/b3', 'D:sus4(b7)'. Devolve None para 'N' e 'X'."""
    label = label.strip()
    if label in ("N", "X", ""):
        return None

    # separa o baixo ("/b3")
    bass_degree = None
    if "/" in label:
        label, bass_degree = label.split("/", 1)

    # separa raiz e qualidade
    if ":" in label:
        root_text, quality = label.split(":", 1)
    else:
        root_text = label
        quality = "maj"

    root = note_value(root_text)

    # tenta a qualidade inteira, depois sem os parênteses
    family = HARTE_TO_FAMILY.get(quality)
    if family is None:
        base = quality.split("(")[0]
        family = HARTE_TO_FAMILY.get(base, "maj")

    # baixo: só guarda se for diferente da raiz
    bass = None
    if bass_degree:
        semis = DEGREE_SEMITONES.get(bass_degree)
        if semis is not None and semis != 0:
            bass = (root + semis) % 12

    return Chord(root, family, bass)


def chord_from_key(key: str) -> Chord | None:
    """Inverso de Chord.key."""
    if key == "N":
        return None
    bass = None
    if "/" in key:
        key, bass_text = key.split("/")
        bass = int(bass_text)
    root_text, family = key.split(":")
    return Chord(int(root_text), family, bass)


# --- Tonalidade -------------------------------------------------------------

# perfis de Krumhansl-Kessler
MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# tons maiores que se escrevem com bemol
FLAT_MAJOR_KEYS = {5, 10, 3, 8, 1, 6}

# tons menores que se escrevem com bemol (Dm, Gm, Cm, Fm, Bbm, Ebm)
FLAT_MINOR_KEYS = {2, 7, 0, 5, 10, 3}


@dataclass(frozen=True)
class Key:
    tonic: int
    mode: str  # "major" ou "minor"

    @property
    def uses_flats(self) -> bool:
        if self.mode == "major":
            return self.tonic in FLAT_MAJOR_KEYS
        return self.tonic in FLAT_MINOR_KEYS

    def name(self) -> str:
        names = FLATS if self.uses_flats else SHARPS
        if self.mode == "major":
            return names[self.tonic]
        return names[self.tonic] + "m"

    def diatonic_chords(self) -> set[str]:
        """Tríades do campo harmônico (chave 'raiz:familia')."""
        if self.mode == "major":
            steps = [(0, "maj"), (2, "min"), (4, "min"), (5, "maj"), (7, "maj"), (9, "min"), (11, "dim")]
        else:
            # menor natural + V maior da harmônica
            steps = [(0, "min"), (2, "dim"), (3, "maj"), (5, "min"), (7, "min"), (7, "maj"), (8, "maj"), (10, "maj")]
        result = set()
        for interval, family in steps:
            result.add(f"{(self.tonic + interval) % 12}:{family}")
        return result


def estimate_key(chroma_mean: np.ndarray, chord_durations: dict[str, float] | None = None) -> Key:
    """Combina o croma médio com o histograma de acordes (quando já existe)."""
    profile = chroma_mean / (chroma_mean.sum() + 1e-9)

    # soma as notas dos acordes detectados, pesadas pela duração
    if chord_durations:
        chord_profile = np.zeros(12)
        for key, seconds in chord_durations.items():
            chord = chord_from_key(key)
            if chord is None:
                continue
            for interval in FAMILY_INTERVALS[PARENT[chord.family]]:
                chord_profile[(chord.root + interval) % 12] += seconds
            # a raiz pesa um pouco mais
            chord_profile[chord.root] += seconds * 0.5
        chord_profile = chord_profile / (chord_profile.sum() + 1e-9)
        profile = 0.4 * profile + 0.6 * chord_profile

    total_seconds = sum(chord_durations.values()) if chord_durations else 0.0

    best_key = Key(0, "major")
    best_score = -np.inf
    for tonic in range(12):
        for mode, template in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            rotated = np.roll(template, tonic)
            score = np.corrcoef(profile, rotated)[0, 1]

            # quanto da música cabe no campo harmônico, e quanto fica no acorde I
            if total_seconds > 0:
                candidate = Key(tonic, mode)
                diatonic = candidate.diatonic_chords()
                tonic_chord = f"{tonic}:{'maj' if mode == 'major' else 'min'}"
                inside = 0.0
                home = 0.0
                dominant = 0.0
                for key, seconds in chord_durations.items():
                    chord = chord_from_key(key)
                    if chord is None:
                        continue
                    if chord.triad_key in diatonic:
                        inside = inside + seconds
                    if chord.triad_key == tonic_chord:
                        home = home + seconds
                    # acorde com sétima menor no V grau aponta forte pro tom
                    if chord.family in ("7", "9") and chord.root == (tonic + 7) % 12:
                        dominant = dominant + seconds
                score = score + 2.0 * inside / total_seconds + 0.4 * home / total_seconds + 0.6 * dominant / total_seconds

            if score > best_score:
                best_score = score
                best_key = Key(tonic, mode)
    return best_key
