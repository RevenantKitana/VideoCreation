"""
Mô-đun render video độc lập từ file kịch bản script.json có sẵn.
Kết nối trực tiếp với engine (Manim + VieNeu TTS + Remotion).
"""

import json
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Union

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine import pipeline


def _prepare_work_dir(script_input: Union[str, Path, dict], output_dir: Optional[Union[str, Path]] = None) -> Path:
    """Chuẩn bị thư mục làm việc và file script.json."""
    if isinstance(script_input, (str, Path)):
        src_path = Path(script_input).resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file kịch bản tại: {src_path}")
        script_data = json.loads(src_path.read_text(encoding="utf-8"))
        work_dir = Path(output_dir).resolve() if output_dir else src_path.parent
    elif isinstance(script_input, dict):
        script_data = script_input
        work_dir = Path(output_dir).resolve() if output_dir else (ROOT / "videos" / f"temp-{os.getpid()}")
    else:
        raise ValueError("script_input phải là đường dẫn file (str/Path) hoặc dict.")

    work_dir.mkdir(parents=True, exist_ok=True)
    target_script = work_dir / "script.json"
    target_script.write_text(json.dumps(script_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return work_dir


def check_script(script_input: Union[str, Path, dict]) -> list[str]:
    """Kiểm tra tính hợp lệ của kịch bản và các công thức LaTeX."""
    work_dir = _prepare_work_dir(script_input)
    return pipeline.check(work_dir)


def generate_preview(script_input: Union[str, Path, dict], output_dir: Optional[Union[str, Path]] = None) -> Path:
    """Xuất ảnh xem trước preview.png từ script.json."""
    work_dir = _prepare_work_dir(script_input, output_dir)
    errors = pipeline.check(work_dir)
    if errors:
        raise ValueError("Kịch bản chứa lỗi:\n" + "\n".join(f"- {e}" for e in errors))
    
    pipeline.preview(work_dir)
    preview_png = work_dir / "preview.png"
    if not preview_png.exists():
        raise RuntimeError("Không tạo được file preview.png")
    return preview_png


def generate_voice(script_input: Union[str, Path, dict], output_dir: Optional[Union[str, Path]] = None, voice_override: Optional[str] = None) -> Path:
    """Tạo âm thanh TTS và canh mốc thời gian phụ đề."""
    work_dir = _prepare_work_dir(script_input, output_dir)
    pipeline.voice(work_dir, voice_override=voice_override)
    report_json = work_dir / "voice" / "report.json"
    return report_json


def render_from_script(
    script_input: Union[str, Path, dict],
    output_dir: Optional[Union[str, Path]] = None,
    voice_override: Optional[str] = None,
    force: bool = False
) -> Dict[str, Any]:
    """
    Render toàn bộ video từ file script.json có sẵn:
    check -> voice -> render -> final.mp4 + cover.png.
    """
    work_dir = _prepare_work_dir(script_input, output_dir)
    
    # 1. Kiểm tra kịch bản
    errors = pipeline.check(work_dir)
    if errors:
        raise ValueError("Lỗi kịch bản:\n" + "\n".join(f"- {e}" for e in errors))
        
    # 2. Tạo âm thanh & căn phụ đề
    print("-> Đang tạo giọng đọc AI và canh mốc thời gian phụ đề...")
    pipeline.voice(work_dir, voice_override=voice_override)
    
    # 3. Render video hoàn chỉnh
    print("-> Đang ghép video và xuất file hoàn chỉnh qua Remotion...")
    pipeline.render(work_dir, force=force)
    
    final_mp4 = work_dir / "final.mp4"
    cover_png = work_dir / "cover.png"
    preview_png = work_dir / "preview.png"
    
    return {
        "status": "success",
        "video_path": str(final_mp4) if final_mp4.exists() else None,
        "cover_path": str(cover_png) if cover_png.exists() else None,
        "preview_path": str(preview_png) if preview_png.exists() else None,
        "work_dir": str(work_dir)
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Render video độc lập từ file script.json có sẵn.")
    parser.add_argument("action", choices=["check", "preview", "voice", "render"], help="Hành động cần thực hiện")
    parser.add_argument("--script", required=True, help="Đường dẫn tới file script.json")
    parser.add_argument("--out", default=None, help="Thư mục xuất kết quả (tùy chọn)")
    parser.add_argument("--voice", default=None, help="Ghi đè giọng đọc (tùy chọn)")
    parser.add_argument("--force", action="store_true", help="Bỏ qua cảnh báo để render")
    
    args = parser.parse_args()
    
    script_file = Path(args.script)
    if not script_file.exists():
        print(f"Lỗi: Không tìm thấy file {args.script}", file=sys.stderr)
        sys.exit(1)
        
    if args.action == "check":
        errs = check_script(script_file)
        if errs:
            print("Phát hiện lỗi trong kịch bản:")
            for e in errs:
                print(f" - {e}")
            sys.exit(1)
        print("Kịch bản hợp lệ 100% (script OK)!")
    elif args.action == "preview":
        p = generate_preview(script_file, output_dir=args.out)
        print(f"Đã xuất ảnh xem trước thành công: {p}")
    elif args.action == "voice":
        v = generate_voice(script_file, output_dir=args.out, voice_override=args.voice)
        print(f"Đã tạo giọng đọc thành công: {v}")
    elif args.action == "render":
        res = render_from_script(script_file, output_dir=args.out, voice_override=args.voice, force=args.force)
        print("\n=== XUẤT VIDEO THÀNH CÔNG ===")
        print(f"Video: {res['video_path']}")
        print(f"Ảnh bìa: {res['cover_path']}")
