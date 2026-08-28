@echo off
chcp 65001 >nul
setlocal

title PDF Merge - 176 Sheets

echo ============================================================
echo PDF MERGE - 176 SHEETS
echo ============================================================
echo.

if not "%~1"=="" (
    set "TARGET=%~1"
    goto HAVE_TARGET
)

echo ลากโฟลเดอร์มาวางบนไฟล์ BAT นี้
echo หรือวาง path ของโฟลเดอร์ด้านล่าง
echo.
set /p "TARGET=Folder: "
set "TARGET=%TARGET:"=%"

:HAVE_TARGET
if "%TARGET%"=="" (
    echo ERROR: ไม่ได้ระบุโฟลเดอร์
    pause
    exit /b 1
)

if not exist "%TARGET%\" (
    echo ERROR: ไม่พบโฟลเดอร์
    echo %TARGET%
    pause
    exit /b 1
)

where py >nul 2>&1
if %errorlevel%==0 goto USE_PY
where python >nul 2>&1
if %errorlevel%==0 goto USE_PYTHON

echo ERROR: ไม่พบ Python ในเครื่อง
echo ติดตั้ง Python แล้วลองใหม่
pause
exit /b 1

:USE_PY
py -3 -c "import fitz" >nul 2>&1
if errorlevel 1 (
    echo กำลังติดตั้ง PyMuPDF...
    py -3 -m pip install PyMuPDF
    if errorlevel 1 goto INSTALL_FAIL
)
py -3 "%~dp0merge_pdf.py" "%TARGET%" --expected 176 --strict
set "RESULT=%errorlevel%"
goto FINISH

:USE_PYTHON
python -c "import fitz" >nul 2>&1
if errorlevel 1 (
    echo กำลังติดตั้ง PyMuPDF...
    python -m pip install PyMuPDF
    if errorlevel 1 goto INSTALL_FAIL
)
python "%~dp0merge_pdf.py" "%TARGET%" --expected 176 --strict
set "RESULT=%errorlevel%"
goto FINISH

:INSTALL_FAIL
echo.
echo ERROR: ติดตั้ง PyMuPDF ไม่สำเร็จ
pause
exit /b 1

:FINISH
echo.
if "%RESULT%"=="0" (
    echo SUCCESS
) else (
    echo FAILED - กรุณาดูข้อความด้านบน
)
echo.
pause
exit /b %RESULT%
