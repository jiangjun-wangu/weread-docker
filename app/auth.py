"""扫码登录：getLoginUid → 二维码 → pollLogin → 存 session"""
import base64
import io
import time

import httpx
import qrcode

from app import logger as log
from app import store


HOST = "https://weread.qq.com"
REFERER = "https://weread.qq.com/"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 "
    "Safari/537.36 Edg/135.0.0.0"
)


class WeReadAuth:
    def __init__(self):
        self.client = httpx.Client(
            base_url=HOST,
            headers={"User-Agent": USER_AGENT, "Referer": REFERER},
            timeout=30,
            follow_redirects=True,
        )
        self.uid = ""

    def fetch_uid(self) -> str:
        r = self.client.get("/api/auth/getLoginUid")
        r.raise_for_status()
        data = r.json()
        self.uid = str(data.get("uid", ""))
        return self.uid

    def qr_url(self) -> str:
        return HOST + "/web/confirm?uid=" + self.uid

    def qr_png_bytes(self) -> bytes:
        img = qrcode.make(self.qr_url())
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def qr_png_base64(self) -> str:
        return base64.b64encode(self.qr_png_bytes()).decode()

    def poll_once(self) -> dict:
        r = self.client.get(
            "/api/auth/getLoginInfo",
            params={"uid": self.uid, "otp": ""},
        )
        r.raise_for_status()
        return r.json()

    def wait_for_login(self, timeout: int = 180, interval: float = 2.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data = self.poll_once()
            except Exception:
                time.sleep(interval)
                continue
            if data.get("succeed"):
                return True
            code = data.get("logicCode", "") or ""
            if code and code != "LOGIN_TIMEOUT":
                return False
            time.sleep(interval)
        return False

    def save(self) -> None:
        """持久化会话 cookie。

        注意：不能只保留 wr_ 前缀的 cookie。微信读书登录后返回的 cookie 中，
        会话有效性还依赖 wr_skey / wr_vid 之外的其它凭据项；过滤掉会导致
        重新加载后的会话不完整，请求时被判 401，从而反复要求重新扫码。
        """
        cookies = {}
        for c in self.client.cookies.jar:
            if c.name and c.value:
                cookies[c.name] = c.value
        if not cookies:
            log.warning("保存会话时未捕获到任何 cookie")
            return
        store.save_session(cookies, self.uid)

    def load(self) -> bool:
        """从持久化存储恢复会话。恢复出的 cookie 会自动补全 domain/path。"""
        sess = store.load_session()
        cookies = sess.get("cookies", {}) or {}
        if not cookies:
            return False
        for k, v in cookies.items():
            self.client.cookies.set(k, v, domain=".weread.qq.com", path="/")
        self.uid = sess.get("uid", "") or ""
        return True

    def renew(self) -> bool:
        try:
            r = self.client.post(
                "/web/login/renewal",
                content='{"rq":"%2Fweb%2Fbook%2Fread","ql":false}',
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            return False
        if r.status_code != 200:
            return False
        try:
            data = r.json()
        except Exception:
            return False
        if not data.get("succeed"):
            return False
        self.save()
        try:
            store.mark_renewed()
        except Exception:
            pass
        return True

    def close(self) -> None:
        self.client.close()
