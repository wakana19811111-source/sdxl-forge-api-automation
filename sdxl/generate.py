"""SDXL 生成（ステップ1：画面なしで1枚）。

使い方:
  python3 generate.py --url https://<PodID>-3000.proxy.runpod.net \
                      --prompt "japanese woman, portrait" --seed 1234567890

  --url を省くと settings.json の api.url を使う。
  --dry-run は送信前の3つの関門だけを通して生成しない（Pod 代がかからない）。

⛔ Forge の override_settings は値の型しか見ない。実在しないモデル名・サンプラー名を
   渡してもエラーを出さず黙って既定にフォールバックする。
   だから送信前に自分で確かめ、生成後は PNG メタデータで裏取りする。
"""

import argparse
import base64
import json
import os
import sys
import zlib
from datetime import datetime

import requests

import model_rules
from settings_loader import SettingsError, load_settings

# RunPod のプロキシ（Cloudflare）は100秒で接続を切る。SDXL のモデル初回ロードは約120秒
# かかるので、1枚目は必ず切られる（2026-08-29 実測）。捨て生成でロードだけ済ませる。
WARMUP_TIMEOUT = 110
GENERATE_TIMEOUT = 600


class GenerateError(RuntimeError):
    """生成を続けてはいけない状態。"""


# --- 送信前の3つの関門（6-1） ---------------------------------------------

def check_model_exists(api_url: str, model_name: str) -> str:
    """sd-models に model_name が実在するか確かめ、送信に使う title を返す。

    ⚠ title はモデルのロード前後で変わる（ロード後は末尾に [hash] が付く）ので、
      照合は model_name で行う（2026-08-29 実測・事前調査_20260829.md）。
    """
    res = requests.get(f"{api_url}/sdapi/v1/sd-models", timeout=60)
    res.raise_for_status()
    models = res.json()
    for m in models:
        if m.get("model_name") == model_name:
            return m["title"]
    names = ", ".join(sorted(m.get("model_name", "?") for m in models))
    raise GenerateError(
        f"モデル '{model_name}' が Pod にありません（配置済み: {names}）"
    )


def check_scheduler_exists(api_url: str, scheduler: str) -> None:
    """schedulers に scheduler が実在するか確かめる。

    ⚠ Forge はサンプラーとスケジューラを分けて持つ。`DPM++ 2M Karras` という
      1つの名前は samplers に無く、`DPM++ 2M` ＋ `karras` の2つに分かれる
      （2026-08-30 に実機で判明）。⛔ 名前を繋げて送ると黙って既定に落ちる。
    """
    res = requests.get(f"{api_url}/sdapi/v1/schedulers", timeout=60)
    res.raise_for_status()
    known = {s.get("name") for s in res.json()}
    for s in res.json():
        known.update(s.get("aliases") or [])
    if scheduler not in known:
        raise GenerateError(
            f"スケジューラ '{scheduler}' が Pod にありません"
            f"（使えるもの: {', '.join(sorted(n for n in known if n))}）"
        )


def check_sampler_exists(api_url: str, sampler_name: str) -> None:
    """samplers に sampler_name が実在するか確かめる。"""
    res = requests.get(f"{api_url}/sdapi/v1/samplers", timeout=60)
    res.raise_for_status()
    samplers = res.json()
    known = {s.get("name") for s in samplers}
    for s in samplers:
        known.update(s.get("aliases") or [])
    if sampler_name not in known:
        raise GenerateError(
            f"サンプラー '{sampler_name}' が Pod にありません"
            f"（使えるもの: {', '.join(sorted(n for n in known if n))}）"
        )


# --- PNG メタデータの裏取り（6-3） ----------------------------------------

def read_png_parameters(image_bytes: bytes) -> str:
    """PNG の tEXt / iTXt チャンクから 'parameters' の中身を取り出す。"""
    if image_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise GenerateError("PNG として読めないデータが返りました")
    pos = 8
    while pos + 8 <= len(image_bytes):
        length = int.from_bytes(image_bytes[pos:pos + 4], "big")
        ctype = image_bytes[pos + 4:pos + 8]
        data = image_bytes[pos + 8:pos + 8 + length]
        pos += 12 + length  # 4(len) + 4(type) + data + 4(crc)
        if ctype == b"tEXt":
            key, _, value = data.partition(b"\x00")
            if key == b"parameters":
                return value.decode("utf-8", "replace")
        elif ctype == b"iTXt":
            key, _, rest = data.partition(b"\x00")
            if key != b"parameters":
                continue
            compressed = rest[0:1]
            body = rest[2:].split(b"\x00", 2)[-1]
            return (
                zlib.decompress(body) if compressed == b"\x01" else body
            ).decode("utf-8", "replace")
        elif ctype == b"IEND":
            break
    raise GenerateError("PNG に parameters（生成条件）が入っていません")


def parse_parameters(text: str) -> dict:
    """parameters の最終行（Steps: ... , Model hash: ... の並び）を dict にする。"""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}
    info = {}
    for part in lines[-1].split(","):
        key, sep, value = part.partition(":")
        if sep:
            info[key.strip()] = value.strip()
    return info


def verify_png(image_bytes: bytes, settings: dict, seed: int) -> dict:
    """Model hash・Size・Seed を照合する。食い違えば「成功」と言わない。"""
    info = parse_parameters(read_png_parameters(image_bytes))
    base = settings["base_params"]
    expected = {
        "Model hash": settings["api"]["model_hash"],
        "Size": f"{base['width']}x{base['height']}",
        "Seed": str(seed),
    }
    mismatch = [
        f"{k}: 期待 {v} / 実際 {info.get(k, '(なし)')}"
        for k, v in expected.items()
        if info.get(k) != v
    ]
    if mismatch:
        raise GenerateError(
            "PNG メタデータが指定と食い違いました（黙ってフォールバックした疑い）\n  "
            + "\n  ".join(mismatch)
        )
    return info


# --- 生成 ------------------------------------------------------------------

def build_payload(settings: dict, title: str, prompt: str, negative: str) -> dict:
    preset = settings["preset"]
    return {
        **settings["base_params"],
        "prompt": model_rules.apply_prefix(preset, prompt),
        "negative_prompt": model_rules.apply_negative(preset, negative),
        "override_settings": {
            "sd_model_checkpoint": title,
            "sd_vae": settings["api"].get("sd_vae", "None"),
        },
    }


def warmup(api_url: str, title: str, sd_vae: str) -> None:
    """モデルをロードさせるための捨て生成。切られても失敗にしない。"""
    payload = {
        "prompt": "warmup", "steps": 1, "width": 512, "height": 512,
        "batch_size": 1, "seed": 1,
        "override_settings": {"sd_model_checkpoint": title, "sd_vae": sd_vae},
    }
    try:
        requests.post(
            f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=WARMUP_TIMEOUT
        )
    except requests.RequestException:
        pass  # 初回ロード120秒でプロキシが切るのは想定どおり
    print("  （モデルのロードを待ちました）")


def generate(settings: dict, title: str, prompt: str, negative: str) -> list:
    api_url = settings["api"]["url"].rstrip("/")
    payload = build_payload(settings, title, prompt, negative)
    res = requests.post(
        f"{api_url}/sdapi/v1/txt2img", json=payload, timeout=GENERATE_TIMEOUT
    )
    res.raise_for_status()
    result = res.json()
    info = json.loads(result.get("info", "{}"))
    batch_size = payload.get("batch_size", 1)
    images = result["images"][:batch_size]
    seeds = info.get("all_seeds") or [info.get("seed", -1)] * len(images)
    return [
        (base64.b64decode(b64), seeds[i] if i < len(seeds) else -1)
        for i, b64 in enumerate(images)
    ]


def save_image(image_bytes: bytes, settings: dict, seed: int, counter: int) -> str:
    output_dir = os.path.expanduser(settings["output"]["dir"])
    os.makedirs(output_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = model_rules.commercial_suffix(settings["preset"])
    name = f"{stamp}_{counter:03d}_{settings['preset_name']}_seed{seed}{suffix}.png"
    path = os.path.join(output_dir, name)
    with open(path, "wb") as f:
        f.write(image_bytes)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="SDXL 生成（ステップ1）")
    parser.add_argument("--url", help="Pod の proxy URL（settings.json を上書き）")
    parser.add_argument("--prompt", default="japanese woman, portrait, natural light")
    parser.add_argument("--negative", default="")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--steps", type=int)
    parser.add_argument("--cfg", type=float)
    parser.add_argument("--sampler")
    parser.add_argument("--no-warmup", action="store_true", help="捨て生成をしない")
    parser.add_argument("--dry-run", action="store_true", help="関門だけ通して生成しない")
    args = parser.parse_args()

    settings = load_settings()
    if args.url:
        settings["api"]["url"] = args.url
    for key, value in (
        ("seed", args.seed), ("steps", args.steps),
        ("cfg_scale", args.cfg), ("sampler_name", args.sampler),
    ):
        if value is not None:
            settings["base_params"][key] = value

    api_url = settings["api"]["url"].rstrip("/")
    if not api_url:
        raise GenerateError("api.url が空です（--url で Pod の URL を渡してください）")

    preset = settings["preset"]
    base = settings["base_params"]
    print("=== SDXL 生成（ステップ1） ===")
    print(f"プリセット: {settings['preset_name']}（{preset['license']}"
          f" / 商用: {preset['commercial_use']}）")
    print(f"モデル:     {settings['api']['model']}  hash {settings['api']['model_hash']}")
    print(f"条件:       {base['width']}x{base['height']} / {base['steps']} steps"
          f" / CFG {base['cfg_scale']} / {base['sampler_name']}"
          f" / scheduler {base.get('scheduler', '(指定なし)')}")
    print(f"保存先:     {settings['output']['dir']}")
    print()

    # 6-1 送信前の3つの関門
    title = check_model_exists(api_url, settings["api"]["model"])
    check_sampler_exists(api_url, base["sampler_name"])
    if base.get("scheduler"):
        check_scheduler_exists(api_url, base["scheduler"])
    model_rules.check_sampler(preset, base["sampler_name"])
    model_rules.check_cfg(preset, base["cfg_scale"])
    print(f"✅ 関門を通過（送信する checkpoint: {title}）")

    if args.dry_run:
        print("--dry-run のため生成しません。")
        return 0

    if not args.no_warmup:
        warmup(api_url, title, settings["api"].get("sd_vae", "None"))

    print("生成中...")
    results = generate(settings, title, args.prompt, args.negative)
    for counter, (image_bytes, seed) in enumerate(results, start=1):
        info = verify_png(image_bytes, settings, seed)
        path = save_image(image_bytes, settings, seed, counter)
        print(f"✅ 保存: {path}")
        print(f"   Model hash {info['Model hash']} / Size {info['Size']} / Seed {info['Seed']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (GenerateError, SettingsError, model_rules.ModelRuleError) as e:
        print(f"🔴 停止: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as e:
        print(f"🔴 通信エラー: {e}", file=sys.stderr)
        sys.exit(1)
