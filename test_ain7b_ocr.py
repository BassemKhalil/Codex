#!/usr/bin/env python3
"""
AIN-7B Arabic OCR Test Script
=============================
Test script for running Arabic OCR using MBZUAI's AIN-7B multimodal model.

The AIN-7B model excels at OCR and document understanding, especially for
Arabic text (both typed and handwritten).

Usage:
    python test_ain7b_ocr.py --image <path_to_image>
    python test_ain7b_ocr.py --image <path_to_image> --prompt "Custom prompt"
"""

import argparse
import sys
from pathlib import Path

import torch
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

try:
    from qwen_vl_utils import process_vision_info
    HAS_QWEN_VL_UTILS = True
except ImportError:
    HAS_QWEN_VL_UTILS = False
    print("Warning: qwen_vl_utils not installed. Using basic inference mode.")
    print("Install with: pip install qwen-vl-utils")


def load_model(model_name: str = "MBZUAI/AIN", use_flash_attention: bool = False):
    """Load the AIN-7B model and processor."""
    print(f"Loading model: {model_name}")

    if use_flash_attention:
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16,
            attn_implementation="flash_attention_2",
            device_map="auto",
        )
    else:
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype="auto",
            device_map="auto",
        )

    processor = AutoProcessor.from_pretrained(model_name)
    print("Model loaded successfully!")
    return model, processor


def run_ocr_with_utils(model, processor, image_path: str, prompt: str, max_tokens: int = 2048):
    """Run OCR using qwen_vl_utils for processing."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": f"file://{image_path}",
                },
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    image_inputs, video_inputs = process_vision_info(messages)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    inputs = inputs.to("cuda" if torch.cuda.is_available() else "cpu")

    print("Running inference...")
    generated_ids = model.generate(**inputs, max_new_tokens=max_tokens)
    generated_ids_trimmed = [
        out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
    )
    return output_text[0]


def run_ocr_basic(model, processor, image_path: str, prompt: str, max_tokens: int = 2048):
    """Run OCR using basic PIL image loading."""
    image = Image.open(image_path)

    conversation = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    text_prompt = processor.apply_chat_template(conversation, add_generation_prompt=True)
    inputs = processor(
        text=[text_prompt], images=[image], padding=True, return_tensors="pt"
    )
    inputs = inputs.to("cuda" if torch.cuda.is_available() else "cpu")

    print("Running inference...")
    output_ids = model.generate(**inputs, max_new_tokens=max_tokens)
    generated_ids = [
        output_ids[len(input_ids):]
        for input_ids, output_ids in zip(inputs.input_ids, output_ids)
    ]
    output_text = processor.batch_decode(
        generated_ids, skip_special_tokens=True, clean_up_tokenization_spaces=True
    )
    return output_text[0]


def main():
    parser = argparse.ArgumentParser(
        description="Run Arabic OCR using AIN-7B model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic OCR (extract all text)
  python test_ain7b_ocr.py --image document.jpg

  # OCR with custom prompt
  python test_ain7b_ocr.py --image document.jpg --prompt "اقرأ النص المكتوب بخط اليد"

  # Extract structured data
  python test_ain7b_ocr.py --image form.jpg --prompt "Extract the names and dates from this form"

  # Use flash attention for faster inference
  python test_ain7b_ocr.py --image document.jpg --flash-attention
        """
    )
    parser.add_argument(
        "--image", "-i",
        type=str,
        required=True,
        help="Path to the input image"
    )
    parser.add_argument(
        "--prompt", "-p",
        type=str,
        default="اقرأ واستخرج كل النص من هذه الصورة بدقة، بما في ذلك النص المطبوع والمكتوب بخط اليد. قدم النص كما يظهر في الوثيقة.",
        help="Prompt for OCR (default: Arabic prompt for complete text extraction)"
    )
    parser.add_argument(
        "--max-tokens", "-m",
        type=int,
        default=2048,
        help="Maximum number of tokens to generate (default: 2048)"
    )
    parser.add_argument(
        "--flash-attention",
        action="store_true",
        help="Use flash attention 2 for faster inference (requires flash-attn package)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="MBZUAI/AIN",
        help="Model name or path (default: MBZUAI/AIN)"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output file to save the extracted text"
    )

    args = parser.parse_args()

    # Validate image path
    image_path = Path(args.image).resolve()
    if not image_path.exists():
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)

    print("=" * 60)
    print("AIN-7B Arabic OCR Test")
    print("=" * 60)
    print(f"Image: {image_path}")
    print(f"Prompt: {args.prompt}")
    print(f"Max tokens: {args.max_tokens}")
    print("=" * 60)

    # Load model
    model, processor = load_model(args.model, args.flash_attention)

    # Run OCR
    if HAS_QWEN_VL_UTILS:
        result = run_ocr_with_utils(model, processor, str(image_path), args.prompt, args.max_tokens)
    else:
        result = run_ocr_basic(model, processor, str(image_path), args.prompt, args.max_tokens)

    print("\n" + "=" * 60)
    print("OCR RESULT:")
    print("=" * 60)
    print(result)
    print("=" * 60)

    # Save output if requested
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(result, encoding="utf-8")
        print(f"\nOutput saved to: {output_path}")

    return result


if __name__ == "__main__":
    main()
