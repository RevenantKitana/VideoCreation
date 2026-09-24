# Sub-Module: Sinh Kịch Bản Video (sub_generate)

Mô-đun độc lập chịu trách nhiệm chuyển đổi yêu cầu bài học (văn bản, đề bài) thành file `script.json` chuẩn cấu trúc của xưởng video Aiducation.

---

## Cấu trúc thư mục

- `generator.py`: Module chính gọi LLM (hỗ trợ Google Gemini, OpenAI, Claude, Ollama cục bộ) để sinh kịch bản `script.json`.
- `schema_rules.py`: Chứa toàn bộ System Prompt, quy tắc viết công thức LaTeX, cấu trúc hook, thời lượng, và các ví dụ mẫu (Few-shot examples).
- `validator.py`: Kiểm tra tính hợp lệ của file JSON (kiểm tra độ dài câu nói, tiếng Việt tự nhiên trong trường `say`, công thức LaTeX).

---

## Cách sử dụng

### 1. Sử dụng qua dòng lệnh (CLI):
```bash
# Sử dụng Google Gemini API
python generator.py --topic "Định lý Pythagoras lớp 8" --subject TOÁN --output script.json

# Chỉ định nhà cung cấp AI và model
python generator.py --topic "Định luật Ôm Vật lý 9" --provider openai --model gpt-4o --output script.json
```

### 2. Sử dụng như một thư viện Python trong Backend:
```python
from sub_generate.generator import generate_script

script_data = generate_script(
    topic="Giải phương trình bậc hai x^2 - 5x + 6 = 0",
    subject="TOÁN",
    voice="Minh Quân Pro",
    format_ratio="9:16",
    provider="gemini"  # hoặc "openai", "anthropic", "ollama"
)

# Lưu kịch bản ra file
import json
with open("script.json", "w", encoding="utf-8") as f:
    json.dump(script_data, f, ensure_ascii=False, indent=2)
```
