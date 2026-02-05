@echo off
REM Build script for Windows
REM Creates a portable NotepadReplica.exe

echo ============================================================
echo Notepad++ Replica - Windows Build Script
echo ============================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Run the build script
python build_portable.py

echo.
pause
