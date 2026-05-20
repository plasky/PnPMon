import json
import keyring
import requests
from typing import Optional

SERVICE_NAME = "PnPMonitor"
COOKIE_KEY = "ligo_pnp_cookies"
PNP_ROOT = "https://pnp.ligo.org"


class AuthManager:
    def save_cookies(self, cookies: list[dict]) -> None:
        keyring.set_password(SERVICE_NAME, COOKIE_KEY, json.dumps(cookies))

    def load_cookies(self) -> Optional[list[dict]]:
        raw = keyring.get_password(SERVICE_NAME, COOKIE_KEY)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def clear_cookies(self) -> None:
        try:
            keyring.delete_password(SERVICE_NAME, COOKIE_KEY)
        except keyring.errors.PasswordDeleteError:
            pass

    def has_cookies(self) -> bool:
        return self.load_cookies() is not None

    def build_session(self) -> Optional[requests.Session]:
        cookies = self.load_cookies()
        if not cookies:
            return None
        session = requests.Session()
        session.headers.update({"User-Agent": "PnPMonitor/1.0"})
        for c in cookies:
            session.cookies.set(
                c["name"],
                c["value"],
                domain=c.get("domain", ".pnp.ligo.org"),
                path=c.get("path", "/"),
            )
        return session

    def is_session_valid(self, session: requests.Session) -> bool:
        try:
            resp = session.get(PNP_ROOT, allow_redirects=True, timeout=15)
            # If redirected to an IdP, the session has expired
            return PNP_ROOT in resp.url and resp.status_code == 200
        except requests.RequestException:
            return False
