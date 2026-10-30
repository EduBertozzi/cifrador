@echo off
REM Windows: na primeira vez instala tudo (com CUDA pra GTX 1060), depois so abre o Cifrador.
cd /d "%~dp0"

where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg nao encontrado. Rode: winget install Gyan.FFmpeg
  echo Depois feche e abra o terminal de novo.
  pause
  exit /b 1
)

REM so considera instalado quando a instalacao inteira terminou sem erro
if exist ".venv\instalado.ok" goto rodar

echo.
echo Versao do Python:
python --version
echo.
echo Instalando (5 a 15 minutos, baixa uns 3 GB)...

if exist ".venv" rmdir /s /q ".venv"

python -m venv .venv
if errorlevel 1 goto erro

.venv\Scripts\python -m pip install --upgrade pip
if errorlevel 1 goto erro

REM PyTorch 2.14 com CUDA 12.6: ultima versao que suporta placas Pascal (GTX 10xx)
.venv\Scripts\python -m pip install torch==2.14.0 --index-url https://download.pytorch.org/whl/cu126
if errorlevel 1 goto erro

.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo ok > ".venv\instalado.ok"

:rodar
REM puxa a versao mais nova do GitHub (se tiver internet)
.venv\Scripts\python atualizar.py
.venv\Scripts\python -m cifrador %*
pause
exit /b 0

:erro
echo.
echo ===============================================
echo  A instalacao falhou. Manda print dessa janela.
echo ===============================================
pause
exit /b 1
