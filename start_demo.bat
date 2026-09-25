@echo off
setlocal
title BoundaryLens SIH26011 Demo — Team areonerds

echo ==================================================
echo   BoundaryLens SIH26011 — Live Demonstration
echo   Team areonerds
echo ==================================================
echo.

:: Detect virtual environment
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment (venv)...
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
) else (
    echo [INFO] No local venv found, using system Python.
)

echo.
echo [STEP 1/2] Running Pre-Demo Health Check...
echo --------------------------------------------------
python scripts\demo_health_check.py
if errorlevel 1 (
    echo.
    echo [ERROR] Demo health check failed.
    echo Please resolve the missing items or run the full pipeline:
    echo     python run_pipeline.py
    echo.
    pause
    exit /b 1
)

echo.
echo [STEP 2/2] Launching 3D Demo Web Server...
echo --------------------------------------------------
python run_demo.py

pause
