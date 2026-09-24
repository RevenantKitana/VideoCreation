"""Build vi-du/index.html — the example gallery staff see on first start.

Generated from vi-du/examples.json so the menu (`welcome`), this page and the folder
stay in step. Opens straight from disk (file://); videos play in the browser.
"""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VD = ROOT / "vi-du"


def build() -> Path:
    data = json.loads((VD / "examples.json").read_text(encoding="utf-8"))
    cards = []
    for i, mode in enumerate(data["modes"], 1):
        vids = []
        for ex in mode["examples"]:
            meta = data["examples"][ex]
            vids.append(f'''
        <figure class="vid">
          <video controls preload="metadata" poster="{ex}/cover.png" src="{ex}/final.mp4"></video>
          <figcaption><b>{html.escape(meta["title"])}</b><span>{html.escape(meta["note"])}</span></figcaption>
        </figure>''')
        cards.append(f'''
    <section class="mode">
      <div class="head"><span class="n">{i}</span><div><h2>{html.escape(mode["name"])}</h2>
        <p>{html.escape(mode["what"])}</p>
        <p class="say">Nói với AI: <q>{html.escape(mode["say"])}</q></p></div></div>
      <div class="vids">{"".join(vids)}
      </div>
    </section>''')
    page = f'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Xưởng TikTok — Video mẫu</title>
<style>
  @font-face {{ font-family: B; src: url("../assets/fonts/BeVietnamPro-Regular.ttf"); font-weight: 400; }}
  @font-face {{ font-family: B; src: url("../assets/fonts/BeVietnamPro-SemiBold.ttf"); font-weight: 600; }}
  @font-face {{ font-family: B; src: url("../assets/fonts/BeVietnamPro-Bold.ttf"); font-weight: 700; }}
  :root {{ --paper:#F5EFE2; --edge:#EBE3D1; --line:#DFD5C0; --ink:#1C1C1A; --muted:#57554E; --jade:#1F6F5C; --soft:#D3E3DA; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; background:var(--paper); color:var(--ink); font:16px/1.55 B, system-ui, sans-serif; }}
  header {{ max-width:1180px; margin:0 auto; padding:40px 24px 8px; }}
  .rule {{ height:3px; background:var(--jade); position:relative; margin-bottom:26px; }}
  .rule::before {{ content:""; position:absolute; left:0; top:-5px; width:13px; height:13px; background:var(--jade); }}
  h1 {{ margin:0 0 6px; color:var(--jade); font-size:clamp(28px,4vw,42px); }}
  header p {{ margin:0; color:var(--muted); max-width:760px; }}
  main {{ max-width:1180px; margin:0 auto; padding:10px 24px 60px; }}
  .mode {{ background:var(--edge); border-radius:16px; padding:22px; margin:22px 0; }}
  .head {{ display:flex; gap:16px; align-items:flex-start; }}
  .n {{ flex:none; width:38px; height:38px; border-radius:50%; background:var(--jade); color:var(--paper);
        display:flex; align-items:center; justify-content:center; font-weight:700; font-size:18px; }}
  h2 {{ margin:2px 0 4px; font-size:21px; }}
  .head p {{ margin:0 0 4px; color:var(--muted); }}
  .say q {{ color:var(--jade); font-weight:600; quotes:"“" "”"; }}
  .vids {{ display:flex; flex-wrap:wrap; gap:18px; margin-top:16px; }}
  .vid {{ margin:0; background:var(--paper); border-radius:12px; padding:10px; }}
  .vid video {{ display:block; border-radius:8px; background:#000; max-height:520px; max-width:100%; }}
  figcaption {{ padding:8px 4px 2px; max-width:520px; }}
  figcaption b {{ display:block; }}
  figcaption span {{ color:var(--muted); font-size:14px; }}
  .foot {{ background:var(--soft); border-radius:14px; padding:18px 22px; }}
  .foot p {{ margin:4px 0; }}
</style></head><body>
<header><div class="rule"></div>
  <h1>Xưởng TikTok Aiducation — xem làm được gì</h1>
  <p>Mỗi mục là một kiểu video xưởng làm được, kèm video mẫu. Bấm ▶ để xem. Muốn làm, chỉ cần nói câu gợi ý với AI.</p>
</header>
<main>{"".join(cards)}
  <section class="foot">
    <p><b>Giọng đọc:</b> {html.escape(data["voices"])}</p>
    <p><b>Thêm:</b> {html.escape(data["also"])}</p>
    <p>Hướng dẫn đầy đủ: <b>HUONG-DAN-SU-DUNG.pdf</b> trong thư mục xưởng.</p>
  </section>
</main></body></html>
'''
    out = VD / "index.html"
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    print(build())
