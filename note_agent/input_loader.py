# note_agent/input_loader.py

from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


SUPPORTED_TEXT_SUFFIXES = {".txt", ".md"}


def read_text_file(file_path: str) -> str:
    """读取本地 .txt / .md 文件。"""
    path = Path(file_path.strip().strip('"').strip("'"))

    if not path.exists():
        raise FileNotFoundError(f"文件不存在：{path}")

    if path.suffix.lower() not in SUPPORTED_TEXT_SUFFIXES:
        raise ValueError(f"暂不支持该文件类型：{path.suffix}，当前仅支持 .txt / .md")

    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(f"文件内容为空：{path}")

    return content


def read_uploaded_text_file(filename: str, content: bytes) -> str:
    """读取 Streamlit 上传的 .txt / .md 文件。"""
    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_TEXT_SUFFIXES:
        raise ValueError(f"暂不支持该文件类型：{suffix}，当前仅支持 .txt / .md")

    text = content.decode("utf-8", errors="ignore").strip()

    if not text:
        raise ValueError(f"上传文件内容为空：{filename}")

    return text


def is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def fetch_webpage_text(url: str, timeout: int = 20) -> str:
    """抓取网页正文文本。"""
    url = url.strip()

    if not is_valid_url(url):
        raise ValueError(f"URL 格式不合法：{url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()

    title = soup.title.get_text(" ", strip=True) if soup.title else ""

    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_text = "\n".join(lines)

    if not cleaned_text:
        raise ValueError(f"网页正文提取失败：{url}")

    return f"# 网页标题：{title}\n# 网页链接：{url}\n\n{cleaned_text}"


def build_combined_input(
    manual_text: str = "",
    file_texts: Iterable[tuple[str, str]] | None = None,
    webpage_texts: Iterable[tuple[str, str]] | None = None,
) -> str:
    """把手动文本、文件文本、网页文本合并为 Agent 输入。"""
    sections = []

    manual_text = manual_text.strip()
    if manual_text:
        sections.append(
            f"""
# 用户手动输入

{manual_text}
""".strip()
        )

    if file_texts:
        for filename, text in file_texts:
            text = text.strip()
            if text:
                sections.append(
                    f"""
# 导入文件：{filename}

{text}
""".strip()
                )

    if webpage_texts:
        for url, text in webpage_texts:
            text = text.strip()
            if text:
                sections.append(
                    f"""
# 导入网页：{url}

{text}
""".strip()
                )

    combined = "\n\n---\n\n".join(sections).strip()

    if not combined:
        raise ValueError("输入内容为空，请至少提供文本、文件或网页 URL 中的一种。")

    return combined