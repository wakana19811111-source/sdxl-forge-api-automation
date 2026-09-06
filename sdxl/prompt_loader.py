"""プロンプトの正本（Markdownファイル）を読む／選んだ項目からプロンプトを組み立てる。

正本: prompts/IntegratedPromptGenerator_SDXL.md
  ## 既定値          → プルダウンにしない。### prompt / ### negative の `- ` 行が全生成に入る
  ## 被写体 など     → 既定値以外の見出し1つ＝プルダウン1つ。`- ` 行が選択肢
  「指定なし」は画面（build_html.py）が先頭に足す——Markdownファイルには書かない。

⛔ プリセットの prompt_prefix / negative_prefix はここでは付けない。
   ステップ1から generate_once() の中で model_rules.apply_prefix / apply_negative が
   付けており、ここでも付けると二重になる。
"""

from pathlib import Path

PROMPTS_FILE = (
    Path(__file__).parent.parent / "prompts" / "IntegratedPromptGenerator_SDXL.md"
)

DEFAULT_SECTION = "既定値"


class PromptFileError(RuntimeError):
    """Markdownファイルが無い・形式が崩れていて画面を作れない状態。"""


class StaleChoiceError(RuntimeError):
    """画面から来た項目が Markdownファイルに無い（HTML だけ古いまま使った）状態。"""


def load_items(path: Path = PROMPTS_FILE) -> dict:
    """Markdownファイルを読み、既定値とプルダウンの項目一覧を返す。

    返り値: {
        "prompt_defaults":   [既定値 prompt の行, ...],
        "negative_defaults": [既定値 negative の行, ...],
        "sections":          {"被写体": [選択肢, ...], ...}（Markdownの並び順）
    }
    ⛔ ファイルが無い・## が1つも無い・プルダウンになる見出しが無いときは
       PromptFileError で止まる（空の画面を黙って作らない）。
    """
    if not path.exists():
        raise PromptFileError(f"Markdownファイルがありません: {path}")

    prompt_defaults = []
    negative_defaults = []
    sections = {}
    section = None        # いま読んでいる ## 見出し
    default_target = None  # 既定値の中の ### prompt / ### negative

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip()
            default_target = None
            if section != DEFAULT_SECTION:
                sections.setdefault(section, [])
        elif stripped.startswith("### ") and section == DEFAULT_SECTION:
            default_target = stripped[4:].strip()
        elif stripped.startswith("- ") and section:
            item = stripped[2:].strip()
            if not item:
                continue
            if section == DEFAULT_SECTION:
                if default_target == "prompt":
                    prompt_defaults.append(item)
                elif default_target == "negative":
                    negative_defaults.append(item)
            else:
                sections[section].append(item)

    if section is None:
        raise PromptFileError(f"Markdownファイルに ## 見出しが1つもありません: {path}")
    if not sections:
        raise PromptFileError(
            f"既定値以外の ## 見出し（プルダウンになる項目）がありません: {path}"
        )

    return {
        "prompt_defaults": prompt_defaults,
        "negative_defaults": negative_defaults,
        "sections": sections,
    }


def build_prompt(data: dict, selections: dict, free_text: str = "") -> tuple:
    """選んだ項目からプロンプトを組み立てる（処理の流れ_ステップ3 の 2）。

    並び順: 1. 既定値 prompt 行 → 2. 選んだ項目（プルダウンの順） → 3. 自由文。
    「, 」でつなぐ。negative は既定値 negative 行のみ。
    重み付けの記法（(smiling:1.2) など）はそのまま通す。

    selections: {"被写体": "1girl, japanese, long hair", ...}。空文字の値は「指定なし」扱い。
    Markdownに無い見出し・選択肢が来たら StaleChoiceError（HTML だけ古いまま使った状態）。
    返り値: (prompt, negative)
    """
    sections = data["sections"]
    picked = {
        name: value.strip()
        for name, value in selections.items()
        if isinstance(value, str) and value.strip()
    }

    unknown = [name for name in picked if name not in sections]
    if unknown:
        raise StaleChoiceError(
            f"プルダウン『{'』『'.join(unknown)}』が Markdownファイルにありません"
        )

    parts = list(data["prompt_defaults"])
    for name, choices in sections.items():  # プルダウンの順＝Markdownの並び順
        value = picked.get(name)
        if not value:
            continue
        if value not in choices:
            raise StaleChoiceError(
                f"『{name}』の選択肢 '{value}' が Markdownファイルにありません"
            )
        parts.append(value)

    free_text = (free_text or "").strip()
    if free_text:
        parts.append(free_text)

    return ", ".join(parts), ", ".join(data["negative_defaults"])
