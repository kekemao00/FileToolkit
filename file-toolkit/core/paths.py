"""输出路径工具：不覆盖已有文件，也绝不写回输入文件本身。"""
from collections.abc import Iterable
from pathlib import Path


def _same(a: Path, b: Path) -> bool:
    try:
        return a.resolve() == b.resolve()
    except OSError:
        return a.absolute() == b.absolute()


def unique_path(path: Path, avoid: Iterable[Path] = ()) -> Path:
    """目标已存在（或与 avoid 中的路径相同）时追加 _1、_2…。

    avoid 传入本批输入文件，防止「输出目录 = 源目录、格式相同」时把源文件覆盖掉。
    """
    avoid = list(avoid)

    def taken(p: Path) -> bool:
        return p.exists() or any(_same(p, a) for a in avoid)

    if not taken(path):
        return path
    i = 1
    while taken(candidate := path.with_name(f"{path.stem}_{i}{path.suffix}")):
        i += 1
    return candidate


def reserve(path: Path, claimed: set[Path], avoid: Iterable[Path] = ()) -> Path:
    """同一批里还没写盘的输出也要避开（如 a.png、a.jpg 都转成 a.webp）。"""
    avoid = list(avoid) + list(claimed)
    out = unique_path(path, avoid)
    claimed.add(out)
    return out
