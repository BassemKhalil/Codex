#!/bin/bash
# Build script for Linux/Mac
# Creates a portable NotepadReplica executable

echo "============================================================"
echo "Notepad++ Replica - Linux/Mac Build Script"
echo "============================================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3 first"
    exit 1
fi

# Run the build script
python3 build_portable.py

echo ""
echo "Done!"
