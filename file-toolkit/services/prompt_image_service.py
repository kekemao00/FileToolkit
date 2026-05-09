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
        return {"success": False, "error": "未配置 AI 生图 API Key，请在设置中配置",
                "image_bytes": None, "image_url": None}

    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "prompt": prompt,
        "n": n,
        "size": size,
        "quality": quality,
        "output_format": output_format,
    }
    url = f"{config['base_url'].rstrip('/')}/images/generations"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            items = data.get("data") or []
            if not items:
                return {"success": False, "error": "API 返回数据格式异常：data 为空",
                        "image_bytes": None, "image_url": None}

            item = items[0]
            if "b64_json" in item and item["b64_json"]:
                image_bytes = base64.b64decode(item["b64_json"])
                return {"success": True, "image_bytes": image_bytes,
                        "image_url": None, "error": ""}

            if "url" in item and item["url"]:
                img_resp = await client.get(item["url"])
                img_resp.raise_for_status()
                return {"success": True, "image_bytes": img_resp.content,
                        "image_url": item["url"], "error": ""}

            return {"success": False, "error": "API 返回数据未包含 b64_json / url",
                    "image_bytes": None, "image_url": None}

    except httpx.HTTPStatusError as e:
        body = e.response.text[:200] if e.response is not None else ""
        return {"success": False, "error": f"API 请求失败 ({e.response.status_code}): {body}",
                "image_bytes": None, "image_url": None}
    except httpx.TimeoutException:
        return {"success": False, "error": "请求超时，请稍后重试",
                "image_bytes": None, "image_url": None}
    except Exception as e:
        return {"success": False, "error": f"生成失败: {e}",
                "image_bytes": None, "image_url": None}


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
