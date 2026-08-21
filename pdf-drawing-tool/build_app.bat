@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt
py -m PyInstaller --noconfirm --clean --onefile --windowed --name "PDF Drawing Tool" main.py
if errorlevel 1 exit /b 1
echo.
echo EXE created: dist\PDF Drawing Tool.exe
pause
