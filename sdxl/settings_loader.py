"""settings.json の読み込みと検証。

プリセットの必須キー（prompt_prefix / negative_prefix / sampler_locked /
cfg_range / license / commercial_use）と model_hash を検証する。

暗黙のフォールバックを作らない。不備は例外で止める。
"""

import copy
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent
SETTINGS_FILE = BASE_DIR.parent / "settings.json"

COMMERCIAL_USE_VALUES = {"allowed", "conditional", "prohibited"}


class SettingsError(ValueError):
    """settings.json の不備。"""


def _require_str(preset: dict, name: str, key: str, allow_empty: bool = False) -> None:
    value = preset.get(key)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise SettingsError(
            f"プリセット '{name}' の {key} は"
            f"{'' if allow_empty else '非空の'}文字列で指定してください: {value!r}"
        )


def validate_preset(name: str, preset: dict) -> None:
    """1つのプリセットが必要なキーを揃えているか確かめる。"""
    if not isinstance(preset, dict):
        raise SettingsError(f"プリセット '{name}' はオブジェクトで指定してください")

    _require_str(preset, name, "model")
    _require_str(preset, name, "model_hash")
    _require_str(preset, name, "license")
    _require_str(preset, name, "prompt_prefix", allow_empty=True)
    _require_str(preset, name, "negative_prefix", allow_empty=True)

    base = preset.get("base_params")
    if not isinstance(base, dict):
        raise SettingsError(f"プリセット '{name}' に base_params がありません")
    for key in ("steps", "cfg_scale", "width", "height"):
        value = base.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SettingsError(
                f"プリセット '{name}' の base_params.{key} は数値で指定してください: {value!r}"
            )
    if not isinstance(base.get("sampler_name"), str) or not base["sampler_name"].strip():
        raise SettingsError(
            f"プリセット '{name}' の base_params.sampler_name は非空の文字列で指定してください"
        )

    if not isinstance(preset.get("sampler_locked"), bool):
        raise SettingsError(
            f"プリセット '{name}' の sampler_locked は true/false で指定してください:"
            f" {preset.get('sampler_locked')!r}"
        )

    rng = preset.get("cfg_range")
    if (
        not isinstance(rng, list)
        or len(rng) != 2
        or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in rng)
        or rng[0] > rng[1]
    ):
        raise SettingsError(
            f"プリセット '{name}' の cfg_range は [下限, 上限] の数値2つで指定してください: {rng!r}"
        )

    commercial = preset.get("commercial_use")
    if commercial not in COMMERCIAL_USE_VALUES:
        raise SettingsError(
            f"プリセット '{name}' の commercial_use は"
            f" {' / '.join(sorted(COMMERCIAL_USE_VALUES))} のいずれかです: {commercial!r}"
        )


def load_raw_settings() -> dict:
    """settings.json をそのまま読む。無ければ例外で止める（既定値を持たない）。"""
    if not SETTINGS_FILE.exists():
        raise SettingsError(f"settings.json が見つかりません: {SETTINGS_FILE}")
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))


def resolve_model_preset(raw: dict) -> dict:
    """active_model_preset を解決した実効 settings を返す（raw は変更しない）。

    - api.model     ← プリセットの model（sd-models の model_name）
    - api.model_hash← プリセットの model_hash（PNG メタデータの照合に使う）
    - base_params   ← {**トップ base_params, **プリセット base_params}
    - preset        ← アクティブなプリセットそのもの（model_rules へ渡す）
    - preset_name   ← アクティブなプリセット名（ファイル名に使う）
    """
    presets = raw.get("model_presets")
    if not presets:
        raise SettingsError("settings.json に model_presets が定義されていません")
    choices = ", ".join(presets)
    active = raw.get("active_model_preset")
    if not active:
        raise SettingsError(f"active_model_preset が未設定です（選択肢: {choices}）")
    if active not in presets:
        raise SettingsError(
            f"active_model_preset '{active}' は model_presets にありません（選択肢: {choices}）"
        )
    for name in sorted(presets):
        validate_preset(name, presets[name])

    preset = presets[active]
    effective = copy.deepcopy(raw)
    effective["api"]["model"] = preset["model"]
    effective["api"]["model_hash"] = preset["model_hash"]
    effective["base_params"] = {
        **raw.get("base_params", {}),
        **preset["base_params"],
    }
    effective["preset"] = copy.deepcopy(preset)
    effective["preset_name"] = active
    return effective


def load_settings() -> dict:
    """実効 settings（プリセット解決済み）を返す。生成side は必ずこれを読む。"""
    return resolve_model_preset(load_raw_settings())
