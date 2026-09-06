# sdxl-forge-api-automation

![生成例（SDXL・日本庭園に立つ女性）](docs/cover.png)

Stable Diffusion XL（SDXL）の画像生成を、WebUI Forge の画面を開かずに動かすプログラム。RunPod 上の WebUI Forge API（`/sdapi/v1/txt2img`）を対象に、11ステップに分けて段階的に作っている。

各ステップの解説記事（Zenn）:

- [Stable Diffusion XLをAPIで動かす（1/11）](https://zenn.dev/triponte/articles/sdxl-forge-api-automation-1) — 4つのファイルと、送信前の4つの確認
- [Stable Diffusion XLをAPIで動かす（2/11）](https://zenn.dev/triponte/articles/sdxl-forge-api-automation-2) — 画面を足しても、生成の入口は1つに保つ
- [Stable Diffusion XLをAPIで動かす（3/11）](https://zenn.dev/triponte/articles/sdxl-forge-api-automation-3) — プロンプトの正本をMarkdownファイルに置く

## 進み具合

| ステップ | 内容 | 状態 |
|---|---|---|
| 1 | コマンド1本で1枚生成（送信前の実在確認つき） | ✅ 済み（タグ `step-1`） |
| 2 | 画面から1枚生成（入力欄と生成ボタンだけ） | ✅ 済み（タグ `step-2`） |
| 3 | 画面で項目を選ぶ（Markdownファイル→HTML生成） | ✅ 済み（タグ `step-3`） |
| 4〜11 | モデル切り替え・複数枚・ControlNet・ADetailer・仕上げ | これから |

ステップが進むごとに、このリポジトリへコードを足していく。各ステップ時点の中身はタグで固定してある。

## ファイルの分担

| ファイル | 役割 |
|---|---|
| `settings.json` | 値の置き場。モデル名・ハッシュ・生成条件・モデルごとの縛り |
| `sdxl/settings_loader.py` | settings.json を読んで検証する。必要なキーが欠けていたら止める |
| `sdxl/model_rules.py` | モデルごとの作法を守らせる。サンプラーの縛り・CFGの範囲 |
| `sdxl/generate.py` | 進行役。送信前の確認 → 生成 → PNGメタデータとの照合 → 保存 |
| `sdxl/proxy.py` | 中継役。ブラウザからの依頼を受けて `generate_once()` を呼ぶ（ステップ2） |
| `sdxl/prompt_loader.py` | プロンプトの正本を読み、選んだ項目からプロンプトを組み立てる（ステップ3） |
| `prompts/` | プロンプトの正本（Markdownファイル）。画面の選択肢はここが出どころ |
| `build_html.py` | 正本を読んで画面のHTMLを書き出す（ステップ2〜3） |
| `html/` | `build_html.py` の生成物。ブラウザで開く画面 |

## 使い方

### コマンドから1枚

```bash
pip install requests
cd sdxl
python3 generate.py --url https://<PodID>-3000.proxy.runpod.net \
  --prompt "japanese woman, portrait, natural light" --seed 1234567890
```

- `--url` を省くと `settings.json` の `api.url` を使う
- `--dry-run` は送信前の確認だけを通して生成しない（GPU代がかからない）
- 保存先は `settings.json` の `output.dir`（既定は `~/sdxl_outputs`）

### 画面から1枚

```bash
python3 build_html.py          # 画面を書き出す（html/ の下にできる）
cd sdxl && python3 proxy.py    # 中継役を起動（localhost:8767）
```

そのうえで `html/IntegratedPromptGenerator_SDXL.html` をブラウザで開く。`settings.json` の `api.url` に Pod の URL を入れてから使う。

画面のプルダウンは `prompts/IntegratedPromptGenerator_SDXL.md` から作られる。選択肢を増やしたいときはこのMarkdownファイルに `- ` の行を足し、`python3 build_html.py` を打ち直す。`## 既定値` に書いた語は、どの生成にも必ず入る。

## 設計の考え方

Forge の生成APIは、実在しないモデル名・サンプラー名を渡してもエラーを出さず、黙って既定の設定で生成を続ける。だから送信前にモデル名・サンプラー名・スケジュール名の実在をAPIで確かめ、1つでも通らなければ生成せずに止める。生成後はPNGメタデータと指定値を照合してから合格とする。

画面を足したあとも、この確認と照合が通る道は1本のままにしてある。`proxy.py` は Forge API を直接呼ばず、コマンドと同じ `generate_once()` を呼ぶだけ。詳しくは上の解説記事に書いた。
