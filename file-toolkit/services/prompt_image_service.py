"""AI 生图服务 — 调用 gpt-image-2 / OpenAI Images API 兼容接口。

设计目标：
- 与 settings_service 解耦运行时配置，允许用户在"设置"页填写 API Key / Base URL / Model
- 纯异步：上层通过 page.run_task() 触发，不阻塞 UI
- 返回统一的 dict，保证 UI 层只需关心 success + image_bytes + error 三个字段
"""
from __future__ import annotations

import base64
import time
from pathlib import Path

import httpx

# 默认值：OpenAI 官方端点 + gpt-image-2
DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-2"


def get_api_config() -> dict:
    """从 settings_service 读取 AI 生图配置。"""
    from services import settings_service
    return {
        "api_key": settings_service.get("ai_image_api_key", ""),
        "base_url": settings_service.get("ai_image_base_url", "") or DEFAULT_BASE_URL,
        "model": settings_service.get("ai_image_model", "") or DEFAULT_MODEL,
    }


def is_configured() -> bool:
    """API Key 是否已配置。"""
    return bool(get_api_config()["api_key"])


async def generate_image(
    prompt: str,
    size: str = "1024x1024",
    quality: str = "high",
    output_format: str = "png",
    n: int = 1,
) -> dict:
    """调用生图接口。

    Args:
        prompt: 完整英文/中文提示词
        size: 图片尺寸（1024x1024 / 1024x1536 / 1536x1024 / auto）
        quality: 质量（low / medium / high / auto）
        output_format: 输出格式（png / jpeg / webp）
        n: 生成张数

    Returns:
        dict: {"success": bool, "image_bytes": bytes | None,
               "image_url": str | None, "error": str}
    """
    config = get_api_config()
    if not config["api_key"]:
        return _fail("未配置 AI 生图 API Key，请在设置中配置")

    payload = {
        "model": config["model"],
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }
    url = f"{config['base_url'].rstrip('/')}/images/generations"
    return await _request(url, config["api_key"], json=payload)


async def edit_image(
    prompt: str,
    images: list[Path],
    size: str = "1024x1024",
    quality: str = "high",
    output_format: str = "png",
    n: int = 1,
) -> dict:
    """带参考图生成（OpenAI Images 的 /images/edits 接口，gpt-image 系列支持多张参考图）。

    参考图以 multipart 上传：一张时字段名 image，多张时 image[]。返回值同 generate_image。
    """
    config = get_api_config()
    if not config["api_key"]:
        return _fail("未配置 AI 生图 API Key，请在设置中配置")
    if not images:
        return _fail("没有参考图")
    try:
        files = [("image[]" if len(images) > 1 else "image", _image_part(Path(p)))
                 for p in images]
    except (OSError, ValueError) as e:
        return _fail(f"参考图读取失败：{e}")

    data = {
        "model": config["model"],
        "prompt": prompt,
        "n": str(n),
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }
    url = f"{config['base_url'].rstrip('/')}/images/edits"
    result = await _request(url, config["api_key"], data=data, files=files)
    if not result["success"] and result.get("status") in (404, 405, 501):
        result["error"] = ("当前接口不支持参考图（/images/edits 不可用）。请在设置里换成支持图片编辑的"
                           f"服务商或模型（如 gpt-image-2）。原始信息：{result['error']}")
    elif not result["success"] and result.get("status") == 400 and _looks_unsupported(result["error"]):
        result["error"] = (f"当前模型不支持参考图生成，请在设置里换成支持图片编辑的模型（如 gpt-image-2）。"
                           f"原始信息：{result['error']}")
    return result


# 接口直接接受的格式；其他格式（bmp / tiff 等）先转成 PNG
_DIRECT_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                 ".webp": "image/webp"}
MAX_REFERENCE_BYTES = 25 * 1024 * 1024
_MAX_REFERENCE_SIDE = 2048


def _image_part(path: Path) -> tuple[str, bytes, str]:
    """读一张参考图，返回 multipart 文件三元组；超大或非常见格式压成 PNG / JPEG。"""
    raw = path.read_bytes()
    mime = _DIRECT_TYPES.get(path.suffix.lower())
    if mime and len(raw) <= MAX_REFERENCE_BYTES:
        return path.name, raw, mime
    import io

    from PIL import Image, ImageOps
    with Image.open(io.BytesIO(raw)) as im:
        im = ImageOps.exif_transpose(im)
        im.thumbnail((_MAX_REFERENCE_SIDE, _MAX_REFERENCE_SIDE))
        buf = io.BytesIO()
        if im.mode in ("RGBA", "LA", "P"):
            im.convert("RGBA").save(buf, "PNG", optimize=True)
            return f"{path.stem}.png", buf.getvalue(), "image/png"
        im.convert("RGB").save(buf, "JPEG", quality=92)
        return f"{path.stem}.jpg", buf.getvalue(), "image/jpeg"


def _looks_unsupported(error: str) -> bool:
    low = error.lower()
    return any(k in low for k in ("not supported", "unsupported", "does not support",
                                  "invalid model", "only supports", "不支持"))


def _fail(error: str, status: int | None = None) -> dict:
    return {"success": False, "error": error, "image_bytes": None, "image_url": None,
            "status": status}


# 生图（尤其是高质量 + 参考图）经常要 1–3 分钟，读超时放宽；连接超时保持较短，断网时尽快报错
_TIMEOUT = httpx.Timeout(connect=20.0, read=300.0, write=120.0, pool=20.0)


async def _request(url: str, api_key: str, **kwargs) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, headers=headers, **kwargs)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data") or []
            if not items:
                return _fail("API 返回数据格式异常：data 为空")

            item = items[0]
            if "b64_json" in item and item["b64_json"]:
                image_bytes = base64.b64decode(item["b64_json"])
                return {"success": True, "image_bytes": image_bytes,
                        "image_url": None, "error": "", "status": resp.status_code}

            if "url" in item and item["url"]:
                img_resp = await client.get(item["url"])
                img_resp.raise_for_status()
                return {"success": True, "image_bytes": img_resp.content,
                        "image_url": item["url"], "error": "", "status": resp.status_code}

            return _fail("API 返回数据未包含 b64_json / url")

    except httpx.HTTPStatusError as e:
        body = e.response.text[:300] if e.response is not None else ""
        return _fail(f"API 请求失败 ({e.response.status_code}): {body}", e.response.status_code)
    except httpx.TimeoutException:
        return _fail("请求超时：服务器长时间没有返回，请稍后重试，或把质量调低")
    except Exception as e:
        return _fail(f"生成失败: {e}")


def default_output_dir() -> Path:
    """默认保存目录：优先使用设置中的输出目录，否则 ~/.file-toolkit/generated。"""
    from services import settings_service
    configured = settings_service.get("default_output_dir", "")
    if configured:
        return Path(configured) / "prompt_image"
    return Path.home() / ".file-toolkit" / "generated"


def save_image(
    image_bytes: bytes,
    output_dir: Path | None = None,
    filename: str = "",
    ext: str = "png",
) -> Path:
    """保存生图结果到本地，返回文件路径。"""
    if output_dir is None:
        output_dir = default_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"prompt_image_{int(time.time())}.{ext}"
    elif not filename.lower().endswith(f".{ext}"):
        filename = f"{filename}.{ext}"
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)
    return output_path


async def check_connection() -> tuple[bool, str]:
    """校验 Key 和 Base URL：请求 GET /models（不生成图片、不消耗额度）。

    返回 (是否可用, 给用户看的说明)。有些兼容服务不提供 /models，此时只能确认地址可达。
    """
    config = get_api_config()
    if not config["api_key"]:
        return False, "请先填写 API Key"
    url = f"{config['base_url'].rstrip('/')}/models"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0)) as client:
            resp = await client.get(url, headers={"Authorization": f"Bearer {config['api_key']}"})
    except httpx.TimeoutException:
        return False, "连接超时，请检查 Base URL 和网络"
    except httpx.HTTPError as e:
        return False, f"无法连接：{e.__class__.__name__}，请检查 Base URL"
    if resp.status_code in (401, 403):
        return False, "API Key 无效或没有权限"
    if resp.status_code in (404, 405):
        return True, "地址可以访问（该服务不提供模型列表，Key 需在生成时验证）"
    if resp.status_code >= 400:
        return False, f"连接失败（HTTP {resp.status_code}）"
    try:
        ids = {m.get("id") for m in resp.json().get("data", []) if isinstance(m, dict)}
    except ValueError:
        ids = set()
    if ids and config["model"] not in ids:
        return True, f"连接成功，但没有找到模型「{config['model']}」，请确认模型名称"
    return True, "连接成功，API Key 有效"
