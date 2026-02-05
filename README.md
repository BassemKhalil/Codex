# Notepad++ Replica

A portable text editor with **Notepad++ session recovery** - designed to help you recover and continue working with your open Notepad++ tabs after it's been removed.

## Features

- **Session Recovery**: Automatically recovers all your open Notepad++ tabs
- **Backup Recovery**: Retrieves unsaved content from Notepad++ backup files
- **Tabbed Interface**: Familiar multi-tab editing experience
- **Portable**: Single executable, no installation required
- **Full Text Editing**:
  - Find and Replace (with regex support)
  - Line numbers
  - Word wrap toggle
  - Go to line
  - Undo/Redo
  - Zoom in/out
- **Keyboard Shortcuts**: Same shortcuts you're used to from Notepad++

## Quick Start

### Option 1: Run directly with Python

```bash
# Launch the editor
python notepad_replica.py

# Auto-recover Notepad++ session on startup
python notepad_replica.py --recover

# Open specific files
python notepad_replica.py document.txt script.py
```

### Option 2: Build a portable executable

```bash
# Windows
build.bat

# Linux/Mac
chmod +x build.sh
./build.sh
```

This creates `dist/NotepadReplica.exe` - a single portable file you can copy anywhere.

## Recovering Your Notepad++ Tabs

1. Launch the application
2. Click **"Recover Notepad++"** button in the toolbar, or go to **File → Recover Notepad++ Session**
3. The application will automatically find and recover:
   - All your open tabs from the session file
   - Unsaved content from backup files
4. Recovered tabs with unsaved changes will be marked with `*`

### Manual Recovery

If automatic detection doesn't work, you can manually locate your Notepad++ files:

- **Session file**: Usually at `%APPDATA%\Notepad++\session.xml`
- **Backup folder**: Usually at `%APPDATA%\Notepad++\backup\`

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| New file | Ctrl+N |
| Open file | Ctrl+O |
| Save | Ctrl+S |
| Save As | Ctrl+Shift+S |
| Close tab | Ctrl+W |
| Undo | Ctrl+Z |
| Redo | Ctrl+Y |
| Find/Replace | Ctrl+F / Ctrl+H |
| Go to line | Ctrl+G |
| Select all | Ctrl+A |
| Duplicate line | Ctrl+D |
| Delete line | Ctrl+L |
| Move line up | Ctrl+Shift+Up |
| Move line down | Ctrl+Shift+Down |
| Zoom in/out | Ctrl++ / Ctrl+- |
| Next/prev tab | Ctrl+Tab / Ctrl+Shift+Tab |

## How It Works

Notepad++ stores session data in two locations:

1. **`session.xml`**: Contains the list of all open files, their paths, cursor positions, and view settings
2. **`backup/` folder**: Contains automatic backups of unsaved changes

This application parses both locations to reconstruct your complete editing session, including files you hadn't saved yet.

## Requirements

- **Python 3.7+** with Tkinter (included in standard Python installations)
- **No external dependencies** for running the application
- **PyInstaller** (optional) for building the portable executable

## Project Structure

```
notepad_replica/
├── __init__.py          # Package initialization
├── main_app.py          # Main application with UI
├── text_editor.py       # Text editor component
├── session_parser.py    # Notepad++ session file parser
└── syntax_highlighter.py # Basic syntax highlighting

notepad_replica.py       # Entry point script
build_portable.py        # PyInstaller build script
build.bat               # Windows build script
build.sh                # Linux/Mac build script
```

---

# AIN-7B Arabic OCR Test

Test script for running Arabic OCR using [MBZUAI's AIN-7B](https://huggingface.co/MBZUAI/AIN) multimodal model.

## About AIN-7B

AIN (Arabic INclusive) is the first Arabic-focused large multimodal model, developed by MBZUAI. It excels at:

- **OCR & Document Understanding** - Both typed and handwritten Arabic text
- **Visual Understanding** - Image description and analysis
- **Bilingual Support** - Arabic (MSA) and English

The model is based on Qwen2-VL-7B, fine-tuned on 3.6M high-quality Arabic-English samples.

## Installation

```bash
# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### GPU Requirements

- Minimum: NVIDIA GPU with 16GB VRAM
- Recommended: NVIDIA GPU with 24GB+ VRAM for larger documents

## Usage

### Basic OCR

```bash
# Extract all text from an Arabic document
python test_ain7b_ocr.py --image document.jpg
```

### Custom Prompts

```bash
# Use a custom prompt for specific extraction
python test_ain7b_ocr.py --image form.jpg --prompt "استخرج الاسماء والتواريخ من هذه الوثيقة"

# English prompt
python test_ain7b_ocr.py --image document.jpg --prompt "Extract all handwritten text from this document"
```

### Advanced Options

```bash
# Use flash attention for faster inference
python test_ain7b_ocr.py --image document.jpg --flash-attention

# Save output to file
python test_ain7b_ocr.py --image document.jpg --output result.txt

# Increase max tokens for longer documents
python test_ain7b_ocr.py --image document.jpg --max-tokens 4096
```

## Example Prompts

| Task | Prompt |
|------|--------|
| Full OCR | `اقرأ واستخرج كل النص من هذه الصورة` |
| Handwritten only | `اقرأ النص المكتوب بخط اليد فقط` |
| Extract names | `استخرج جميع الأسماء من هذه الوثيقة` |
| Form extraction | `Extract all form fields and their values` |
| Table extraction | `استخرج البيانات من الجدول في شكل منظم` |

## Model Performance

AIN-7B achieves strong performance on CAMEL-Bench, outperforming GPT-4o by 3.4% on average across 38 sub-domains. It particularly excels at:

- OCR & Document Understanding
- Remote Sensing
- Agricultural Image Understanding

## References

- [AIN Hugging Face Model](https://huggingface.co/MBZUAI/AIN)
- [AIN GitHub Repository](https://github.com/mbzuai-oryx/AIN)
- [AIN Paper (arXiv)](https://arxiv.org/abs/2502.00094)

## License

This test script is provided for educational and research purposes. The AIN model is subject to its own license terms from MBZUAI.
