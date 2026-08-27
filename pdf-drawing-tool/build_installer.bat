@echo off
setlocal
cd /d "%~dp0"
if not exist "dist\PDF Drawing Tool\PDF Drawing Tool.exe" call build_app.bat
if errorlevel 1 exit /b 1
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo Inno Setup 6 not found. Install it from https://jrsoftware.org/isdl.php
  pause
  exit /b 1
)
"%ISCC%" setup.iss
if errorlevel 1 exit /b 1
echo.
echo Setup created: installer_output\PDF_Drawing_Tool_Setup.exe
pause
