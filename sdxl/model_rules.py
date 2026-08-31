"""モデル固有の作法。

値は settings.json のプリセットが持ち、このファイルは「守らせる処理」だけを持つ。
モデルを足すときに直すのは settings.json であって、このファイルではない。

暗黙のフォールバックを作らない。縛りから外れた値は例外で止める。
"""


class ModelRuleError(ValueError):
    """プリセットの縛り（サンプラー・CFG）から外れた指定。"""


def check_sampler(preset: dict, sampler_name: str) -> None:
    """sampler_locked が true のとき、プリセットのサンプラー以外を受け付けない。

    NoobAI XL（V-Prediction）は Euler 以外だと画像が崩れるため。
    """
    if not preset.get("sampler_locked", False):
        return
    fixed = preset["base_params"]["sampler_name"]
    if sampler_name != fixed:
        raise ModelRuleError(
            f"このモデルはサンプラーが {fixed} に固定されています"
            f"（指定: {sampler_name}）"
        )


def check_cfg(preset: dict, cfg_scale: float) -> None:
    """cfg_range の外なら止める。範囲の指定が無いプリセットは素通り。"""
    rng = preset.get("cfg_range")
    if not rng:
        return
    low, high = rng
    if not low <= cfg_scale <= high:
        raise ModelRuleError(
            f"このモデルの CFG は {low}〜{high} です（指定: {cfg_scale}）"
        )


def apply_prefix(preset: dict, prompt: str) -> str:
    """prompt_prefix をプロンプトの先頭に付ける（Pony のスコアタグなど）。"""
    prefix = preset.get("prompt_prefix", "").strip()
    if not prefix:
        return prompt
    if not prompt.strip():
        return prefix
    return f"{prefix}, {prompt}"


def apply_negative(preset: dict, negative: str) -> str:
    """negative_prefix を Negative の先頭に付ける。"""
    prefix = preset.get("negative_prefix", "").strip()
    if not prefix:
        return negative
    if not negative.strip():
        return prefix
    return f"{prefix}, {negative}"


def commercial_suffix(preset: dict) -> str:
    """商用不可のモデルなら画像のファイル名に付ける印を返す。

    後から画像を見て「どのモデルで作ったか」が分かるようにする。
    """
    return "_NC" if preset.get("commercial_use") == "prohibited" else ""
