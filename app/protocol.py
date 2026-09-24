"""微信读书协议核心算法 - 从 WeReadProtocol.cpp / WeReadClient.cpp 移植"""
import hashlib


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def encode_id(value: str) -> str:
    """对应 C++ encodeId(const char*, Md5Function, char*, size_t)"""
    raw = value.encode("utf-8")
    first_hash = md5_hex(raw)
    numeric = len(value) > 0 and value.isdigit()

    out = first_hash[0:3]
    out += "3" if numeric else "4"
    out += "2"
    out += first_hash[30:32]

    if numeric:
        for offset in range(0, len(value), 9):
            if offset != 0:
                out += "g"
            chunk = value[offset:offset + 9]
            number = int(chunk)
            chunk_hex = format(number, "x")
            out += format(len(chunk_hex), "02x")
            out += chunk_hex
    else:
        encoded = "".join(format(b, "x") for b in raw)
        out += format(len(encoded), "02x")
        out += encoded

    while len(out) < 20:
        need = 20 - len(out)
        out += first_hash[:need]

    final_hash = md5_hex(out.encode("utf-8"))
    out += final_hash[0:3]
    return out


def sign_query(query: str) -> str:
    """对应 C++ signQuery()，输出小写十六进制"""
    raw = query.encode("utf-8")
    length = len(raw)
    a = 0x15051505
    b = a
    i = length
    while i > 1:
        current = raw[i - 1]
        previous = raw[i - 2]
        a = (a ^ (current << ((length - i + 1) % 30))) & 0x7fffffff
        b = (b ^ (previous << ((i - 1) % 30))) & 0x7fffffff
        i -= 2
    return format(a + b, "x")


def url_encode(value: str) -> str:
    """对应 C++ urlEncode()，RFC 3986 unreserved 字符不编码"""
    safe = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")
    out = []
    for b in value.encode("utf-8"):
        c = chr(b)
        if c in safe:
            out.append(c)
        else:
            out.append("%%%02X" % b)
    return "".join(out)


def make_content_body(book_id: str, chapter_uid: str, psvts: str, timestamp: int, random_value: int) -> dict:
    """对应 C++ makeContentBody()，返回 JSON 请求体字典"""
    encoded_book = encode_id(book_id)
    encoded_chapter = encode_id(chapter_uid)
    encoded_ts = encode_id(str(timestamp))

    while encoded_ts == psvts:
        timestamp += 1
        encoded_ts = encode_id(str(timestamp))

    request_random = (random_value * random_value) & 0xFFFFFFFF
    encoded_ps = url_encode(psvts)

    query = (
        "b=" + encoded_book +
        "&c=" + encoded_chapter +
        "&ct=" + str(timestamp) +
        "&pc=" + encoded_ts +
        "&prevChapter=false" +
        "&ps=" + encoded_ps +
        "&r=" + str(request_random) +
        "&sc=1" +
        "&st=0"
    )
    signature = sign_query(query)

    return {
        "b": encoded_book,
        "c": encoded_chapter,
        "r": request_random,
        "ct": timestamp,
        "ps": psvts,
        "pc": encoded_ts,
        "sc": 1,
        "prevChapter": "false",
        "st": 0,
        "s": signature,
    }


def decimal_digits(value: int) -> int:
    return len(str(value))


def parse_decimal(s: str) -> int:
    result = 0
    for c in s:
        if c < "0" or c > "9":
            return 0
        result = result * 10 + (ord(c) - ord("0"))
    return result


def swap_positions(encoded_length: int, tail: bytes) -> list:
    if encoded_length < 4:
        return []
    if encoded_length < 11:
        return [0, 2]
    expected_tail = min(4, (encoded_length + 9) // 10)
    if len(tail) != expected_tail:
        return []
    decimal = ""
    for idx in range(len(tail), 0, -1):
        value = tail[idx - 1]
        transformed = 0
        for bit in range(8):
            if (value >> bit) & 1:
                transformed += 1 << (2 * bit)
        decimal += str(transformed)
    modulus = encoded_length - expected_tail - 2
    if modulus == 0:
        return []
    step = decimal_digits(modulus)
    out = []
    i = 0
    while len(out) < 10 and i + step < len(decimal):
        out.append(parse_decimal(decimal[i:i + step]) % modulus)
        out.append(parse_decimal(decimal[i + 1:i + 1 + step]) % modulus)
        i += step
    return out


def base64_value(c: int) -> int:
    if 65 <= c <= 90:
        return c - 65
    if 97 <= c <= 122:
        return c - 97 + 26
    if 48 <= c <= 57:
        return c - 48 + 52
    if c == 45 or c == 43:
        return 62
    if c == 95 or c == 47:
        return 63
    return 0xFF


def base64url_decode(data: bytes) -> bytes:
    out = bytearray()
    quartet = [0, 0, 0, 0]
    quartet_len = 0
    for b in data:
        value = base64_value(b)
        if value == 0xFF:
            continue
        quartet[quartet_len] = value
        quartet_len += 1
        if quartet_len == 4:
            out.append(((quartet[0] << 2) | (quartet[1] >> 4)) & 0xFF)
            out.append(((quartet[1] << 4) | (quartet[2] >> 2)) & 0xFF)
            out.append(((quartet[2] << 6) | quartet[3]) & 0xFF)
            quartet_len = 0
    if quartet_len == 1:
        raise ValueError("invalid base64: leftover 1 char")
    if quartet_len == 0:
        return bytes(out)
    count = quartet_len - 1
    decoded = [
        ((quartet[0] << 2) | (quartet[1] >> 4)) & 0xFF,
        ((quartet[1] << 4) | (quartet[2] >> 2)) & 0xFF,
        ((quartet[2] << 6) | quartet[3]) & 0xFF,
    ]
    out.extend(decoded[:count])
    return bytes(out)


def copy_shard_body(shards: list) -> bytes:
    out = bytearray()
    for i, shard in enumerate(shards):
        if len(shard) < 32:
            raise ValueError("shard too short")
        data = shard[32:]
        if i == 0:
            if len(data) < 1:
                raise ValueError("first shard too short")
            data = data[1:]
        out += data
    return bytes(out)


def reverse_swaps_inplace(data: bytearray) -> None:
    length = len(data)
    if length < 4:
        raise ValueError("data too short")
    tail_len = min(4, (length + 9) // 10)
    tail = bytes(data[length - tail_len:])
    positions = swap_positions(length, tail)
    count = len(positions)
    if count == 0 or count % 2 != 0:
        raise ValueError("invalid swap positions")
    pair = count
    while pair >= 2:
        for delta in (1, 0):
            left = positions[pair - 1] + delta
            right = positions[pair - 2] + delta
            if left >= length or right >= length:
                continue
            data[left], data[right] = data[right], data[left]
        if pair == 2:
            break
        pair -= 2


def combine_and_decode(shards: list) -> bytes:
    combined = bytearray(copy_shard_body(shards))
    reverse_swaps_inplace(combined)
    return base64url_decode(bytes(combined))
