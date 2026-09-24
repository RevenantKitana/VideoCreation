# Sub-Module: Render Video Độc Lập (sub_render)

Mô-đun chuyên trách nhận đầu vào là file `script.json` có sẵn để:
1. Kiểm tra tính hợp lệ (`check`)
2. Xuất ảnh xem trước (`preview.png`)
3. Tạo âm thanh & canh mốc thời gian karaoke (`voice`)
4. Xuất video hoàn chỉnh (`final.mp4` + `cover.png`)

**Hoàn toàn độc lập, không phụ thuộc vào bất kỳ AI Agent hay API key bên ngoài nào.**

---

## Cấu trúc thư mục

- `renderer.py`: Entry point chính xử lý toàn bộ pipeline render từ file `script.json`.
- `api_server.py`: Máy chủ FastAPI sẵn sàng chạy để nhận request render từ Web Frontend (Cloudflare R2).
- `README.md`: Hướng dẫn sử dụng.

---

## Cách sử dụng

### 1. Sử dụng qua dòng lệnh (CLI)
```bash
# 1. Kiểm tra kịch bản
python -m sub_render.renderer check --script path/to/script.json

# 2. Xuất ảnh xem trước preview.png
python -m sub_render.renderer preview --script path/to/script.json --out build_output/

# 3. Xuất video hoàn chỉnh (final.mp4 + cover.png)
python -m sub_render.renderer render --script path/to/script.json --out build_output/
```

### 2. Sử dụng như một thư viện Python
```python
from sub_render import render_from_script, generate_preview

# Xuất ảnh xem trước
preview_path = generate_preview("path/to/script.json", output_dir="output/")
print(f"Ảnh preview: {preview_path}")

# Render toàn bộ video
result = render_from_script("path/to/script.json", output_dir="output/")
print(f"Video final: {result['video_path']}")
print(f"Ảnh cover: {result['cover_path']}")
```

### 3. Khởi chạy làm Backend API Server (cho Web / R2 Frontend)
```bash
# Chạy server FastAPI tại cổng 8000
python -m sub_render.api_server --port 8000
```
Sau đó Frontend có thể gửi POST request JSON tới `http://localhost:8000/api/render` để nhận video.
