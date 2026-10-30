@echo off
REM Instala tudo baixando o PyTorch com curl (aguenta internet caindo).
cd /d "%~dp0"

set WHEEL=torch-2.14.0+cu126-cp314-cp314-win_amd64.whl
set URL=https://download.pytorch.org/whl/cu126/torch-2.14.0%%2Bcu126-cp314-cp314-win_amd64.whl

echo.
echo === 1/4 Preparando o ambiente ===
if not exist ".venv\Scripts\python.exe" python -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip

echo.
echo === 2/4 Baixando o PyTorch (2,6 GB). Se a internet cair ele tenta de novo sozinho ===
set TENTATIVA=0
:baixar
set /a TENTATIVA+=1
curl -L -C - --retry 10 --retry-delay 3 -o "%WHEEL%" "%URL%"
if errorlevel 1 (
  if %TENTATIVA% LSS 30 (
    echo Caiu. Continuando de onde parou ^(tentativa %TENTATIVA%^)...
    timeout /t 3 >nul
    goto baixar
  )
  goto erro
)

echo.
echo === 3/4 Instalando o PyTorch ===
.venv\Scripts\python -m pip install "%WHEEL%"
if errorlevel 1 goto erro

echo.
echo === 4/4 Instalando o resto ===
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto erro

echo ok > ".venv\instalado.ok"
del "%WHEEL%"

echo.
echo ===============================================
echo  Pronto! Agora e so abrir o iniciar.bat
echo ===============================================
pause
exit /b 0

:erro
echo.
echo ===============================================
echo  Deu erro. Manda print dessa janela.
echo ===============================================
pause
exit /b 1
