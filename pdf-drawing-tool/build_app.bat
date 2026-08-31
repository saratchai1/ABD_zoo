@echo off
setlocal
cd /d "%~dp0"
py -m pip install -r requirements.txt
py -m PyInstaller --noconfirm --clean --onedir --windowed --name "PDF Drawing Tool" v260_main.py
if errorlevel 1 exit /b 1
echo.
echo V2.6.0 app folder created: dist\PDF Drawing Tool\
echo EXE: dist\PDF Drawing Tool\PDF Drawing Tool.exe
pause
