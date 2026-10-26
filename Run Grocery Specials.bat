@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python was not found. Install Python and make sure it is on PATH.
    goto finish
)

python -c "import flask, requests" >nul 2>&1
if errorlevel 1 (
    echo Required Python packages are missing.
    echo Install them by running: python -m pip install -r requirements.txt
    goto finish
)

echo Opening Grocery Specials in your browser...
echo Keep this window open while using the search page.
echo.
python "%~dp0grocery_web.py"
if errorlevel 1 (
    echo.
    echo The grocery tracker exited with an error.
)

:finish
echo.
pause
