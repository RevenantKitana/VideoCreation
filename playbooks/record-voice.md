# Playbook — the person records their own voice

Use when they want to read the narration themselves. The script must already pass
`check` and `preview` (see make-video.md steps 1–4).

1. Tell them, in Vietnamese:
   > Em sẽ mở trang "Phòng thu" trên trình duyệt. Mỗi lần một câu: bấm **Nghe mẫu** để
   > nghe cách đọc, bấm **Ghi âm**, đọc theo chữ sáng lên, bấm **Dừng**. Câu nào hiện màu
   > đỏ thì đọc lại câu đó. Xong hết thì bấm **Hoàn tất**. Nên ngồi chỗ yên tĩnh, dùng tai
   > nghe có mic nếu có.
2. Run `./os record <v>` (Windows `os.cmd record <v>`). It opens http://127.0.0.1:8765 and
   keeps running until they press Hoàn tất. The first time, the browser asks for the
   microphone: they must click **Allow / Cho phép**.
3. While it runs, stay available. Common issues:
   - "Không mở được micro" → browser permission blocked; in Chrome click the lock icon by
     the address → Microphone → Allow, reload.
   - A line stays red after 3 tries → the `say` text is probably awkward to read aloud.
     Offer to reword it in script.json (then restart `record`; earlier good takes are kept).
4. When they say they're done (or the command exits), run `./os voice <v>` to confirm the
   report is clean (voice will be `record`), then continue with `render`.

Notes
- Takes are cleaned automatically: silence trimmed, gentle denoise, level normalised.
- The karaoke pace in the studio comes from the AI reading of the line; they don't have
  to match it exactly — the animation re-times itself to *their* recording.
