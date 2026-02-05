"""
Notepad++ Replica - Main Application

A portable text editor with Notepad++ session recovery capabilities.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, font
import os
import sys
from typing import Optional, List, Dict
from dataclasses import dataclass

from .text_editor import TextEditor
from .session_parser import (
    recover_session, get_notepadpp_paths, TabInfo, SessionData,
    get_all_backup_files, read_file_content
)


@dataclass
class Tab:
    """Represents an open tab"""
    editor: TextEditor
    filepath: Optional[str]
    filename: str
    modified: bool = False
    is_new: bool = True
    encoding: str = 'utf-8'


class FindReplaceDialog(tk.Toplevel):
    """Find and Replace dialog"""

    def __init__(self, parent, editor: TextEditor):
        super().__init__(parent)
        self.editor = editor
        self.title("Find and Replace")
        self.geometry("450x200")
        self.resizable(False, False)
        self.transient(parent)

        self._setup_ui()
        self.find_entry.focus_set()

    def _setup_ui(self):
        # Find row
        find_frame = ttk.Frame(self, padding=10)
        find_frame.pack(fill=tk.X)

        ttk.Label(find_frame, text="Find:").pack(side=tk.LEFT)
        self.find_entry = ttk.Entry(find_frame, width=40)
        self.find_entry.pack(side=tk.LEFT, padx=5)

        # Replace row
        replace_frame = ttk.Frame(self, padding=10)
        replace_frame.pack(fill=tk.X)

        ttk.Label(replace_frame, text="Replace:").pack(side=tk.LEFT)
        self.replace_entry = ttk.Entry(replace_frame, width=40)
        self.replace_entry.pack(side=tk.LEFT, padx=5)

        # Options
        options_frame = ttk.Frame(self, padding=10)
        options_frame.pack(fill=tk.X)

        self.case_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Case sensitive",
                        variable=self.case_var).pack(side=tk.LEFT)

        self.regex_var = tk.BooleanVar()
        ttk.Checkbutton(options_frame, text="Regex",
                        variable=self.regex_var).pack(side=tk.LEFT, padx=10)

        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Find Next",
                   command=self._find_next).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Replace",
                   command=self._replace).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Replace All",
                   command=self._replace_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="Close",
                   command=self.destroy).pack(side=tk.RIGHT, padx=2)

        # Bind Enter key
        self.find_entry.bind('<Return>', lambda e: self._find_next())

    def _find_next(self):
        pattern = self.find_entry.get()
        if pattern:
            result = self.editor.find_text(
                pattern,
                self.case_var.get(),
                self.regex_var.get()
            )
            if result:
                self.editor.text.tag_remove(tk.SEL, '1.0', tk.END)
                self.editor.text.tag_add(tk.SEL, result[0], result[1])
                self.editor.text.mark_set(tk.INSERT, result[1])
                self.editor.text.see(result[0])
            else:
                messagebox.showinfo("Find", "No matches found")

    def _replace(self):
        find_pattern = self.find_entry.get()
        replace_with = self.replace_entry.get()
        if find_pattern:
            self.editor.replace_text(
                find_pattern, replace_with,
                self.case_var.get(), self.regex_var.get()
            )

    def _replace_all(self):
        find_pattern = self.find_entry.get()
        replace_with = self.replace_entry.get()
        if find_pattern:
            count = self.editor.replace_all(
                find_pattern, replace_with,
                self.case_var.get(), self.regex_var.get()
            )
            messagebox.showinfo("Replace All", f"Replaced {count} occurrences")


class GoToLineDialog(simpledialog.Dialog):
    """Go to line dialog"""

    def __init__(self, parent, max_line: int):
        self.max_line = max_line
        self.result = None
        super().__init__(parent, title="Go to Line")

    def body(self, master):
        ttk.Label(master, text=f"Line number (1 - {self.max_line}):").grid(row=0, column=0, pady=5)
        self.entry = ttk.Entry(master, width=20)
        self.entry.grid(row=0, column=1, padx=5, pady=5)
        return self.entry

    def apply(self):
        try:
            self.result = int(self.entry.get())
        except ValueError:
            self.result = None


class NotepadReplica(tk.Tk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.title("Notepad++ Replica")
        self.geometry("1200x800")

        # Application state
        self.tabs: Dict[str, Tab] = {}  # tab_id -> Tab
        self.new_file_counter = 1
        self.word_wrap_enabled = False
        self.current_find_dialog: Optional[FindReplaceDialog] = None

        # Set up UI
        self._setup_styles()
        self._setup_menu()
        self._setup_toolbar()
        self._setup_notebook()
        self._setup_statusbar()
        self._setup_bindings()

        # Set app icon (if available)
        try:
            self.iconbitmap('icon.ico')
        except:
            pass

        # Start with a new tab
        self.new_file()

    def _setup_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')

        # Tab style
        style.configure('TNotebook.Tab', padding=[10, 5])

    def _setup_menu(self):
        """Set up menu bar"""
        self.menubar = tk.Menu(self)
        self.config(menu=self.menubar)

        # File menu
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self.new_file, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Open Folder...", command=self.open_folder)
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self.save_file_as, accelerator="Ctrl+Shift+S")
        file_menu.add_command(label="Save All", command=self.save_all, accelerator="Ctrl+Shift+A")
        file_menu.add_separator()
        file_menu.add_command(label="Close", command=self.close_current_tab, accelerator="Ctrl+W")
        file_menu.add_command(label="Close All", command=self.close_all_tabs)
        file_menu.add_separator()
        file_menu.add_command(label="Recover Notepad++ Session", command=self.recover_notepadpp_session)
        file_menu.add_command(label="Browse Notepad++ Backups", command=self.browse_notepadpp_backups)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app, accelerator="Alt+F4")

        # Edit menu
        edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", command=self.cut, accelerator="Ctrl+X")
        edit_menu.add_command(label="Copy", command=self.copy, accelerator="Ctrl+C")
        edit_menu.add_command(label="Paste", command=self.paste, accelerator="Ctrl+V")
        edit_menu.add_command(label="Delete", command=self.delete)
        edit_menu.add_separator()
        edit_menu.add_command(label="Select All", command=self.select_all, accelerator="Ctrl+A")
        edit_menu.add_separator()
        edit_menu.add_command(label="Duplicate Line", command=self.duplicate_line, accelerator="Ctrl+D")
        edit_menu.add_command(label="Delete Line", command=self.delete_line, accelerator="Ctrl+L")

        # Search menu
        search_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Search", menu=search_menu)
        search_menu.add_command(label="Find...", command=self.show_find_dialog, accelerator="Ctrl+F")
        search_menu.add_command(label="Find & Replace...", command=self.show_find_dialog, accelerator="Ctrl+H")
        search_menu.add_separator()
        search_menu.add_command(label="Go to Line...", command=self.goto_line, accelerator="Ctrl+G")

        # View menu
        view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=view_menu)

        self.word_wrap_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(label="Word Wrap", variable=self.word_wrap_var,
                                   command=self.toggle_word_wrap)

        view_menu.add_separator()
        view_menu.add_command(label="Zoom In", command=lambda: self.zoom(1), accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=lambda: self.zoom(-1), accelerator="Ctrl+-")
        view_menu.add_command(label="Reset Zoom", command=lambda: self.zoom(0), accelerator="Ctrl+0")

        # Encoding menu
        encoding_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Encoding", menu=encoding_menu)

        self.encoding_var = tk.StringVar(value='utf-8')
        for enc in ['UTF-8', 'UTF-8 BOM', 'UTF-16', 'ANSI (Windows-1252)', 'ISO-8859-1']:
            encoding_menu.add_radiobutton(label=enc, variable=self.encoding_var,
                                           value=enc.lower().replace(' ', '-').replace('(', '').replace(')', ''))

        # Help menu
        help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)
        help_menu.add_command(label="Keyboard Shortcuts", command=self.show_shortcuts)

    def _setup_toolbar(self):
        """Set up toolbar"""
        toolbar = ttk.Frame(self, padding=2)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Toolbar buttons
        ttk.Button(toolbar, text="New", command=self.new_file, width=6).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="Open", command=self.open_file, width=6).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="Save", command=self.save_file, width=6).pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        ttk.Button(toolbar, text="Undo", command=self.undo, width=6).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="Redo", command=self.redo, width=6).pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        ttk.Button(toolbar, text="Find", command=self.show_find_dialog, width=6).pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Recovery button (highlighted)
        recovery_btn = ttk.Button(toolbar, text="Recover Notepad++", command=self.recover_notepadpp_session)
        recovery_btn.pack(side=tk.LEFT, padx=5)

    def _setup_notebook(self):
        """Set up the tabbed notebook"""
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bind tab change event
        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

        # Bind middle-click to close tab
        self.notebook.bind('<Button-2>', self._on_middle_click)

        # Right-click menu for tabs
        self.tab_menu = tk.Menu(self, tearoff=0)
        self.tab_menu.add_command(label="Close", command=self.close_current_tab)
        self.tab_menu.add_command(label="Close Others", command=self.close_other_tabs)
        self.tab_menu.add_command(label="Close All", command=self.close_all_tabs)
        self.tab_menu.add_separator()
        self.tab_menu.add_command(label="Copy Path", command=self._copy_current_path)

        self.notebook.bind('<Button-3>', self._show_tab_menu)

    def _setup_statusbar(self):
        """Set up status bar"""
        self.statusbar = ttk.Frame(self, padding=2)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_text = ttk.Label(self.statusbar, text="Ready")
        self.status_text.pack(side=tk.LEFT)

        self.tab_count_label = ttk.Label(self.statusbar, text="Tabs: 0")
        self.tab_count_label.pack(side=tk.RIGHT, padx=10)

    def _setup_bindings(self):
        """Set up global keyboard bindings"""
        self.bind('<Control-n>', lambda e: self.new_file())
        self.bind('<Control-N>', lambda e: self.new_file())
        self.bind('<Control-o>', lambda e: self.open_file())
        self.bind('<Control-O>', lambda e: self.open_file())
        self.bind('<Control-s>', lambda e: self.save_file())
        self.bind('<Control-S>', lambda e: self.save_file())
        self.bind('<Control-Shift-s>', lambda e: self.save_file_as())
        self.bind('<Control-Shift-S>', lambda e: self.save_file_as())
        self.bind('<Control-w>', lambda e: self.close_current_tab())
        self.bind('<Control-W>', lambda e: self.close_current_tab())
        self.bind('<Control-f>', lambda e: self.show_find_dialog())
        self.bind('<Control-F>', lambda e: self.show_find_dialog())
        self.bind('<Control-h>', lambda e: self.show_find_dialog())
        self.bind('<Control-H>', lambda e: self.show_find_dialog())
        self.bind('<Control-g>', lambda e: self.goto_line())
        self.bind('<Control-G>', lambda e: self.goto_line())
        self.bind('<Control-plus>', lambda e: self.zoom(1))
        self.bind('<Control-minus>', lambda e: self.zoom(-1))
        self.bind('<Control-0>', lambda e: self.zoom(0))
        self.bind('<Control-Tab>', lambda e: self._next_tab())
        self.bind('<Control-Shift-Tab>', lambda e: self._prev_tab())

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

    def _get_current_tab(self) -> Optional[Tab]:
        """Get the currently active tab"""
        tab_id = self.notebook.select()
        return self.tabs.get(tab_id)

    def _get_current_editor(self) -> Optional[TextEditor]:
        """Get the editor of the current tab"""
        tab = self._get_current_tab()
        return tab.editor if tab else None

    def _update_tab_title(self, tab_id: str):
        """Update tab title to reflect modified state"""
        tab = self.tabs.get(tab_id)
        if tab:
            title = tab.filename
            if tab.modified:
                title = f"*{title}"
            self.notebook.tab(tab_id, text=title)

    def _update_status(self):
        """Update status bar"""
        self.tab_count_label.config(text=f"Tabs: {len(self.tabs)}")

    def _on_tab_changed(self, event=None):
        """Handle tab change event"""
        tab = self._get_current_tab()
        if tab:
            self.title(f"{tab.filename} - Notepad++ Replica")
            self.encoding_var.set(tab.encoding.lower())

    def _on_middle_click(self, event):
        """Close tab on middle click"""
        try:
            index = self.notebook.index(f"@{event.x},{event.y}")
            tab_id = self.notebook.tabs()[index]
            self._close_tab(tab_id)
        except:
            pass

    def _show_tab_menu(self, event):
        """Show right-click menu for tabs"""
        try:
            index = self.notebook.index(f"@{event.x},{event.y}")
            self.notebook.select(index)
            self.tab_menu.tk_popup(event.x_root, event.y_root)
        except:
            pass

    def _copy_current_path(self):
        """Copy current file path to clipboard"""
        tab = self._get_current_tab()
        if tab and tab.filepath:
            self.clipboard_clear()
            self.clipboard_append(tab.filepath)
            self.status_text.config(text="Path copied to clipboard")

    def _next_tab(self):
        """Switch to next tab"""
        current = self.notebook.index(self.notebook.select())
        total = len(self.notebook.tabs())
        if total > 1:
            self.notebook.select((current + 1) % total)

    def _prev_tab(self):
        """Switch to previous tab"""
        current = self.notebook.index(self.notebook.select())
        total = len(self.notebook.tabs())
        if total > 1:
            self.notebook.select((current - 1) % total)

    # File operations

    def new_file(self):
        """Create a new empty tab"""
        editor = TextEditor(self.notebook)
        filename = f"new {self.new_file_counter}"
        self.new_file_counter += 1

        tab_id = self.notebook.add(editor, text=filename)
        self.notebook.select(editor)

        tab = Tab(
            editor=editor,
            filepath=None,
            filename=filename,
            is_new=True
        )

        # Get the actual tab ID
        actual_tab_id = str(editor)
        self.tabs[actual_tab_id] = tab

        # Set up modification callback
        def on_modified():
            tab.modified = True
            self._update_tab_title(actual_tab_id)

        editor.set_on_modified(on_modified)
        editor.focus()

        self._update_status()
        return actual_tab_id

    def open_file(self, filepath: str = None):
        """Open a file"""
        if filepath is None:
            filepath = filedialog.askopenfilename(
                title="Open File",
                filetypes=[
                    ("All Files", "*.*"),
                    ("Text Files", "*.txt"),
                    ("Python Files", "*.py"),
                    ("JavaScript Files", "*.js"),
                    ("HTML Files", "*.html"),
                    ("CSS Files", "*.css"),
                    ("JSON Files", "*.json"),
                    ("XML Files", "*.xml"),
                    ("Markdown Files", "*.md"),
                ]
            )

        if not filepath:
            return

        # Check if file is already open
        for tab_id, tab in self.tabs.items():
            if tab.filepath and os.path.normpath(tab.filepath) == os.path.normpath(filepath):
                self.notebook.select(tab_id)
                return

        # Read file content
        content, error = read_file_content(filepath)
        if error:
            messagebox.showerror("Error", f"Could not open file:\n{error}")
            return

        # Create new tab
        editor = TextEditor(self.notebook)
        filename = os.path.basename(filepath)

        self.notebook.add(editor, text=filename)
        self.notebook.select(editor)

        tab = Tab(
            editor=editor,
            filepath=filepath,
            filename=filename,
            is_new=False
        )

        actual_tab_id = str(editor)
        self.tabs[actual_tab_id] = tab

        # Set content
        editor.set_content(content or '')

        # Set up modification callback
        def on_modified():
            tab.modified = True
            self._update_tab_title(actual_tab_id)

        editor.set_on_modified(on_modified)
        editor.focus()

        self._update_status()
        self.status_text.config(text=f"Opened: {filepath}")

    def open_folder(self):
        """Open all files in a folder"""
        folder = filedialog.askdirectory(title="Open Folder")
        if not folder:
            return

        count = 0
        for entry in os.listdir(folder):
            filepath = os.path.join(folder, entry)
            if os.path.isfile(filepath):
                # Only open text-like files
                ext = os.path.splitext(entry)[1].lower()
                text_extensions = ['.txt', '.py', '.js', '.html', '.css', '.json',
                                   '.xml', '.md', '.yml', '.yaml', '.ini', '.cfg',
                                   '.sh', '.bat', '.ps1', '.sql', '.log', '.csv']
                if ext in text_extensions or not ext:
                    self.open_file(filepath)
                    count += 1

        self.status_text.config(text=f"Opened {count} files from {folder}")

    def save_file(self):
        """Save current file"""
        tab = self._get_current_tab()
        if not tab:
            return

        if tab.is_new or not tab.filepath:
            self.save_file_as()
        else:
            self._save_to_file(tab, tab.filepath)

    def save_file_as(self):
        """Save current file with new name"""
        tab = self._get_current_tab()
        if not tab:
            return

        filepath = filedialog.asksaveasfilename(
            title="Save As",
            defaultextension=".txt",
            initialfile=tab.filename,
            filetypes=[
                ("All Files", "*.*"),
                ("Text Files", "*.txt"),
                ("Python Files", "*.py"),
                ("JavaScript Files", "*.js"),
                ("HTML Files", "*.html"),
                ("CSS Files", "*.css"),
                ("JSON Files", "*.json"),
            ]
        )

        if filepath:
            self._save_to_file(tab, filepath)

    def _save_to_file(self, tab: Tab, filepath: str):
        """Save tab content to file"""
        try:
            content = tab.editor.get_content()
            encoding = tab.encoding

            with open(filepath, 'w', encoding=encoding) as f:
                f.write(content)

            # Update tab info
            tab.filepath = filepath
            tab.filename = os.path.basename(filepath)
            tab.is_new = False
            tab.modified = False

            # Update tab title
            tab_id = str(tab.editor)
            self.notebook.tab(tab_id, text=tab.filename)

            self.status_text.config(text=f"Saved: {filepath}")

        except Exception as e:
            messagebox.showerror("Error", f"Could not save file:\n{e}")

    def save_all(self):
        """Save all modified files"""
        saved = 0
        for tab_id, tab in self.tabs.items():
            if tab.modified:
                if tab.is_new or not tab.filepath:
                    # Can't auto-save new files
                    continue
                self._save_to_file(tab, tab.filepath)
                saved += 1

        self.status_text.config(text=f"Saved {saved} files")

    def _close_tab(self, tab_id: str) -> bool:
        """Close a specific tab"""
        tab = self.tabs.get(tab_id)
        if not tab:
            return True

        # Check for unsaved changes
        if tab.modified:
            result = messagebox.askyesnocancel(
                "Unsaved Changes",
                f"Do you want to save changes to {tab.filename}?"
            )
            if result is None:  # Cancel
                return False
            elif result:  # Yes
                self.notebook.select(tab_id)
                self.save_file()
                if tab.modified:  # Save was cancelled
                    return False

        # Remove tab
        self.notebook.forget(tab_id)
        del self.tabs[tab_id]

        self._update_status()

        # If no tabs left, create a new one
        if not self.tabs:
            self.new_file()

        return True

    def close_current_tab(self):
        """Close the current tab"""
        tab_id = self.notebook.select()
        if tab_id:
            self._close_tab(tab_id)

    def close_other_tabs(self):
        """Close all tabs except current"""
        current_id = self.notebook.select()
        for tab_id in list(self.tabs.keys()):
            if tab_id != current_id:
                if not self._close_tab(tab_id):
                    break

    def close_all_tabs(self):
        """Close all tabs"""
        for tab_id in list(self.tabs.keys()):
            if not self._close_tab(tab_id):
                break

    # Session recovery

    def recover_notepadpp_session(self):
        """Recover tabs from Notepad++ session"""
        npp_dir, session_file, backup_dir = get_notepadpp_paths()

        if not session_file or not os.path.exists(session_file):
            # Ask user to locate session file
            session_file = filedialog.askopenfilename(
                title="Locate Notepad++ session.xml",
                filetypes=[("XML Files", "*.xml"), ("All Files", "*.*")],
                initialdir=os.environ.get('APPDATA', '')
            )
            if not session_file:
                messagebox.showinfo(
                    "Recovery",
                    "Could not find Notepad++ session file.\n\n"
                    "Please locate your session.xml file manually.\n"
                    "It's usually in: %APPDATA%\\Notepad++"
                )
                return

            # Derive backup dir from session file location
            backup_dir = os.path.join(os.path.dirname(session_file), 'backup')

        # Show progress
        self.status_text.config(text="Recovering Notepad++ session...")
        self.update()

        # Recover session
        session = recover_session(session_file, backup_dir)

        if session.errors:
            for error in session.errors[:5]:  # Show first 5 errors
                print(f"Warning: {error}")

        if not session.tabs:
            messagebox.showinfo(
                "Recovery",
                "No tabs found in Notepad++ session.\n\n"
                f"Session file: {session_file}"
            )
            return

        # Close default new tab if empty
        if len(self.tabs) == 1:
            tab = self._get_current_tab()
            if tab and tab.is_new and not tab.modified:
                tab_id = self.notebook.select()
                self.notebook.forget(tab_id)
                del self.tabs[tab_id]

        # Create tabs for recovered files
        recovered = 0
        for tab_info in session.tabs:
            editor = TextEditor(self.notebook)

            # Determine display name
            if tab_info.is_backup:
                display_name = f"{tab_info.filename} (recovered)"
            else:
                display_name = tab_info.filename

            self.notebook.add(editor, text=display_name)

            tab = Tab(
                editor=editor,
                filepath=tab_info.filepath if not tab_info.is_new_file else None,
                filename=tab_info.filename,
                is_new=tab_info.is_new_file,
                encoding=tab_info.encoding
            )

            actual_tab_id = str(editor)
            self.tabs[actual_tab_id] = tab

            # Set content
            if tab_info.content:
                editor.set_content(tab_info.content)
                if tab_info.is_backup:
                    tab.modified = True
                    self._update_tab_title(actual_tab_id)
            else:
                editor.set_content(f"# Could not recover content for: {tab_info.filepath}")

            # Set encoding
            editor.set_encoding(tab_info.encoding)

            # Set up modification callback
            def on_modified(t=tab, tid=actual_tab_id):
                t.modified = True
                self._update_tab_title(tid)

            editor.set_on_modified(on_modified)
            recovered += 1

        # Select first recovered tab
        if self.tabs:
            first_tab = list(self.tabs.values())[0]
            self.notebook.select(str(first_tab.editor))

        self._update_status()
        self.status_text.config(text=f"Recovered {recovered} tabs from Notepad++")

        messagebox.showinfo(
            "Recovery Complete",
            f"Successfully recovered {recovered} tabs from Notepad++!\n\n"
            f"Session file: {session_file}\n"
            f"Backup directory: {backup_dir}\n\n"
            "Note: Unsaved changes are marked with *"
        )

    def browse_notepadpp_backups(self):
        """Browse all Notepad++ backup files"""
        _, _, backup_dir = get_notepadpp_paths()

        if not backup_dir or not os.path.exists(backup_dir):
            backup_dir = filedialog.askdirectory(
                title="Locate Notepad++ backup folder",
                initialdir=os.environ.get('APPDATA', '')
            )
            if not backup_dir:
                return

        # Get all backup files
        tabs = get_all_backup_files(backup_dir)

        if not tabs:
            messagebox.showinfo("Backups", "No backup files found.")
            return

        # Create tabs for backup files
        for tab_info in tabs:
            editor = TextEditor(self.notebook)
            self.notebook.add(editor, text=tab_info.filename)

            tab = Tab(
                editor=editor,
                filepath=tab_info.backup_path,
                filename=tab_info.filename,
                is_new=True
            )

            actual_tab_id = str(editor)
            self.tabs[actual_tab_id] = tab

            if tab_info.content:
                editor.set_content(tab_info.content)

            def on_modified(t=tab, tid=actual_tab_id):
                t.modified = True
                self._update_tab_title(tid)

            editor.set_on_modified(on_modified)

        self._update_status()
        self.status_text.config(text=f"Loaded {len(tabs)} backup files")

    # Edit operations

    def undo(self):
        """Undo last edit"""
        editor = self._get_current_editor()
        if editor:
            try:
                editor.text.edit_undo()
            except tk.TclError:
                pass

    def redo(self):
        """Redo last undone edit"""
        editor = self._get_current_editor()
        if editor:
            try:
                editor.text.edit_redo()
            except tk.TclError:
                pass

    def cut(self):
        """Cut selection"""
        editor = self._get_current_editor()
        if editor:
            editor.text.event_generate('<<Cut>>')

    def copy(self):
        """Copy selection"""
        editor = self._get_current_editor()
        if editor:
            editor.text.event_generate('<<Copy>>')

    def paste(self):
        """Paste from clipboard"""
        editor = self._get_current_editor()
        if editor:
            editor.text.event_generate('<<Paste>>')

    def delete(self):
        """Delete selection"""
        editor = self._get_current_editor()
        if editor:
            try:
                editor.text.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass

    def select_all(self):
        """Select all text"""
        editor = self._get_current_editor()
        if editor:
            editor._select_all()

    def duplicate_line(self):
        """Duplicate current line"""
        editor = self._get_current_editor()
        if editor:
            editor._duplicate_line()

    def delete_line(self):
        """Delete current line"""
        editor = self._get_current_editor()
        if editor:
            editor._delete_line()

    # Search operations

    def show_find_dialog(self):
        """Show find and replace dialog"""
        editor = self._get_current_editor()
        if editor:
            if self.current_find_dialog:
                self.current_find_dialog.destroy()
            self.current_find_dialog = FindReplaceDialog(self, editor)

    def goto_line(self):
        """Go to specific line"""
        editor = self._get_current_editor()
        if editor:
            content = editor.get_content()
            max_line = content.count('\n') + 1
            dialog = GoToLineDialog(self, max_line)
            if dialog.result and 1 <= dialog.result <= max_line:
                editor.goto_line(dialog.result)

    # View operations

    def toggle_word_wrap(self):
        """Toggle word wrap"""
        self.word_wrap_enabled = self.word_wrap_var.get()
        for tab in self.tabs.values():
            tab.editor.set_word_wrap(self.word_wrap_enabled)

    def zoom(self, direction: int):
        """Zoom text (direction: 1=in, -1=out, 0=reset)"""
        for tab in self.tabs.values():
            current_font = font.Font(font=tab.editor.text['font'])
            current_size = current_font.actual()['size']

            if direction == 0:
                new_size = 10
            else:
                new_size = max(6, min(72, current_size + (2 * direction)))

            new_font = font.Font(family='Consolas', size=new_size)
            tab.editor.text.configure(font=new_font)
            tab.editor.line_numbers.font = new_font

    # Help

    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            "About",
            "Notepad++ Replica v1.0.0\n\n"
            "A portable text editor with Notepad++ session recovery.\n\n"
            "Features:\n"
            "- Recover open tabs from Notepad++\n"
            "- Recover unsaved backup files\n"
            "- Full text editing capabilities\n"
            "- Find and Replace\n"
            "- Multiple tabs support\n\n"
            "Created to help users transition from Notepad++"
        )

    def show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
Keyboard Shortcuts:

File:
  Ctrl+N         New file
  Ctrl+O         Open file
  Ctrl+S         Save
  Ctrl+Shift+S   Save As
  Ctrl+W         Close tab

Edit:
  Ctrl+Z         Undo
  Ctrl+Y         Redo
  Ctrl+A         Select All
  Ctrl+D         Duplicate line
  Ctrl+L         Delete line
  Ctrl+Shift+Up  Move line up
  Ctrl+Shift+Down Move line down

Search:
  Ctrl+F         Find
  Ctrl+H         Find & Replace
  Ctrl+G         Go to line

View:
  Ctrl++         Zoom in
  Ctrl+-         Zoom out
  Ctrl+0         Reset zoom

Navigation:
  Ctrl+Tab       Next tab
  Ctrl+Shift+Tab Previous tab
"""
        messagebox.showinfo("Keyboard Shortcuts", shortcuts)

    def quit_app(self):
        """Quit application"""
        # Check for unsaved changes
        for tab in self.tabs.values():
            if tab.modified:
                result = messagebox.askyesnocancel(
                    "Unsaved Changes",
                    "You have unsaved changes. Save before exit?"
                )
                if result is None:  # Cancel
                    return
                elif result:  # Yes
                    self.save_all()
                break

        self.destroy()


def main():
    """Main entry point"""
    app = NotepadReplica()
    app.mainloop()


if __name__ == '__main__':
    main()
