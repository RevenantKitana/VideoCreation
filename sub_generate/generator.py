"""
Mô-đun sinh kịch bản tự động script.json từ yêu cầu đề bài / chủ đề.
Hỗ trợ: Gemini API, OpenAI API, Anthropic Claude, hoặc Ollama cục bộ.
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

from .schema_rules import SYSTEM_PROMPT, FEW_SHOT_MATH_EXAMPLE
from .validator import validate_script


def _clean_json_response(raw_text: str) -> str:
    """Loại bỏ markdown block ```json ... ``` nếu LLM trả về định dạng code block."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def generate_with_gemini(prompt: str, api_key: Optional[str] = None, model: str = "gemini-1.5-flash") -> str:
    """Gọi Gemini API thông qua REST API (không phụ thuộc SDK bên ngoài)."""
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Thiếu GEMINI_API_KEY. Vui lòng thiết lập biến môi trường GEMINI_API_KEY hoặc truyền api_key.")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{SYSTEM_PROMPT}\n\nVí dụ tham khảo:\n{json.dumps(FEW_SHOT_MATH_EXAMPLE, ensure_ascii=False, indent=2)}\n\nYêu cầu tạo kịch bản cho đề bài sau:\n{prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.2
        }
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_with_openai(prompt: str, api_key: Optional[str] = None, model: str = "gpt-4o") -> str:
    """Gọi OpenAI API qua HTTP."""
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("Thiếu OPENAI_API_KEY.")
        
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Đề bài/Chủ đề:\n{prompt}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}"
        }
    )
    
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def generate_with_ollama(prompt: str, base_url: str = "http://localhost:11434", model: str = "qwen2.5-coder") -> str:
    """Gọi Ollama chạy mô hình cục bộ."""
    url = f"{base_url}/api/generate"
    payload = {
        "model": model,
        "system": SYSTEM_PROMPT,
        "prompt": prompt,
        "format": "json",
        "stream": False
    }
    
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    
    with urllib.request.urlopen(req) as res:
        data = json.loads(res.read().decode("utf-8"))
        return data["response"]


def generate_script(
    topic: str,
    subject: str = "TOÁN",
    voice: str = "Minh Quân Pro",
    format_ratio: str = "9:16",
    provider: str = "gemini",
    api_key: Optional[str] = None,
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Hàm sinh kịch bản JSON hoàn chỉnh từ chủ đề.
    """
    full_prompt = f"Môn học: {subject}\nTỉ lệ: {format_ratio}\nGiọng đọc: {voice}\nChủ đề/Đề bài: {topic}"
    
    if provider == "gemini":
        raw = generate_with_gemini(full_prompt, api_key=api_key, model=model or "gemini-1.5-flash")
    elif provider == "openai":
        raw = generate_with_openai(full_prompt, api_key=api_key, model=model or "gpt-4o")
    elif provider == "ollama":
        raw = generate_with_ollama(full_prompt, model=model or "qwen2.5-coder")
    else:
        raise ValueError(f"Không hỗ trợ provider: {provider}")
        
    cleaned_json = _clean_json_response(raw)
    script_data = json.loads(cleaned_json)
    
    # Kiểm tra kịch bản vừa sinh ra
    is_valid, errors = validate_script(script_data)
    if not is_valid:
        print(f"[CẢNH BÁO] Kịch bản sinh ra có một số điểm cần lưu ý:\n" + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
        
    return script_data


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sinh kịch bản script.json tự động từ đề bài.")
    parser.add_argument("--topic", required=True, help="Chủ đề hoặc bài toán cần giảng.")
    parser.add_argument("--subject", default="TOÁN", help="Môn học (TOÁN, LÝ, HÓA, SINH, ANH).")
    parser.add_argument("--voice", default="Minh Quân Pro", help="Giọng đọc AI.")
    parser.add_argument("--format", default="9:16", choices=["9:16", "16:9"], help="Tỉ lệ video.")
    parser.add_argument("--provider", default="gemini", choices=["gemini", "openai", "ollama"], help="Nhà cung cấp LLM.")
    parser.add_argument("--output", default="script.json", help="Đường dẫn file đầu ra.")
    
    args = parser.parse_args()
    
    print(f"Đang tạo kịch bản cho: {args.topic} ({args.subject})...")
    try:
        res = generate_script(
            topic=args.topic,
            subject=args.subject,
            voice=args.voice,
            format_ratio=args.format,
            provider=args.provider
        )
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(res, f, ensure_ascii=False, indent=2)
        print(f"-> Đã lưu kịch bản thành công vào: {args.output}")
    except Exception as err:
        print(f"Lỗi: {err}", file=sys.stderr)
        sys.exit(1)
