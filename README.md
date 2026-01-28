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
