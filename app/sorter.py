"""书架排序与筛选"""


def first_letter(text):
    """中文取拼音首字母（GB2312），英文取大写首字母，其它返回 #"""
    if not text:
        return "#"
    c = text[0]
    if c.isascii() and c.isalpha():
        return c.upper()
    try:
        enc = c.encode("gb2312")
    except Exception:
        return "#"
    if len(enc) < 2:
        return "#"
    code = (enc[0] << 8) | enc[1]
    ranges = [
        (0xB0A1, 0xB0C4, "A"), (0xB0C5, 0xB2C0, "B"), (0xB2C1, 0xB4ED, "C"),
        (0xB4EE, 0xB6E9, "D"), (0xB6EA, 0xB7A1, "E"), (0xB7A2, 0xB8C0, "F"),
        (0xB8C1, 0xB9FD, "G"), (0xB9FE, 0xBBF6, "H"), (0xBBF7, 0xBFA5, "J"),
        (0xBFA6, 0xC0AB, "K"), (0xC0AC, 0xC2E7, "L"), (0xC2E8, 0xC4C2, "M"),
        (0xC4C3, 0xC5B5, "N"), (0xC5B6, 0xC5BD, "O"), (0xC5BE, 0xC6D9, "P"),
        (0xC6DA, 0xC8BA, "Q"), (0xC8BB, 0xC8F5, "R"), (0xC8F6, 0xCBF9, "S"),
        (0xCBFA, 0xCDD9, "T"), (0xCDDA, 0xCEF3, "W"), (0xCEF4, 0xD188, "X"),
        (0xD1B9, 0xD4D0, "Y"), (0xD4D1, 0xD7F9, "Z"),
    ]
    for lo, hi, letter in ranges:
        if lo <= code <= hi:
            return letter
    return "#"


SORT_KEYS = {
    "recent": lambda b: b.get("readUpdateTime", 0),
    "update": lambda b: b.get("updateTime", 0),
    "publish": lambda b: b.get("publishTime", ""),
    "title": lambda b: (first_letter(b.get("title", "")).replace("#", "ZZZ"), b.get("title", "")),
    "author": lambda b: (first_letter(b.get("author", "")).replace("#", "ZZZ"), b.get("author", "")),
    "category": lambda b: b.get("category", ""),
    "price": lambda b: b.get("centPrice", 0),
    "chapters": lambda b: b.get("lastChapterIdx", 0),
    "finished": lambda b: b.get("finished", 0),
    "reading": lambda b: b.get("readingTime", 0),
    "progress": lambda b: b.get("progress", 0),
}


def sort_books(books, sort="recent", order="desc"):
    key = SORT_KEYS.get(sort)
    if not key:
        return books
    reverse = order == "desc"
    return sorted(books, key=key, reverse=reverse)


def filter_books(books, mode="all"):
    if mode == "all":
        return books
    if mode == "reading":
        return [b for b in books if b.get("hasProgress") and not b.get("finishReading")]
    if mode == "finished":
        return [b for b in books if b.get("finishReading")]
    if mode == "unread":
        return [b for b in books if not b.get("hasProgress")]
    return books


def search_books(books, q=""):
    if not q or not q.strip():
        return books
    kw = q.strip().lower()
    return [
        b for b in books
        if kw in (b.get("title") or "").lower()
        or kw in (b.get("author") or "").lower()
    ]
