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

set "ASSET=%~1"
if "%ASSET%"=="" set "ASSET=XAUUSD"

set "EVIDENCE=%~2"
if "%EVIDENCE%"=="" set "EVIDENCE=examples\xauusd_evidence.json"

if not exist "%EVIDENCE%" set "EVIDENCE=%PROJECT_ROOT%%EVIDENCE%"
if not exist "%EVIDENCE%" (
    echo Evidence file "%EVIDENCE%" does not exist. 1>&2
    exit /b 1
)

set "PYTHONPATH=%PROJECT_ROOT%src"
"%PYTHON_EXE%" -m macro_engine.cli "%ASSET%" "%EVIDENCE%"
exit /b %ERRORLEVEL%

