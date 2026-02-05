#!/usr/bin/env python3
"""
Notepad++ Replica - Entry Point

A portable text editor with Notepad++ session recovery.
Run this script directly or build it as a portable executable.

Usage:
    python notepad_replica.py                    # Launch the editor
    python notepad_replica.py file1.txt file2.py # Open specific files
    python notepad_replica.py --recover          # Auto-recover Notepad++ session
"""

import sys
import os

# Add the parent directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from notepad_replica.main_app import NotepadReplica


def main():
    """Main entry point"""
    app = NotepadReplica()

    # Parse command line arguments
    args = sys.argv[1:]

    auto_recover = False
    files_to_open = []

    for arg in args:
        if arg in ('--recover', '-r', '/recover'):
            auto_recover = True
        elif arg in ('--help', '-h', '/h', '/?'):
            print(__doc__)
            return
        elif os.path.exists(arg):
            files_to_open.append(arg)

    # Auto-recover if requested
    if auto_recover:
        app.after(100, app.recover_notepadpp_session)
    # Open files if provided
    elif files_to_open:
        for filepath in files_to_open:
            app.after(100, lambda f=filepath: app.open_file(f))

    app.mainloop()


if __name__ == '__main__':
    main()
