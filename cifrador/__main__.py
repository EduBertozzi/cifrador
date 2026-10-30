"""Uso:
    python -m cifrador                 abre a interface no navegador
    python -m cifrador musica.mp3      analisa direto no terminal e imprime a cifra
"""

import argparse
import logging
import threading
import webbrowser
from pathlib import Path


def serve(port: int) -> None:
    import uvicorn

    from .server import app

    url = f"http://127.0.0.1:{port}"
    print(f"\n  Cifrador rodando em {url}\n  (Ctrl+C para parar)\n")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


def run_cli(source: str, quality: str, lyrics: bool) -> None:
    from .pipeline import Options, analyze
    from .theory import Chord

    work = Path("musicas") / Path(source).stem
    path = Path(source)
    if source.startswith("http"):
        from .audio import download_from_link

        path = download_from_link(source, work / "entrada")

    def report(stage: str, value: float) -> None:
        print(f"  [{value * 100:5.1f}%] {stage}")

    result = analyze(path, work, Options(quality=quality, lyrics=lyrics), report)
    flats = result["key"]["flats"]
    best = result["capos"][0]

    print(f"\nTom: {result['key']['name']}   BPM: {result['bpm']}   Compasso: {result['meter']}/4")
    print(f"Afinação: {result['tuning_cents']:+d} cents")
    if best["capo"]:
        print(f"Capotraste: {best['capo']}ª casa\n")
    else:
        print("Capotraste: sem capo\n")

    for segment in result["segments"]:
        if segment["root"] is None:
            continue
        real = Chord(segment["root"], segment["family"], segment["bass"])
        hand = real.transpose(-best["capo"])
        print(f"  {segment['start']:7.2f}s  {real.name(flats):10s} forma: {hand.name():10s} confiança {segment['confidence']:.0%}")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="cifrador")
    parser.add_argument("musica", nargs="?", help="arquivo de áudio ou link (opcional)")
    parser.add_argument("--porta", type=int, default=8765)
    parser.add_argument("--qualidade", choices=["rapido", "maximo"], default="rapido")
    parser.add_argument("--sem-letra", action="store_true")
    args = parser.parse_args()

    if args.musica:
        run_cli(args.musica, args.qualidade, not args.sem_letra)
    else:
        serve(args.porta)


if __name__ == "__main__":
    main()
