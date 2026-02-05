"""
Notepad++ Session Parser

Parses Notepad++ session.xml files and recovers backup files to restore
open tabs and their content.

Notepad++ stores session data in:
- %APPDATA%\Notepad++\session.xml - list of open files
- %APPDATA%\Notepad++\backup\ - unsaved file backups
"""

import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from pathlib import Path
import re
import glob


@dataclass
class TabInfo:
    """Information about a single tab/file"""
    filepath: str
    filename: str
    content: Optional[str] = None
    encoding: str = "utf-8"
    cursor_pos: int = 0
    first_visible_line: int = 0
    is_backup: bool = False
    backup_path: Optional[str] = None
    is_new_file: bool = False  # For "new 1", "new 2" etc.
    lang: str = "Normal Text"


@dataclass
class SessionData:
    """Complete session data from Notepad++"""
    tabs: List[TabInfo] = field(default_factory=list)
    active_tab_index: int = 0
    errors: List[str] = field(default_factory=list)


def get_notepadpp_paths() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Get paths to Notepad++ configuration directories.

    Returns:
        Tuple of (config_dir, session_file, backup_dir)
    """
    # Standard Notepad++ locations
    appdata = os.environ.get('APPDATA', '')

    if appdata:
        npp_dir = os.path.join(appdata, 'Notepad++')
        session_file = os.path.join(npp_dir, 'session.xml')
        backup_dir = os.path.join(npp_dir, 'backup')

        if os.path.exists(npp_dir):
            return npp_dir, session_file, backup_dir

    # Check portable installation locations
    possible_locations = [
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Notepad++'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Notepad++'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Notepad++'),
    ]

    for loc in possible_locations:
        if loc and os.path.exists(loc):
            session_file = os.path.join(loc, 'session.xml')
            backup_dir = os.path.join(loc, 'backup')
            if os.path.exists(session_file):
                return loc, session_file, backup_dir

    return None, None, None


def parse_session_xml(session_file: str) -> SessionData:
    """
    Parse Notepad++ session.xml file.

    Args:
        session_file: Path to session.xml

    Returns:
        SessionData object with parsed tab information
    """
    session = SessionData()

    if not os.path.exists(session_file):
        session.errors.append(f"Session file not found: {session_file}")
        return session

    try:
        tree = ET.parse(session_file)
        root = tree.getroot()

        # Find all File elements in mainView and subView
        for view in ['mainView', 'subView']:
            view_elem = root.find(f'.//{view}')
            if view_elem is None:
                continue

            # Get active tab index for main view
            if view == 'mainView':
                active_index = view_elem.get('activeIndex', '0')
                try:
                    session.active_tab_index = int(active_index)
                except ValueError:
                    pass

            for file_elem in view_elem.findall('.//File'):
                filepath = file_elem.get('filename', '')
                if not filepath:
                    continue

                # Extract filename
                filename = os.path.basename(filepath)

                # Check if it's a "new" file (unsaved)
                is_new = filepath.startswith('new ') or '\\new ' in filepath.lower()

                # Get cursor position
                cursor_pos = 0
                first_visible = 0
                try:
                    cursor_pos = int(file_elem.get('firstVisibleLine', '0'))
                    first_visible = int(file_elem.get('firstVisibleLine', '0'))
                except ValueError:
                    pass

                # Get language
                lang = file_elem.get('lang', 'Normal Text')

                # Get encoding
                encoding = file_elem.get('encoding', 'utf-8')
                if encoding == '-1':
                    encoding = 'utf-8'

                # Get backup path if present
                backup_path = file_elem.get('backupFilePath', '')

                tab = TabInfo(
                    filepath=filepath,
                    filename=filename,
                    encoding=encoding,
                    cursor_pos=cursor_pos,
                    first_visible_line=first_visible,
                    is_new_file=is_new,
                    backup_path=backup_path if backup_path else None,
                    lang=lang
                )

                session.tabs.append(tab)

    except ET.ParseError as e:
        session.errors.append(f"Error parsing session.xml: {e}")
    except Exception as e:
        session.errors.append(f"Unexpected error: {e}")

    return session


def find_backup_files(backup_dir: str) -> dict:
    """
    Find all backup files in the Notepad++ backup directory.

    Notepad++ backup filenames follow patterns like:
    - filename.ext@2024-01-15_143022
    - new 1@2024-01-15_143022

    Args:
        backup_dir: Path to backup directory

    Returns:
        Dictionary mapping original filename to list of backup files
    """
    backups = {}

    if not os.path.exists(backup_dir):
        return backups

    # Pattern: filename@timestamp or filename.ext@timestamp
    backup_pattern = re.compile(r'^(.+?)@(\d{4}-\d{2}-\d{2}_\d{6})$')

    for entry in os.listdir(backup_dir):
        full_path = os.path.join(backup_dir, entry)
        if not os.path.isfile(full_path):
            continue

        match = backup_pattern.match(entry)
        if match:
            original_name = match.group(1)
            timestamp = match.group(2)

            if original_name not in backups:
                backups[original_name] = []

            backups[original_name].append({
                'path': full_path,
                'timestamp': timestamp,
                'filename': entry
            })

    # Sort backups by timestamp (newest first)
    for name in backups:
        backups[name].sort(key=lambda x: x['timestamp'], reverse=True)

    return backups


def read_file_content(filepath: str, encoding: str = 'utf-8') -> Tuple[Optional[str], Optional[str]]:
    """
    Read content from a file, trying multiple encodings.

    Args:
        filepath: Path to file
        encoding: Preferred encoding

    Returns:
        Tuple of (content, error_message)
    """
    encodings_to_try = [encoding, 'utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'utf-16']

    # Remove duplicates while preserving order
    seen = set()
    encodings_to_try = [e for e in encodings_to_try if not (e in seen or seen.add(e))]

    if not os.path.exists(filepath):
        return None, f"File not found: {filepath}"

    for enc in encodings_to_try:
        try:
            with open(filepath, 'r', encoding=enc) as f:
                return f.read(), None
        except UnicodeDecodeError:
            continue
        except Exception as e:
            return None, str(e)

    # Try binary read as last resort
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
            return content.decode('utf-8', errors='replace'), None
    except Exception as e:
        return None, str(e)


def recover_session(session_file: Optional[str] = None,
                    backup_dir: Optional[str] = None) -> SessionData:
    """
    Recover a complete Notepad++ session including backup files.

    Args:
        session_file: Path to session.xml (auto-detected if None)
        backup_dir: Path to backup directory (auto-detected if None)

    Returns:
        SessionData with all tabs and their content
    """
    # Auto-detect paths if not provided
    if session_file is None or backup_dir is None:
        _, auto_session, auto_backup = get_notepadpp_paths()
        if session_file is None:
            session_file = auto_session
        if backup_dir is None:
            backup_dir = auto_backup

    session = SessionData()

    if session_file is None:
        session.errors.append("Could not locate Notepad++ session file")
        return session

    # Parse session.xml
    session = parse_session_xml(session_file)

    # Find all backup files
    backups = {}
    if backup_dir:
        backups = find_backup_files(backup_dir)

    # Load content for each tab
    for tab in session.tabs:
        content = None

        # First, try to load from explicit backup path
        if tab.backup_path and os.path.exists(tab.backup_path):
            content, error = read_file_content(tab.backup_path, tab.encoding)
            if content is not None:
                tab.content = content
                tab.is_backup = True
                continue

        # Second, try to find matching backup file
        filename = tab.filename
        if filename in backups and backups[filename]:
            newest_backup = backups[filename][0]
            content, error = read_file_content(newest_backup['path'], tab.encoding)
            if content is not None:
                tab.content = content
                tab.is_backup = True
                tab.backup_path = newest_backup['path']
                continue

        # Check for full path match in backups
        for backup_name, backup_list in backups.items():
            if tab.filepath.endswith(backup_name) or backup_name.endswith(tab.filename):
                if backup_list:
                    newest_backup = backup_list[0]
                    content, error = read_file_content(newest_backup['path'], tab.encoding)
                    if content is not None:
                        tab.content = content
                        tab.is_backup = True
                        tab.backup_path = newest_backup['path']
                        break

        if tab.content is not None:
            continue

        # Third, try to load from original file path
        if os.path.exists(tab.filepath):
            content, error = read_file_content(tab.filepath, tab.encoding)
            if content is not None:
                tab.content = content
            elif error:
                session.errors.append(f"Error reading {tab.filename}: {error}")
        elif not tab.is_new_file:
            # File doesn't exist and no backup found
            tab.content = f"# File not found: {tab.filepath}\n# No backup available"
            session.errors.append(f"File not found: {tab.filepath}")

    return session


def get_all_backup_files(backup_dir: Optional[str] = None) -> List[TabInfo]:
    """
    Get all backup files as tabs, useful for browsing all backups.

    Args:
        backup_dir: Path to backup directory

    Returns:
        List of TabInfo objects for all backup files
    """
    if backup_dir is None:
        _, _, backup_dir = get_notepadpp_paths()

    if backup_dir is None or not os.path.exists(backup_dir):
        return []

    tabs = []
    backups = find_backup_files(backup_dir)

    for original_name, backup_list in backups.items():
        for backup in backup_list:
            content, _ = read_file_content(backup['path'])

            tab = TabInfo(
                filepath=backup['path'],
                filename=f"{original_name} ({backup['timestamp']})",
                content=content,
                is_backup=True,
                backup_path=backup['path']
            )
            tabs.append(tab)

    return tabs
