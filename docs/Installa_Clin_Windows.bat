@echo off
chcp 65001 >nul
title Clin - Installazione app desktop per Windows
echo.
echo  Clin - Installazione app desktop per Windows
echo  ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo  Python 3 non trovato sul computer.
  echo  Apro la pagina ufficiale di Python: installalo spuntando "Add Python to PATH" e poi riapri questo file.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)

set "DEST=%USERPROFILE%\.clin\app"
set "ZIP=%TEMP%\clin-main.zip"
set "TMP=%TEMP%\clin-extract"

echo  [1/4] Scaricamento di Clin in %DEST%...
if not exist "%USERPROFILE%\.clin" mkdir "%USERPROFILE%\.clin"
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'https://github.com/clin-app/clin/archive/refs/heads/main.zip' -OutFile '%ZIP%'"
if errorlevel 1 (
  echo  Errore durante il download. Controlla la connessione e riprova.
  pause
  exit /b 1
)

if exist "%TMP%" rmdir /s /q "%TMP%"
powershell -NoProfile -Command "Expand-Archive -Path '%ZIP%' -DestinationPath '%TMP%' -Force"
if exist "%DEST%\.venv" move "%DEST%\.venv" "%TEMP%\clin-venv-bak" >nul
if exist "%DEST%\models" move "%DEST%\models" "%TEMP%\clin-models-bak" >nul
if exist "%DEST%" rmdir /s /q "%DEST%"
move "%TMP%\clin-main" "%DEST%" >nul
if exist "%TEMP%\clin-venv-bak" move "%TEMP%\clin-venv-bak" "%DEST%\.venv" >nul
if exist "%TEMP%\clin-models-bak" move "%TEMP%\clin-models-bak" "%DEST%\models" >nul
del /f /q "%ZIP%" 2>nul
rmdir /s /q "%TMP%" 2>nul

echo  [2/4] Creazione ambiente Python e installazione interfaccia grafica...
if not exist "%DEST%\.venv\Scripts\python.exe" python -m venv "%DEST%\.venv"
"%DEST%\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check --upgrade pip
"%DEST%\.venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check "PyMuPDF>=1.24" "openpyxl>=3.1" "PySide6>=6.6"
if errorlevel 1 (
  echo  Errore nell'installazione dei pacchetti Python.
  pause
  exit /b 1
)

echo  [3/4] Scaricamento modello OCR italiano (2,6 MB)...
"%DEST%\.venv\Scripts\python.exe" "%DEST%\scripts\fetch_ocr_model.py" >nul 2>nul

echo  [4/4] Creazione icona Clin sul Desktop...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Clin.lnk'); $s.TargetPath = '%DEST%\.venv\Scripts\pythonw.exe'; $s.Arguments = '\"%DEST%\clin_gui.py\"'; $s.WorkingDirectory = '%DEST%'; $s.Description = 'Clin - Anonimizzazione locale'; $s.Save()"

echo.
echo  Pronto! Trovi l'icona "Clin" sul Desktop. Avvio l'applicazione...
start "" "%DEST%\.venv\Scripts\pythonw.exe" "%DEST%\clin_gui.py"
echo.
pause
