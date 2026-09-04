"""画面のHTMLを生成する（ステップ2：入力欄と生成ボタンだけの最小版）。

使い方: python3 build_html.py
出力:   html/IntegratedPromptGenerator_SDXL.html

⭐ 画面は手で書かない。このスクリプトの生成物だけが画面。
⚠ ステップ3で「Markdownファイルから項目を読む」処理をここに足し、
  同じファイル名へ上書き生成する。
  差し込み口は render_selectors()——ステップ2では空文字を返すだけ。
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
OUT_FILE = BASE_DIR / "html" / "IntegratedPromptGenerator_SDXL.html"
PROXY_URL = "http://localhost:8767"

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
<h1>統合プロンプトジェネレーター SDXL（ステップ2）</h1>
"""

FORM = """\
<p class="note">プロンプトを入れて「生成」を押してください。negative はプリセットの negative_prefix が自動で付きます。</p>
<textarea id="prompt" placeholder="japanese woman, portrait, natural light"></textarea>
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

  // fetch にタイムアウトは付けない（初回はモデルのロードで数分かかるため）
  let res;
  try {
    res = await fetch(PROXY_URL + "/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        prompt: document.getElementById("prompt").value,
        negative: ""
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


def render_selectors() -> str:
    """項目の選択UI。ステップ3で Markdownファイルから生成する（今は空）。"""
    return ""


def build_page() -> str:
    return HEAD + render_selectors() + FORM + SCRIPT.replace("%PROXY_URL%", PROXY_URL)


def main() -> None:
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(build_page(), encoding="utf-8")
    print(f"生成完了: {OUT_FILE}")


if __name__ == "__main__":
    main()
