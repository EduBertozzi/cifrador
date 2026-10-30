@echo off
REM Windows: abre o Cifrador (e instala na primeira vez).
cd /d "%~dp0"

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg nao encontrado. Rode: winget install Gyan.FFmpeg
  echo Depois feche e abra o terminal de novo.
  pause
  exit /b 1
)

REM ainda nao instalou: chama o instalador (que aguenta internet caindo)
if not exist ".venv\instalado.ok" (
  call instalar.bat
  if not exist ".venv\instalado.ok" exit /b 1
)

REM modelos de IA (Demucs, BTC, Whisper) ficam dentro desta pasta, nao no C:
set "HF_HOME=%~dp0_modelos\huggingface"
set "TORCH_HOME=%~dp0_modelos\torch"
set "XDG_CACHE_HOME=%~dp0_modelos"

REM puxa a versao mais nova do GitHub (se tiver internet)
.venv\Scripts\python atualizar.py
.venv\Scripts\python -m cifrador %*
pause
