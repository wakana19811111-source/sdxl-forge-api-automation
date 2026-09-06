"""画面のHTMLを生成する（ステップ3：プルダウン＋自由文＋生成ボタン）。

使い方: python3 build_html.py
入力:   prompts/IntegratedPromptGenerator_SDXL.md（プロンプトの正本）
出力:   html/IntegratedPromptGenerator_SDXL.html

⭐ 画面は手で書かない。このスクリプトの生成物だけが画面。
⭐ 選択肢は Markdownファイルから HTML の中へ直接書き出す一本（GET /prompts は作らない）。
  Markdownファイルを直したらこのスクリプトで再生成する。
⛔ Markdownファイルが無い・## が1つも無いときはエラーで止まる（空の画面を黙って作らない）。
"""

import sys
from html import escape
from pathlib import Path

BASE_DIR = Path(__file__).parent
OUT_FILE = BASE_DIR / "html" / "IntegratedPromptGenerator_SDXL.html"
PROXY_URL = "http://localhost:8767"

sys.path.insert(0, str(BASE_DIR / "sdxl"))
from prompt_loader import PromptFileError, load_items  # noqa: E402

HEAD = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>統合プロンプトジェネレーター SDXL</title>
<style>
  body {
    font-family: "Hiragino Sans", "Hiragino Kaku Gothic ProN", sans-serif;
    max-width: 720px; margin: 0 auto; padding: 24px;
    background: #f5f6f8; color: #222;
  }
  h1 { font-size: 20px; }
  .note { color: #666; font-size: 13px; }
  .selector { margin-top: 10px; }
  .selector label { display: inline-block; width: 5em; font-size: 14px; }
  .pg-select {
    font-size: 15px; padding: 6px; border: 1px solid #bbb; border-radius: 6px;
    background: #fff; min-width: 60%;
  }
  textarea {
    width: 100%; box-sizing: border-box; height: 96px;
    font-size: 15px; padding: 8px; border: 1px solid #bbb; border-radius: 6px;
  }
  button {
    margin-top: 12px; padding: 10px 28px; font-size: 16px;
    background: #2563a8; color: #fff; border: none; border-radius: 6px;
    cursor: pointer;
  }
  button:disabled { background: #9ab; cursor: wait; }
  #status { margin-top: 12px; min-height: 1.4em; font-size: 14px; }
  #status.error { color: #c0392b; }
  #result-img { max-width: 100%; margin-top: 12px; border: 1px solid #ccc; }
  #result-meta { font-size: 13px; color: #444; margin-top: 6px; word-break: break-all; }
</style>
</head>
<body>
<h1>統合プロンプトジェネレーター SDXL（ステップ3）</h1>
"""

FORM = """\
<p class="note">項目を選ぶか、自由文プロンプトを入れて「生成」を押してください。既定値の prompt / negative（Markdownファイルの ## 既定値）は自動で付きます。</p>
<textarea id="prompt" placeholder="自由文（例: sitting on a bench in a park）"></textarea>
<br>
<button id="gen-btn" onclick="runGenerate()">生成</button>
<div id="status"></div>
<img id="result-img" hidden alt="生成画像">
<div id="result-meta"></div>
"""

SCRIPT = """\
<script>
const PROXY_URL = "%PROXY_URL%";

async function runGenerate() {
  const btn = document.getElementById("gen-btn");
  const status = document.getElementById("status");
  const img = document.getElementById("result-img");
  const meta = document.getElementById("result-meta");

  btn.disabled = true;
  status.classList.remove("error");
  status.textContent = "生成中…（初回はモデルのロードで数分かかります）";
  img.hidden = true;
  img.removeAttribute("src");
  meta.textContent = "";

  // プルダウンで選んだ項目を集める（「指定なし」＝value が空のものは送らない）
  const selections = {};
  document.querySelectorAll(".pg-select").forEach((sel) => {
    if (sel.value) selections[sel.dataset.section] = sel.value;
  });

  // fetch にタイムアウトは付けない（初回はモデルのロードで数分かかるため）
  let res;
  try {
    res = await fetch(PROXY_URL + "/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: document.getElementById("prompt").value,
        selections: selections
      })
    });
  } catch (e) {
    status.classList.add("error");
    status.textContent = "proxy.py（8767）に接続できません";
    btn.disabled = false;
    return;
  }

  let data = {};
  try { data = await res.json(); } catch (e) { /* 本文がJSONでない応答 */ }

  if (!res.ok) {
    status.classList.add("error");
    status.textContent = data.error || ("エラー（HTTP " + res.status + "）");
    btn.disabled = false;
    return;
  }

  img.src = "data:image/png;base64," + data.image_base64;
  img.hidden = false;
  meta.textContent = "保存先: " + data.path + " ／ seed: " + data.seed;
  status.textContent = "生成が終わりました";
  btn.disabled = false;
}
</script>
</body>
</html>
"""


def render_selectors(data: dict) -> str:
    """Markdownファイルの項目からプルダウンを作る。どのプルダウンも先頭は「指定なし」。"""
    rows = []
    for name, choices in data["sections"].items():
        options = ['<option value="">指定なし</option>'] + [
            f"<option>{escape(choice)}</option>" for choice in choices
        ]
        rows.append(
            f'<div class="selector"><label>{escape(name)}</label>'
            f'<select class="pg-select" data-section="{escape(name)}">'
            + "".join(options)
            + "</select></div>"
        )
    return "\n".join(rows) + "\n"


def build_page(data: dict) -> str:
    return (
        HEAD + render_selectors(data) + FORM
        + SCRIPT.replace("%PROXY_URL%", PROXY_URL)
    )


def main() -> None:
    data = load_items()  # Markdownが無い・## が無いときはここで止まる
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(build_page(data), encoding="utf-8")
    print(f"生成完了: {OUT_FILE}")
    print(f"プルダウン: {', '.join(data['sections'])}")
    print(f"選択肢の総数: {sum(len(c) for c in data['sections'].values())}")


if __name__ == "__main__":
    try:
        main()
    except PromptFileError as e:
        print(f"🔴 停止: {e}", file=sys.stderr)
        sys.exit(1)
