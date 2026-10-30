"""Os dois modelos de reconhecimento de acordes usados no ensemble.

1. lv-chordia: ensemble de 5 CNNs + HMM (ISMIR 2019, Jiang et al.), ~170 acordes.
2. BTC: Bi-directional Transformer for Chord recognition (ISMIR 2019, Park et al.), 170 acordes.

Os dois erram em lugares diferentes, então a votação entre eles
(rodando na mixagem inteira e no stem harmônico) acerta mais que qualquer um sozinho.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import torch

log = logging.getLogger("cifrador")


@dataclass
class Segment:
    start: float
    end: float
    label: str


class LVChordia:
    name = "lv-chordia"
    weight = 1.0

    def __init__(self, device: str):
        # versões novas têm sessão (carrega o ensemble uma vez só); as antigas só a função
        try:
            from lv_chordia import LVChordiaSession

            self.session = LVChordiaSession(chord_dict_name="submission", device=device)
            self.session.load()
        except ImportError:
            from lv_chordia.chord_recognition import chord_recognition

            self.session = None
            self.function = chord_recognition

    def predict(self, path: Path) -> list[Segment]:
        if self.session is not None:
            raw = self.session.infer(str(path))
        else:
            raw = self.function(str(path), chord_dict_name="submission")
        segments = []
        for item in raw:
            segments.append(Segment(float(item["start_time"]), float(item["end_time"]), item["chord"]))
        return segments


class BTC:
    name = "btc"
    weight = 0.85

    def __init__(self, device: str):
        from transformers import AutoModel

        self.model = AutoModel.from_pretrained(
            "puar-playground/btc-chord",
            trust_remote_code=True,
            device=device,
        )

    def predict(self, path: Path) -> list[Segment]:
        raw = self.model.predict(str(path))
        segments = []
        for item in raw:
            segments.append(Segment(float(item["start"]), float(item["end"]), item["chord"]))
        return segments


_CACHE: dict[str, object] = {}


def load_recognizers(device: str | None = None) -> list:
    """Carrega os modelos uma vez só. Se um falhar, segue com o outro."""
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    loaded = []
    for cls in (LVChordia, BTC):
        if cls.name in _CACHE:
            loaded.append(_CACHE[cls.name])
            continue
        try:
            instance = cls(device)
        except Exception as error:  # noqa: BLE001
            log.warning("Não consegui carregar %s: %s", cls.name, error)
            continue
        _CACHE[cls.name] = instance
        loaded.append(instance)

    if not loaded:
        raise RuntimeError("Nenhum modelo de acorde carregou. Rode 'pip install -r requirements.txt' de novo.")
    return loaded
