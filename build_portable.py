#!/usr/bin/env python3
"""
Build Script for Notepad++ Replica

Creates a portable single-file executable using PyInstaller.

Requirements:
    pip install pyinstaller

Usage:
    python build_portable.py
"""

import subprocess
import sys
import os
import shutil


def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False


def install_pyinstaller():
    """Install PyInstaller"""
    print("Installing PyInstaller...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])


def build_executable():
    """Build the portable executable"""
    # PyInstaller options
    script_dir = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(script_dir, 'notepad_replica.py')

    # Build command
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onefile',                    # Single file executable
        '--windowed',                   # No console window
        '--name', 'NotepadReplica',     # Output name
        '--clean',                      # Clean PyInstaller cache
        '--noconfirm',                  # Replace output without asking

        # Add data files
        '--add-data', f'{script_dir}/notepad_replica;notepad_replica',

        # Hidden imports (just in case)
        '--hidden-import', 'tkinter',
        '--hidden-import', 'tkinter.ttk',
        '--hidden-import', 'tkinter.font',
        '--hidden-import', 'tkinter.filedialog',
        '--hidden-import', 'tkinter.messagebox',
        '--hidden-import', 'tkinter.simpledialog',

        main_script
    ]

    print("Building portable executable...")
    print(f"Command: {' '.join(cmd)}")
    print()

    # Run PyInstaller
    result = subprocess.run(cmd, cwd=script_dir)

    if result.returncode == 0:
        exe_path = os.path.join(script_dir, 'dist', 'NotepadReplica.exe')
        if os.path.exists(exe_path):
            print()
            print("=" * 60)
            print("BUILD SUCCESSFUL!")
            print("=" * 60)
            print(f"\nPortable executable created at:\n  {exe_path}")
            print(f"\nFile size: {os.path.getsize(exe_path) / (1024*1024):.1f} MB")
            print("\nYou can now copy this file anywhere and run it!")
            print("\nUsage:")
            print("  NotepadReplica.exe                  - Launch editor")
            print("  NotepadReplica.exe --recover        - Auto-recover Notepad++ session")
            print("  NotepadReplica.exe file.txt         - Open specific file")
            return True

    print("Build failed!")
    return False


def main():
    """Main build process"""
    print("=" * 60)
    print("Notepad++ Replica - Portable Build Script")
    print("=" * 60)
    print()

    # Check/install PyInstaller
    if not check_pyinstaller():
        print("PyInstaller not found.")
        response = input("Install PyInstaller? (y/n): ").strip().lower()
        if response == 'y':
            install_pyinstaller()
        else:
            print("PyInstaller is required to build the executable.")
            return 1

    # Build
    success = build_executable()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
