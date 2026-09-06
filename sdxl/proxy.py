"""SDXL 用プロキシ（ステップ3：画面と Forge API の中継）。

起動: python3 proxy.py
ポート: 8767（他のプログラムと重ならない番号なら何でもよい）

経路は POST /generate と OPTIONS（CORS）だけ。
  GET /prompts は作らない。画面の選択肢は build_html.py が
    Markdownファイルから HTML へ直接書き出す一本にする。
  GET /settings はステップ4で足す。

POST /generate は「選んだ項目」（selections）と自由文（prompt）を受け取り、
prompt_loader.build_prompt() で既定値＋選んだ項目＋自由文を組み立ててから
generate_once() を呼ぶ。

⛔ この proxy は Forge API を直接呼ばない。生成は必ず generate.generate_once() を
   通す——送信前の関門と PNG 照合を、コマンド経路と画面経路で同じに通すため
   （フォールバックを作らない）。
⛔ 例外は 500 とエラー文をそのまま返す（黙って作り直さない・別の値で再試行しない）。
"""

import base64
import json
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

import model_rules
import prompt_loader
from generate import GenerateError, generate_once
from settings_loader import SettingsError, load_settings

PORT = 8767


class ProxyHandler(BaseHTTPRequestHandler):

    def _cors(self):
        # 画面は file:// で開くため CORS を許す
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
        if self.path != "/generate":
            self.send_response(404)
            self.end_headers()
            return

        try:
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
            )
        except ValueError:
            self._json(400, {"error": "リクエストボディがJSONとして読めません。"})
            return
        if not isinstance(body, dict):
            self._json(400, {"error": "リクエストボディはJSONオブジェクトである必要があります。"})
            return

        free_text = body.get("prompt", "")
        if not isinstance(free_text, str):
            self._json(400, {"error": "prompt は文字列で指定してください。"})
            return
        selections = body.get("selections", {})
        if not isinstance(selections, dict) or not all(
            isinstance(k, str) and isinstance(v, str)
            for k, v in selections.items()
        ):
            self._json(400, {"error": "selections は {見出し: 選択肢} の形で指定してください。"})
            return

        # 全プルダウン「指定なし」（＝値が空）＋自由文も空なら生成しない
        if not free_text.strip() and not any(v.strip() for v in selections.values()):
            self._json(400, {"error": "項目を選ぶか、プロンプトを入れてください"})
            return

        # Markdownファイル（プロンプトの正本）から既定値＋選んだ項目＋自由文を組み立てる
        try:
            items = prompt_loader.load_items()
            prompt, negative = prompt_loader.build_prompt(items, selections, free_text)
        except prompt_loader.StaleChoiceError as e:
            print(f"  選択肢の不一致: {e}")
            self._json(400, {"error": "HTMLが更新されていません。ブラウザを再読み込みしてください"})
            return
        except prompt_loader.PromptFileError as e:
            self._json(500, {"error": str(e)})
            return

        try:
            settings = load_settings()
            results = generate_once(settings, prompt, negative)
            if not results:
                self._json(500, {"error": "画像が返りませんでした。"})
                return
            first = results[0]
            self._json(200, {
                "image_base64": base64.b64encode(first["image_bytes"]).decode("ascii"),
                "seed": first["seed"],
                "path": first["path"],
                "model_hash": first["info"].get("Model hash", ""),
            })
        except (GenerateError, SettingsError, model_rules.ModelRuleError) as e:
            self._json(500, {"error": str(e)})
        except Exception as e:
            print(traceback.format_exc())
            self._json(500, {"error": str(e)})

    def _json(self, code: int, data: dict):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"  {format % args}")


if __name__ == "__main__":
    print("=== SDXL プロキシ起動（ステップ3） ===")
    print(f"ポート: {PORT}")
    print("経路: POST /generate")
    print("Ctrl+C で停止")
    print()
    HTTPServer(("", PORT), ProxyHandler).serve_forever()
