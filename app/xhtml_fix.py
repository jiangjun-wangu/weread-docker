"""XHTML 规范化：修复微信读书长章节多文档拼接导致的 XML 结构损坏。

问题现象
--------
部分章节（19/38 本书、124 个章节文件）在 EPUB 中打开报：
    error on line 19 at column 6: Invalid processing instruction: <?xml

根因
----
微信读书对长章节会返回多段内容，每段都是**一份完整的 XHTML 文档**
（各自带 <?xml?>、<!DOCTYPE html>、<html>、<head>、<body>、</html>）。
`protocol.combine_and_decode` 把这些分片解码后直接拼接，于是产出：

    <?xml ...?>...<body>内容A</body></html>
    <?xml ...?>...<body>内容B</body></html>

第二段起的 XML 处理指令出现在文档中部，违反 XML 规范
（"<?xml" 只允许出现在文件最开头），阅读器解析即报错。

修复策略
--------
1. 按 <?xml 声明把内容切成若干段；
2. 每段提取 <body> 内的内容（若无 body 则整段保留）；
3. 用第一段的文档头（声明 + doctype + <html> 开头标签 + <head>）作为骨架；
4. 把各段 body 内容合并进同一个 <body>，输出单一合法 XHTML 文档。
"""
import re

_XML_DECL_RE = re.compile(r"<\?xml[^>]*\?>", re.I)
_DOCTYPE_RE = re.compile(r"<!DOCTYPE[^>]*>", re.I)
_BODY_RE = re.compile(r"<body[^>]*>(.*?)</body\s*>", re.I | re.S)
_BODY_OPEN_RE = re.compile(r"<body[^>]*>", re.I)
_HEAD_RE = re.compile(r"<head[^>]*>.*?</head\s*>", re.I | re.S)
_HTML_OPEN_RE = re.compile(r"<html[^>]*>", re.I)

# 微信读书的原文存在两种 XML 声明写法：
#   1) 标准：<?xml version="1.0" encoding="utf-8"?>
#   2) 被转义成注释：<!--?xml version="1.0" encoding="utf-8"?-->
# 二者都标记着一份新 XHTML 文档的开始，切分时需一并识别。
_DOC_START_RE = re.compile(
    r"(?:<\?xml[^>]*\?>|<!--\s*\?xml[^>]*\?-->)",
    re.I,
)


def _split_segments(text: str) -> list:
    """按文档起始标记切分，返回各段（不含标记本身）。"""
    marks = [m.start() for m in _DOC_START_RE.finditer(text)]
    if len(marks) <= 1:
        return [text]
    segments = []
    for i, start in enumerate(marks):
        m = _DOC_START_RE.match(text, start)
        body_start = m.end() if m else start
        body_end = marks[i + 1] if i + 1 < len(marks) else len(text)
        segments.append(text[body_start:body_end])
    return segments


def _extract_body(segment: str) -> str:
    """取出 <body> 内内容；无 body 标签时整段返回。"""
    m = _BODY_RE.search(segment)
    if m:
        return m.group(1)
    # 没有闭合 body：截取到 body 开标签之后
    m2 = _BODY_OPEN_RE.search(segment)
    if m2:
        tail = segment[m2.end():]
        end = tail.lower().rfind("</html>")
        return tail[:end] if end >= 0 else tail
    return segment


def _document_head(text: str) -> str:
    """提取首段的文档骨架：声明 + doctype + <html> + <head>。"""
    # 统一输出标准 XML 声明（原文可能是注释形态）
    decl = '<?xml version="1.0" encoding="UTF-8"?>'

    doctype = ""
    m = _DOCTYPE_RE.search(text)
    if m:
        doctype = m.group(0) + "\n"

    html_open = ""
    m = _HTML_OPEN_RE.search(text)
    if m:
        html_open = m.group(0) + "\n"

    head = ""
    m = _HEAD_RE.search(text)
    if m:
        head = m.group(0) + "\n"

    return decl + "\n" + doctype + html_open + head


def normalize_xhtml(data) -> bytes:
    """把可能由多份 XHTML 拼接而成的章节内容规范化为单一合法文档。

    输入 bytes 或 str；输出 bytes。
    若内容本就合法（只有一个 XML 声明），原样返回。
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return data
    else:
        text = data

    # 判定文档类型，避免误伤非 XHTML 内容：
    #  - 含 <html 或文档起始标记：完整 XHTML 文档，走归一流程
    #  - 否则可能是纯文本片段或 HTML 片段（整本 EPUB 的章节文件即如此），
    #    这类内容本来就不是合法 XML 文档，不应强行包装，也不应改写标签。
    has_doc_start = bool(_DOC_START_RE.search(text))
    looks_like_html = bool(re.search(r"<html\b|<body\b", text, re.I))
    if not has_doc_start and not looks_like_html:
        # 纯文本/片段：原样透传
        return text.encode("utf-8")

    # 1) 多文档拼接归一（微信读书长章节由多份完整 XHTML 拼接而成）
    if len(_DOC_START_RE.findall(text)) > 1:
        segments = _split_segments(text)
        bodies = [_extract_body(s) for s in segments]
        head = _document_head(text)
        text = (head + "<body>\n" + "\n".join(b.strip() for b in bodies)
                + "\n</body>\n</html>\n")
    elif has_doc_start:
        # 单文档但声明被写成注释形态（<!--?xml ...?>）：还原为标准声明，
        # 否则 XML 解析器会把它当注释，导致后续内容位置异常。
        m = _DOC_START_RE.search(text)
        if m and m.group(0).lower().startswith("<!--"):
            text = decl_standard() + text[m.end():]

    # 2) 去重重复属性（分片拼接会让 img 标签出现重复的 data-w 等属性）
    text = dedupe_attributes(text)
    return text.encode("utf-8")


def decl_standard() -> str:
    """标准 XML 声明。"""
    return '<?xml version="1.0" encoding="UTF-8"?>'


_TAG_RE = re.compile(r"<([a-zA-Z][-a-zA-Z0-9:]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
_ATTR_RE = re.compile(r"""([-a-zA-Z0-9_:.]+)\s*=\s*("([^"]*)"|'([^']*)')""")


def _dedupe_tag_attrs(attr_text: str) -> str:
    """去掉同一标签内重复出现的属性（保留首次出现的值）。"""
    seen = set()
    out = []
    pos = 0
    for m in _ATTR_RE.finditer(attr_text):
        name = m.group(1)
        if name in seen:
            # 重复属性：跳过原文（含前导空白）
            out.append((m.start(), m.end()))
        else:
            seen.add(name)
    if not out:
        return attr_text
    # 从后往前删除，避免影响偏移
    for start, end in reversed(out):
        attr_text = attr_text[:start] + attr_text[end:]
    # 清理可能残留的多余空白
    attr_text = re.sub(r"\s{2,}", " ", attr_text)
    return attr_text


def dedupe_attributes(text: str) -> str:
    """遍历所有标签，去除重复属性。"""
    if not text or "<" not in text:
        return text

    def repl(m):
        tag = m.group(1)
        attrs = m.group(2)
        if "=" not in attrs:
            return m.group(0)
        fixed = _dedupe_tag_attrs(attrs)
        if fixed == attrs:
            return m.group(0)
        return "<" + tag + fixed + ">"

    return _TAG_RE.sub(repl, text)


def count_xml_declarations(data) -> int:
    """统计文档起始标记数量（标准声明 + 注释形态声明），用于自检与测试。"""
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return 0
    else:
        text = data
    return len(_DOC_START_RE.findall(text))
