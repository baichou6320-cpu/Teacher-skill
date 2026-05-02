"""文件加载器 — 统一入口，支持文本文件和 PDF。

按扩展名自动分发：
  .md / .txt -> 文本读取（自动编码检测）
  .pdf       -> pypdf 文本提取
"""
from pathlib import Path
from typing import Union


class FileLoadError(Exception):
    """文件加载异常基类."""
    pass


class UnsupportedFormatError(FileLoadError):
    """不支持的文件格式."""
    pass


class FileNotFoundError(FileLoadError):
    """文件不存在."""
    pass


class EncodingError(FileLoadError):
    """无法识别文件编码."""
    pass


# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {".md", ".txt", ".pdf"}


def load_file(path: Union[str, Path]) -> str:
    """加载文件内容，按扩展名自动分发。

    Args:
        path: 文件路径，支持 str 或 Path。

    Returns:
        文件文本内容。

    Raises:
        FileNotFoundError: 文件不存在。
        UnsupportedFormatError: 文件扩展名不在支持列表中。
        EncodingError: 文本文件编码无法识别。
        FileLoadError: 其他加载错误（如 PDF 库未安装）。
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFormatError(
            f"不支持的文件格式: {ext}。支持: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if ext == ".pdf":
        return _load_pdf(path)

    return _load_text(path)


def _load_text(path: Path) -> str:
    """加载文本文件，自动检测编码。

    尝试顺序: utf-8 -> gbk -> utf-16 -> latin-1。

    Args:
        path: 文本文件路径。

    Returns:
        文件文本内容。

    Raises:
        EncodingError: 所有编码尝试均失败。
    """
    for encoding in ("utf-8", "gbk", "utf-16", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except UnicodeDecodeError:
            continue

    raise EncodingError(f"无法解码文件: {path}")


def _load_pdf(path: Path) -> str:
    """使用 pypdf 提取 PDF 文本。

    Args:
        path: PDF 文件路径。

    Returns:
        提取的文本内容，各页以双换行分隔。

    Raises:
        FileLoadError: pypdf 未安装，或 PDF 无法读取。
    """
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise FileLoadError(
            "读取 PDF 需要安装 pypdf: pip install pypdf"
        ) from exc

    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        raise FileLoadError(f"无法读取 PDF 文件: {path}") from exc

    texts = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text.strip())

    return "\n\n".join(texts)
