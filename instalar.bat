@echo off
REM Instala tudo usando so o disco onde esta a pasta (nao enche o C:).
cd /d "%~dp0"

echo.
echo === Limpando o cache antigo do pip no C: (sobra das tentativas anteriores) ===
python -m pip cache purge >nul 2>nul
if exist "%LOCALAPPDATA%\pip\cache" rmdir /s /q "%LOCALAPPDATA%\pip\cache"

REM daqui pra frente, temporarios e cache ficam dentro desta pasta
set "TEMP=%~dp0_temp"
set "TMP=%~dp0_temp"
set "PIP_CACHE_DIR=%~dp0_temp\pip"
if not exist "_temp" mkdir "_temp"

set WHEEL=torch-2.14.0+cu126-cp314-cp314-win_amd64.whl
set URL=https://download.pytorch.org/whl/cu126/torch-2.14.0%%2Bcu126-cp314-cp314-win_amd64.whl

echo.
echo === 1/4 Preparando o ambiente ===
if exist ".venv" rmdir /s /q ".venv"
python -m venv .venv
if errorlevel 1 goto erro
.venv\Scripts\python -m pip install --no-cache-dir --upgrade pip

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
.venv\Scripts\python -m pip install --no-cache-dir "%WHEEL%"
if errorlevel 1 goto erro
del "%WHEEL%"

echo.
echo === 4/4 Instalando o resto ===
.venv\Scripts\python -m pip install --no-cache-dir -r requirements.txt
if errorlevel 1 goto erro

echo ok > ".venv\instalado.ok"
rmdir /s /q "_temp" 2>nul

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
