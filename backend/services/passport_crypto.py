"""超星 Passport 加解密与签名纯算法层。

严格对齐 Java 参考实现（`passport-cookie-login`）与官方《passport2 v2 API 文档》：

- ``gen_signature``：参数名按 ASCII 升序 → 逐个拼 ``key + value``（None 视为 ""）
  → 末尾追加 secretKey → 取 MD5 十六进制小写（32 位）
- ``package_param``：每项拼成 ``"[" + "-" + "#%'3A" + 值 + "-" + "#%'3A" + "]"`` 后顺序拼接
- AES：``AES/CBC/PKCS5Padding``，key = IV = 16 字节密钥；密文先 URL 解码再 Base64 解码
- RSA：公钥为 Base64 编码的 X.509 SubjectPublicKeyInfo，算法 ``SHA256withRSA``

本模块只做纯计算，不发网络请求、不读配置。
"""

import base64
import hashlib
import re
from typing import Any, Iterable, Mapping
from urllib.parse import unquote, unquote_plus

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.serialization import load_der_public_key

# 官方文档给出的 enc 握手串拼接符
PACKAGE_KEY = "-#%'3A"

# VC3 中 MD5 校验尾长度
ENC_LEN = 32

_NON_B64 = re.compile(r"[^A-Za-z0-9+/]")


def md5_hex(text: str) -> str:
    """MD5 十六进制小写（32 位）。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def gen_signature(secret_key: str, params: Mapping[str, Any]) -> str:
    """生成接口 signature。

    :param secret_key: 产品私钥（AppKey / debugKey）
    :param params: 请求参数名 → 参数值（不含 signature）
    """
    buffer: list[str] = []
    for key in sorted(params.keys()):
        value = params.get(key)
        buffer.append(key)
        buffer.append("" if value is None else str(value))
    buffer.append(secret_key)
    return md5_hex("".join(buffer))


def package_param(values: Iterable[Any]) -> str:
    """构造 enc 握手串的明文，顺序与传入一致，空值项跳过。"""
    parts: list[str] = []
    for value in values:
        text = "" if value is None else str(value)
        if not text:
            continue
        parts.append(f"[{PACKAGE_KEY}{text}{PACKAGE_KEY}]")
    return "".join(parts)


def b64_decode(text: str) -> bytes:
    """宽容的 Base64 解码。

    Java 侧使用 commons-codec 的 ``Base64.decodeBase64``，会自动忽略非法字符并容错补齐
    padding；Python 的 ``base64.b64decode`` 默认严格，这里做等价处理。
    """
    cleaned = _NON_B64.sub("", text or "")
    if not cleaned:
        return b""
    return base64.b64decode(cleaned + "=" * ((-len(cleaned)) % 4))


def decode_url(text: str, plus_as_space: bool = False) -> str:
    """URL 解码。

    Java 的 ``URLDecoder.decode`` 会把 ``+`` 解码成空格，等价于 :func:`unquote_plus`；
    Python 的 :func:`unquote` 不会。默认使用 Java 语义，必要时可切换。
    """
    if not text:
        return ""
    return unquote_plus(text) if plus_as_space else unquote(text)


def aes_decode(cipher_text: str, aes_key: str) -> str:
    """AES/CBC/PKCS5Padding 解密，返回 UTF-8 明文。

    与 Java 参考实现一致：key 为 16 字节密钥，**IV = key 的前 16 字节**；
    入参是 Base64 编码（并可能做过 URL 编码）的密文。
    """
    key = (aes_key or "").encode("utf-8")
    if len(key) < 16:
        raise ValueError("AES key 长度不足 16 字节")

    data = b64_decode(unquote(cipher_text or ""))
    if not data:
        return ""

    decryptor = Cipher(algorithms.AES(key), modes.CBC(key[:16])).decryptor()
    padded = decryptor.update(data) + decryptor.finalize()

    pad_len = padded[-1] if padded else 0
    if 1 <= pad_len <= 16:
        padded = padded[:-pad_len]
    return padded.decode("utf-8")


def rsa_check(content: str, sign_base64: str, public_key_base64: str) -> bool:
    """SHA256withRSA 验签。

    :param content: 待验签内容（会按 UTF-8 编码）
    :param sign_base64: 签名串（Base64）
    :param public_key_base64: 公钥（Base64 编码的 X.509 SubjectPublicKeyInfo）
    :return: 验签通过返回 True，任何异常一律返回 False
    """
    try:
        public_key = load_der_public_key(b64_decode(public_key_base64))
        public_key.verify(
            b64_decode(sign_base64),
            content.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False
