"""
Basic Syntax Highlighting

Provides simple syntax highlighting for common file types.
"""

import tkinter as tk
import re
from typing import Dict, List, Tuple


# Language definitions: pattern -> tag name
LANGUAGES = {
    'python': {
        'keywords': r'\b(def|class|if|elif|else|for|while|try|except|finally|with|as|import|from|return|yield|raise|pass|break|continue|and|or|not|in|is|None|True|False|lambda|global|nonlocal|assert|async|await)\b',
        'strings': r'(\"\"\"[\s\S]*?\"\"\"|\'\'\'[\s\S]*?\'\'\'|\"[^\"]*\"|\'[^\']*\')',
        'comments': r'#.*$',
        'numbers': r'\b\d+\.?\d*\b',
        'functions': r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
        'decorators': r'@\w+',
    },
    'javascript': {
        'keywords': r'\b(function|var|let|const|if|else|for|while|do|switch|case|break|continue|return|try|catch|finally|throw|new|class|extends|import|export|from|default|async|await|typeof|instanceof|this|null|undefined|true|false)\b',
        'strings': r'(`[\s\S]*?`|\"[^\"]*\"|\'[^\']*\')',
        'comments': r'(//.*$|/\*[\s\S]*?\*/)',
        'numbers': r'\b\d+\.?\d*\b',
        'functions': r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    },
    'html': {
        'tags': r'</?[a-zA-Z][a-zA-Z0-9]*',
        'attributes': r'\s([a-zA-Z-]+)=',
        'strings': r'\"[^\"]*\"|\'[^\']*\'',
        'comments': r'<!--[\s\S]*?-->',
    },
    'css': {
        'selectors': r'^[.#]?[a-zA-Z][a-zA-Z0-9_-]*',
        'properties': r'([a-zA-Z-]+)\s*:',
        'values': r':\s*([^;]+)',
        'comments': r'/\*[\s\S]*?\*/',
    },
    'json': {
        'keys': r'\"([^\"]+)\"\s*:',
        'strings': r':\s*\"[^\"]*\"',
        'numbers': r':\s*-?\d+\.?\d*',
        'booleans': r'\b(true|false|null)\b',
    },
    'sql': {
        'keywords': r'\b(SELECT|FROM|WHERE|AND|OR|INSERT|INTO|VALUES|UPDATE|SET|DELETE|CREATE|TABLE|INDEX|DROP|ALTER|JOIN|LEFT|RIGHT|INNER|OUTER|ON|GROUP|BY|ORDER|ASC|DESC|LIMIT|OFFSET|HAVING|UNION|AS|DISTINCT|COUNT|SUM|AVG|MIN|MAX|NULL|NOT|IN|LIKE|BETWEEN|EXISTS|CASE|WHEN|THEN|ELSE|END)\b',
        'strings': r'\'[^\']*\'',
        'comments': r'(--.*$|/\*[\s\S]*?\*/)',
        'numbers': r'\b\d+\.?\d*\b',
    },
}

# Color schemes for different token types
COLORS = {
    'keywords': '#0000FF',      # Blue
    'strings': '#008000',       # Green
    'comments': '#808080',      # Gray
    'numbers': '#FF8C00',       # Dark Orange
    'functions': '#800080',     # Purple
    'decorators': '#FF00FF',    # Magenta
    'tags': '#800000',          # Maroon
    'attributes': '#FF0000',    # Red
    'selectors': '#0000FF',     # Blue
    'properties': '#FF0000',    # Red
    'values': '#008000',        # Green
    'keys': '#800080',          # Purple
    'booleans': '#0000FF',      # Blue
}


def detect_language(filename: str) -> str:
    """Detect language from filename extension"""
    ext_map = {
        '.py': 'python',
        '.pyw': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'javascript',
        '.tsx': 'javascript',
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'html',
        '.css': 'css',
        '.scss': 'css',
        '.less': 'css',
        '.json': 'json',
        '.sql': 'sql',
    }

    import os
    _, ext = os.path.splitext(filename.lower())
    return ext_map.get(ext, 'text')


class SyntaxHighlighter:
    """Applies syntax highlighting to a text widget"""

    def __init__(self, text_widget: tk.Text, language: str = 'text'):
        self.text = text_widget
        self.language = language
        self._setup_tags()

    def _setup_tags(self):
        """Set up text tags for highlighting"""
        for tag_name, color in COLORS.items():
            self.text.tag_configure(tag_name, foreground=color)

        # Configure tag priority (later tags override earlier ones)
        for tag_name in COLORS.keys():
            self.text.tag_raise(tag_name)

    def set_language(self, language: str):
        """Set the highlighting language"""
        self.language = language

    def highlight(self, start: str = '1.0', end: str = tk.END):
        """Apply syntax highlighting to the specified range"""
        if self.language not in LANGUAGES:
            return

        # Remove existing tags
        for tag_name in COLORS.keys():
            self.text.tag_remove(tag_name, start, end)

        # Get content
        content = self.text.get(start, end)

        # Apply patterns
        patterns = LANGUAGES[self.language]

        for token_type, pattern in patterns.items():
            self._apply_pattern(content, pattern, token_type, start)

    def _apply_pattern(self, content: str, pattern: str, tag_name: str, base_index: str):
        """Apply a regex pattern and tag matches"""
        try:
            flags = re.MULTILINE | re.IGNORECASE if tag_name == 'keywords' else re.MULTILINE
            for match in re.finditer(pattern, content, flags):
                start_pos = f"{base_index}+{match.start()}c"
                end_pos = f"{base_index}+{match.end()}c"
                self.text.tag_add(tag_name, start_pos, end_pos)
        except re.error:
            pass

    def highlight_line(self, line_num: int):
        """Highlight a single line (for incremental updates)"""
        start = f"{line_num}.0"
        end = f"{line_num}.end"
        self.highlight(start, end)
