"""
Mô-đun kiểm tra tính hợp lệ của kịch bản script.json trước khi đưa vào render.
"""

import re
from typing import Tuple, List

FORBIDDEN_SYMBOLS_IN_SAY = [
    r"\\[a-zA-Z]+",  # LaTeX commands like \frac, \sqrt
    r"=", r"\+", r"\*", r"/", r"\^", r"_", r"\\", r"<", r">", r"\$",
    r"\{", r"\}", r"\[", r"\]"
]

def validate_script(data: dict) -> Tuple[bool, List[str]]:
    """
    Kiểm tra cấu trúc và nội dung của script.json.
    Trả về: (is_valid, errors)
    """
    errors = []
    
    if not isinstance(data, dict):
        return False, ["Dữ liệu kịch bản phải là một JSON Object."]
        
    for field in ["title", "subject", "scenes"]:
        if field not in data:
            errors.append(f"Thiếu trường bắt buộc: '{field}'.")
            
    scenes = data.get("scenes", [])
    if not isinstance(scenes, list) or len(scenes) == 0:
        errors.append("Mảng 'scenes' phải có ít nhất 1 cảnh.")
        return False, errors
        
    total_steps = 0
    
    for s_idx, scene in enumerate(scenes, 1):
        if "heading" not in scene:
            errors.append(f"Cảnh {s_idx}: Thiếu 'heading'.")
            
        steps = scene.get("steps", [])
        if not isinstance(steps, list) or len(steps) == 0:
            errors.append(f"Cảnh {s_idx} ({scene.get('heading', '')}): Không có 'steps'.")
            continue
            
        for step_idx, step in enumerate(steps, 1):
            total_steps += 1
            say = step.get("say", "")
            if not say:
                errors.append(f"Cảnh {s_idx}, Bước {step_idx}: Thiếu trường 'say'.")
            elif len(say) > 220:
                errors.append(f"Cảnh {s_idx}, Bước {step_idx}: Câu 'say' dài quá 220 ký tự ({len(say)} ký tự).")
                
            # Kiểm tra ký hiệu thô trong câu nói
            for sym in FORBIDDEN_SYMBOLS_IN_SAY:
                if re.search(sym, say):
                    errors.append(f"Cảnh {s_idx}, Bước {step_idx}: 'say' chứa ký hiệu toán học hoặc ký tự cấm: \"{say}\". Cần viết dạng chữ tiếng Việt phát âm tự nhiên.")
                    break
                    
            show = step.get("show", [])
            if not isinstance(show, list):
                errors.append(f"Cảnh {s_idx}, Bước {step_idx}: 'show' phải là một danh sách (list).")
            else:
                for elem_idx, elem in enumerate(show, 1):
                    if not isinstance(elem, dict) or "id" not in elem:
                        errors.append(f"Cảnh {s_idx}, Bước {step_idx}, Phần tử {elem_idx}: Thiếu 'id'.")
                        
    if total_steps < 5:
        errors.append(f"Tổng số bước trong video quá ngắn ({total_steps} bước). Khuyến nghị từ 8 đến 14 bước.")
        
    return len(errors) == 0, errors
