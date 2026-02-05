"""
Text Editor Component

A feature-rich text editor widget with line numbers, syntax highlighting,
and common text editing operations.
"""

import tkinter as tk
from tkinter import ttk, font
import re
from typing import Optional, Callable, Dict, List, Tuple


class LineNumbers(tk.Canvas):
    """Line numbers widget for text editor"""

    def __init__(self, parent, text_widget, **kwargs):
        super().__init__(parent, **kwargs)
        self.text_widget = text_widget
        self.font = font.Font(family='Consolas', size=10)
        self.configure(width=50, bg='#f0f0f0', highlightthickness=0)

    def redraw(self):
        """Redraw line numbers"""
        self.delete("all")

        # Get visible range
        first_visible = self.text_widget.index("@0,0")
        last_visible = self.text_widget.index(f"@0,{self.text_widget.winfo_height()}")

        first_line = int(first_visible.split('.')[0])
        last_line = int(last_visible.split('.')[0])

        # Draw line numbers
        for line_num in range(first_line, last_line + 1):
            dline = self.text_widget.dlineinfo(f"{line_num}.0")
            if dline:
                y = dline[1]
                self.create_text(
                    45, y,
                    anchor="ne",
                    text=str(line_num),
                    font=self.font,
                    fill='#666666'
                )


class TextEditor(ttk.Frame):
    """
    A full-featured text editor widget with:
    - Line numbers
    - Undo/redo support
    - Find and replace
    - Word wrap toggle
    - Status bar
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent)

        self.filepath: Optional[str] = None
        self.encoding: str = 'utf-8'
        self.modified: bool = False
        self._on_modified_callback: Optional[Callable] = None

        self._setup_ui()
        self._setup_bindings()

    def _setup_ui(self):
        """Set up the editor UI"""
        # Main container
        self.editor_frame = ttk.Frame(self)
        self.editor_frame.pack(fill=tk.BOTH, expand=True)

        # Line numbers
        self.line_numbers = LineNumbers(self.editor_frame, None)
        self.line_numbers.pack(side=tk.LEFT, fill=tk.Y)

        # Text widget with scrollbar
        text_frame = ttk.Frame(self.editor_frame)
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbars
        self.v_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scrollbar = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Text widget
        self.text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            undo=True,
            maxundo=-1,
            font=font.Font(family='Consolas', size=10),
            bg='white',
            fg='black',
            insertbackground='black',
            selectbackground='#0078d7',
            selectforeground='white',
            padx=5,
            pady=5,
            yscrollcommand=self._on_scroll_y,
            xscrollcommand=self.h_scrollbar.set
        )
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Connect scrollbars
        self.v_scrollbar.config(command=self._scroll_text)
        self.h_scrollbar.config(command=self.text.xview)

        # Update line numbers reference
        self.line_numbers.text_widget = self.text

        # Status bar
        self.status_frame = ttk.Frame(self)
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(
            self.status_frame,
            text="Ln 1, Col 1",
            anchor=tk.W,
            padding=(5, 2)
        )
        self.status_label.pack(side=tk.LEFT)

        self.encoding_label = ttk.Label(
            self.status_frame,
            text="UTF-8",
            anchor=tk.E,
            padding=(5, 2)
        )
        self.encoding_label.pack(side=tk.RIGHT)

        self.length_label = ttk.Label(
            self.status_frame,
            text="0 characters",
            anchor=tk.E,
            padding=(5, 2)
        )
        self.length_label.pack(side=tk.RIGHT)

    def _setup_bindings(self):
        """Set up keyboard and event bindings"""
        # Track modifications
        self.text.bind('<<Modified>>', self._on_text_modified)

        # Update line numbers and status on changes
        self.text.bind('<KeyRelease>', self._on_key_release)
        self.text.bind('<ButtonRelease-1>', self._update_status)
        self.text.bind('<Configure>', self._on_configure)

        # Standard keyboard shortcuts
        self.text.bind('<Control-a>', self._select_all)
        self.text.bind('<Control-A>', self._select_all)
        self.text.bind('<Control-d>', self._duplicate_line)
        self.text.bind('<Control-D>', self._duplicate_line)
        self.text.bind('<Control-l>', self._delete_line)
        self.text.bind('<Control-L>', self._delete_line)
        self.text.bind('<Control-Shift-Up>', self._move_line_up)
        self.text.bind('<Control-Shift-Down>', self._move_line_down)

    def _on_scroll_y(self, *args):
        """Handle vertical scroll"""
        self.v_scrollbar.set(*args)
        self.line_numbers.redraw()

    def _scroll_text(self, *args):
        """Scroll text and line numbers together"""
        self.text.yview(*args)
        self.line_numbers.redraw()

    def _on_configure(self, event=None):
        """Handle widget resize"""
        self.line_numbers.redraw()

    def _on_key_release(self, event=None):
        """Handle key release"""
        self.line_numbers.redraw()
        self._update_status()

    def _on_text_modified(self, event=None):
        """Handle text modification"""
        if self.text.edit_modified():
            self.modified = True
            if self._on_modified_callback:
                self._on_modified_callback()
            # Reset the modified flag for future changes
            self.text.edit_modified(False)

    def _update_status(self, event=None):
        """Update status bar"""
        cursor_pos = self.text.index(tk.INSERT)
        line, col = cursor_pos.split('.')
        self.status_label.config(text=f"Ln {line}, Col {int(col) + 1}")

        # Update character count
        content = self.text.get('1.0', tk.END)
        char_count = len(content) - 1  # Subtract trailing newline
        self.length_label.config(text=f"{char_count} characters")

    def _select_all(self, event=None):
        """Select all text"""
        self.text.tag_add(tk.SEL, '1.0', tk.END)
        self.text.mark_set(tk.INSERT, '1.0')
        self.text.see(tk.INSERT)
        return 'break'

    def _duplicate_line(self, event=None):
        """Duplicate current line"""
        line = self.text.index(tk.INSERT).split('.')[0]
        line_content = self.text.get(f'{line}.0', f'{line}.end')
        self.text.insert(f'{line}.end', f'\n{line_content}')
        return 'break'

    def _delete_line(self, event=None):
        """Delete current line"""
        line = self.text.index(tk.INSERT).split('.')[0]
        self.text.delete(f'{line}.0', f'{int(line) + 1}.0')
        return 'break'

    def _move_line_up(self, event=None):
        """Move current line up"""
        line = int(self.text.index(tk.INSERT).split('.')[0])
        if line > 1:
            current_line = self.text.get(f'{line}.0', f'{line}.end')
            self.text.delete(f'{line}.0', f'{int(line) + 1}.0')
            self.text.insert(f'{line - 1}.0', current_line + '\n')
            self.text.mark_set(tk.INSERT, f'{line - 1}.0')
        return 'break'

    def _move_line_down(self, event=None):
        """Move current line down"""
        line = int(self.text.index(tk.INSERT).split('.')[0])
        end_line = int(self.text.index(tk.END).split('.')[0])
        if line < end_line - 1:
            current_line = self.text.get(f'{line}.0', f'{line}.end')
            self.text.delete(f'{line}.0', f'{int(line) + 1}.0')
            self.text.insert(f'{line + 1}.0', current_line + '\n')
            self.text.mark_set(tk.INSERT, f'{line + 1}.0')
        return 'break'

    # Public API

    def get_content(self) -> str:
        """Get all text content"""
        return self.text.get('1.0', 'end-1c')

    def set_content(self, content: str):
        """Set text content"""
        self.text.delete('1.0', tk.END)
        self.text.insert('1.0', content)
        self.text.edit_reset()  # Clear undo stack
        self.text.edit_modified(False)
        self.modified = False
        self.line_numbers.redraw()
        self._update_status()

    def set_encoding(self, encoding: str):
        """Set encoding for display"""
        self.encoding = encoding
        self.encoding_label.config(text=encoding.upper())

    def set_on_modified(self, callback: Callable):
        """Set callback for when text is modified"""
        self._on_modified_callback = callback

    def set_word_wrap(self, enabled: bool):
        """Toggle word wrap"""
        self.text.configure(wrap=tk.WORD if enabled else tk.NONE)
        self.h_scrollbar.pack_forget() if enabled else self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    def goto_line(self, line_number: int):
        """Go to specific line"""
        self.text.mark_set(tk.INSERT, f'{line_number}.0')
        self.text.see(tk.INSERT)
        self._update_status()

    def find_text(self, pattern: str, case_sensitive: bool = False,
                  regex: bool = False, start: str = '1.0') -> Optional[Tuple[str, str]]:
        """
        Find text in editor

        Returns:
            Tuple of (start_index, end_index) if found, None otherwise
        """
        if not pattern:
            return None

        search_args = {'nocase': not case_sensitive}
        if regex:
            search_args['regexp'] = True

        start_pos = self.text.search(pattern, start, stopindex=tk.END, **search_args)
        if not start_pos:
            return None

        if regex:
            # For regex, we need to find the match length
            match = re.search(pattern, self.text.get(start_pos, tk.END),
                              0 if case_sensitive else re.IGNORECASE)
            if match:
                end_pos = f"{start_pos}+{len(match.group())}c"
            else:
                return None
        else:
            end_pos = f"{start_pos}+{len(pattern)}c"

        return start_pos, end_pos

    def replace_text(self, find_pattern: str, replace_with: str,
                     case_sensitive: bool = False, regex: bool = False) -> bool:
        """Replace current selection or find next"""
        # If text is selected and matches, replace it
        try:
            sel_start = self.text.index(tk.SEL_FIRST)
            sel_end = self.text.index(tk.SEL_LAST)
            selected = self.text.get(sel_start, sel_end)

            if case_sensitive:
                matches = selected == find_pattern
            else:
                matches = selected.lower() == find_pattern.lower()

            if matches:
                self.text.delete(sel_start, sel_end)
                self.text.insert(sel_start, replace_with)
                return True
        except tk.TclError:
            pass

        # Find next occurrence
        result = self.find_text(find_pattern, case_sensitive, regex)
        if result:
            self.text.tag_remove(tk.SEL, '1.0', tk.END)
            self.text.tag_add(tk.SEL, result[0], result[1])
            self.text.mark_set(tk.INSERT, result[1])
            self.text.see(result[0])
            return True
        return False

    def replace_all(self, find_pattern: str, replace_with: str,
                    case_sensitive: bool = False, regex: bool = False) -> int:
        """Replace all occurrences"""
        count = 0
        start = '1.0'

        while True:
            result = self.find_text(find_pattern, case_sensitive, regex, start)
            if not result:
                break

            self.text.delete(result[0], result[1])
            self.text.insert(result[0], replace_with)
            start = f"{result[0]}+{len(replace_with)}c"
            count += 1

        return count

    def insert_text(self, text: str, position: Optional[str] = None):
        """Insert text at position (default: cursor)"""
        if position is None:
            position = tk.INSERT
        self.text.insert(position, text)

    def get_selected_text(self) -> Optional[str]:
        """Get currently selected text"""
        try:
            return self.text.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return None

    def focus(self):
        """Set focus to text widget"""
        self.text.focus_set()
