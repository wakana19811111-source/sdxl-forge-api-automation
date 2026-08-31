# sdxl-forge-api-automation

![生成例（SDXL・日本庭園に立つ女性）](docs/cover.png)

Stable Diffusion XL（SDXL）の画像生成を、WebUI Forge の画面を開かずにコマンド1本で動かすプログラム。RunPod 上の WebUI Forge API（`/sdapi/v1/txt2img`）を対象に、11ステップに分けて段階的に作っている。

各ステップの解説記事（Zenn）: [SDXLをAPIで動かす（1）4つのファイルと、送信前の4つの確認](https://zenn.dev/triponte/articles/sdxl-forge-api-automation-1)

## 進み具合

| ステップ | 内容 | 状態 |
|---|---|---|
| 1 | コマンド1本で1枚生成（送信前の実在確認つき） | ✅ 済み |
| 2 | 画面から1枚生成 | これから |
| 3〜11 | 順次 | これから |

ステップが進むごとに、このリポジトリへコードを足していく。

## ファイルの分担

| ファイル | 役割 |
|---|---|
| `settings.json` | 値の置き場。モデル名・ハッシュ・生成条件・モデルごとの縛り |
| `sdxl/settings_loader.py` | settings.json を読んで検証する。必要なキーが欠けていたら止める |
| `sdxl/model_rules.py` | モデルごとの作法を守らせる。サンプラーの縛り・CFGの範囲 |
| `sdxl/generate.py` | 進行役。送信前の確認 → 生成 → PNGメタデータとの照合 → 保存 |

## 使い方

```bash
pip install requests
cd sdxl
python3 generate.py --url https://<PodID>-3000.proxy.runpod.net \
  --prompt "japanese woman, portrait, natural light" --seed 1234567890
```

- `--url` を省くと `settings.json` の `api.url` を使う
- `--dry-run` は送信前の確認だけを通して生成しない（GPU代がかからない）
- 保存先は `settings.json` の `output.dir`（既定は `~/sdxl_outputs`）

## 設計の考え方

Forge の生成APIは、実在しないモデル名・サンプラー名を渡してもエラーを出さず、黙って既定の設定で生成を続ける。だから送信前にモデル名・サンプラー名・スケジュール名の実在をAPIで確かめ、1つでも通らなければ生成せずに止める。生成後はPNGメタデータと指定値を照合してから合格とする。詳しくは上の解説記事に書いた。
