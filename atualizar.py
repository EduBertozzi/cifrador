"""Atualiza o Cifrador sozinho a partir do GitHub (sem precisar de git instalado).

Roda toda vez que o iniciar abre. Se estiver sem internet, só segue em frente.
"""

import hashlib
import io
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# repositório oficial do projeto
REPO = "EduBertozzi/cifrador"
BRANCH = "main"
ZIP_URL = f"https://github.com/{REPO}/archive/refs/heads/{BRANCH}.zip"

ROOT = Path(__file__).resolve().parent

# nunca mexe nisso: ambiente instalado, músicas analisadas e o próprio script que está rodando
KEEP = {".venv", "musicas", "iniciar.bat", "iniciar.sh", ".git"}


def file_hash(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    print("Procurando atualização...")
    try:
        with urllib.request.urlopen(ZIP_URL, timeout=20) as response:
            data = response.read()
    except Exception as error:  # noqa: BLE001
        print(f"Sem atualização agora ({error.__class__.__name__}). Seguindo com a versão atual.")
        return

    requirements_before = file_hash(ROOT / "requirements.txt")
    archive = zipfile.ZipFile(io.BytesIO(data))

    # o zip vem com uma pasta raiz tipo "cifrador-main/"
    prefix = archive.namelist()[0].split("/")[0] + "/"
    changed = 0
    for name in archive.namelist():
        relative = name[len(prefix):]
        if not relative or name.endswith("/"):
            continue
        if relative.split("/")[0] in KEEP:
            continue
        target = ROOT / relative
        content = archive.read(name)
        if target.exists() and target.read_bytes() == content:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        changed = changed + 1

    # apaga o cache antigo do Python pra não rodar código velho
    for cache in ROOT.rglob("__pycache__"):
        if ".venv" not in cache.parts:
            shutil.rmtree(cache, ignore_errors=True)

    if changed == 0:
        print("Já está na versão mais nova.")
        return
    print(f"Atualizado ({changed} arquivos).")

    # se entrou biblioteca nova, instala
    if file_hash(ROOT / "requirements.txt") != requirements_before:
        print("Instalando bibliotecas novas...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], check=False)


if __name__ == "__main__":
    main()
