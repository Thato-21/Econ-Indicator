@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
set "PYTHON_EXE=C:\msys64\ucrt64\bin\python.exe"

if not exist "%PYTHON_EXE%" (
    where python.exe >nul 2>nul
    if errorlevel 1 (
        echo Python 3.12+ was not found. Install Python from python.org and try again. 1>&2
        exit /b 1
    )
    set "PYTHON_EXE=python.exe"
)

set "PYTHONPATH=%PROJECT_ROOT%src"
cd /d "%PROJECT_ROOT%"
echo Starting Macro Compass at http://127.0.0.1:8765
echo Keep this window open. Press Ctrl+C to stop the app.
"%PYTHON_EXE%" -m macro_engine.web --host 127.0.0.1 --port 8765 --open
exit /b %ERRORLEVEL%
