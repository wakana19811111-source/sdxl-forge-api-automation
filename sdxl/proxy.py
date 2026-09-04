"""SDXL 用プロキシ（ステップ2：画面と Forge API の中継）。

起動: python3 proxy.py
ポート: 8767（他のプログラムと重ならない番号なら何でもよい）

経路は POST /generate と OPTIONS（CORS）だけ。
  GET /prompts はステップ3、GET /settings はステップ4で足す。

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

        prompt = body.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            self._json(400, {"error": "プロンプトを入れてください"})
            return
        negative = body.get("negative", "")
        if not isinstance(negative, str):
            self._json(400, {"error": "negative は文字列で指定してください。"})
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
    print("=== SDXL プロキシ起動（ステップ2） ===")
    print(f"ポート: {PORT}")
    print("経路: POST /generate")
    print("Ctrl+C で停止")
    print()
    HTTPServer(("", PORT), ProxyHandler).serve_forever()
