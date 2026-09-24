"""
Máy chủ API độc lập (Standalone HTTP API Server) phục vụ yêu cầu render từ Frontend.
Chạy trực tiếp bằng Python thuần (không cần cài thêm framework ngoài).
"""

import json
import os
import sys
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

from .renderer import render_from_script, generate_preview, check_script

PORT = 8000
BUILD_DIR = Path(__file__).resolve().parents[1] / "videos" / "api_jobs"


class RenderAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, data: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len)

        try:
            payload = json.loads(post_body.decode("utf-8"))
        except Exception:
            return self._send_json(400, {"status": "error", "message": "Dữ liệu gửi lên phải là JSON hợp lệ."})

        job_id = f"job_{uuid.uuid4().hex[:8]}"
        job_dir = BUILD_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        if parsed.path == "/api/check":
            errors = check_script(payload)
            if errors:
                return self._send_json(400, {"status": "invalid", "errors": errors})
            return self._send_json(200, {"status": "valid", "message": "Kịch bản hợp lệ 100%!"})

        elif parsed.path == "/api/preview":
            try:
                preview_path = generate_preview(payload, output_dir=job_dir)
                return self._send_json(200, {
                    "status": "success",
                    "job_id": job_id,
                    "preview_path": str(preview_path),
                    "file_url": f"/files/{job_id}/preview.png"
                })
            except Exception as e:
                return self._send_json(500, {"status": "error", "message": str(e)})

        elif parsed.path == "/api/render":
            try:
                res = render_from_script(payload, output_dir=job_dir)
                return self._send_json(200, {
                    "status": "success",
                    "job_id": job_id,
                    "video_path": res.get("video_path"),
                    "cover_path": res.get("cover_path"),
                    "video_url": f"/files/{job_id}/final.mp4",
                    "cover_url": f"/files/{job_id}/cover.png"
                })
            except Exception as e:
                return self._send_json(500, {"status": "error", "message": str(e)})

        else:
            return self._send_json(404, {"status": "error", "message": "Endpoint không tồn tại."})

    def do_GET(self):
        parsed = urlparse(self.path)
        # Phục vụ file tĩnh kết quả (video, ảnh)
        if parsed.path.startswith("/files/"):
            rel_path = parsed.path[len("/files/"):]
            file_path = (BUILD_DIR / rel_path).resolve()
            if file_path.exists() and file_path.is_file():
                self.send_response(200)
                if file_path.suffix == ".mp4":
                    self.send_header("Content-Type", "video/mp4")
                elif file_path.suffix == ".png":
                    self.send_header("Content-Type", "image/png")
                else:
                    self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
                return
        self._send_json(404, {"status": "error", "message": "Không tìm thấy file."})


def run_server(port: int = PORT):
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    server_address = ("", port)
    httpd = HTTPServer(server_address, RenderAPIHandler)
    print(f"=== MÁY CHỦ SUB_RENDER API ĐANG CHẠY TẠI CỔNG {port} ===")
    print(f"Endpoints:")
    print(f" - POST http://localhost:{port}/api/check")
    print(f" - POST http://localhost:{port}/api/preview")
    print(f" - POST http://localhost:{port}/api/render")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã tắt máy chủ.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Khởi chạy Render API Server.")
    parser.add_argument("--port", type=int, default=PORT, help="Cổng chạy server (mặc định 8000)")
    args = parser.parse_args()
    run_server(args.port)
