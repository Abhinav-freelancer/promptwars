@echo off
REM SANCHALAN Setup Script — installs SUMO + Python deps
REM Run from: sanchalan/

echo === SANCHALAN Setup ===

REM 1. Check for SUMO
where sumo >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] SUMO found in PATH
    goto :check_python
)

REM Check SUMO_HOME
if defined SUMO_HOME (
    echo [OK] SUMO_HOME=%SUMO_HOME%
    goto :check_python
)

echo [!] SUMO not found. Install options:
echo     winget install EclipseFoundation.SUMO
echo     OR download from https://sumo.dlr.de/download.php
echo     OR set SUMO_HOME to your install path
echo.
echo Set SUMO_HOME or add SUMO to PATH, then re-run this script.
echo Proceeding with Python setup only...

:check_python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found
    exit /b 1
)
echo [OK] Python found

REM 2. Install Python dependencies
echo Installing Python dependencies...
pip install -r requirements.txt

REM 3. Build SUMO network from XML definitions
echo.
echo Building SUMO network...
cd simulation\network
netconvert -n sanchalan.nod.xml -e sanchalan.edg.xml -x sanchalan.con.xml -o sanchalan.net.xml
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] netconvert failed. Make sure SUMO bin is in PATH.
    echo You can install SUMO via: winget install EclipseFoundation.SUMO
) else (
    echo [OK] SUMO network built: sanchalan.net.xml
)
cd ..\..

REM 4. Init DB
echo.
echo Initializing database...
cd backend
python -c "from database import init_db, seed_corridors; init_db(); seed_corridors()"
cd ..

echo.
echo === Setup complete ===
echo To start: cd backend ^& python -m uvicorn main:app --reload --port 8000
