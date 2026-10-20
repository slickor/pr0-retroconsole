"""pr0gramm REST API Client for pr0-retroconsole.

Handles fetching items, post details, comment trees, tags, voting,
and cookie authentication with automatic nonce extraction.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any
import requests

logger = logging.getLogger("pr0.api")

API_BASE = "https://pr0.app/api"
CDN_THUMB = "https://thumb.pr0.app"
CDN_IMG = "https://img.pr0.app"
CDN_VID = "https://vid.pr0.app"

try:
    from version import VERSION
except ImportError:
    from .version import VERSION

USER_AGENT = f"pr0-retroconsole/{VERSION} (+https://github.com/slickor/pr0-retroconsole)"

# Flag bitmasks
FLAG_SFW = 1
FLAG_NSFW = 2
FLAG_NSFL = 4
FLAG_NSFP = 8

FLAG_NAMES = {
    FLAG_SFW: "SFW",
    FLAG_NSFW: "NSFW",
    FLAG_NSFL: "NSFL",
    FLAG_NSFP: "NSFP",
}


def parse_me_cookie(me_cookie: str | None) -> tuple[str | None, str | None]:
    """Extract username and 16-character voting nonce from a pr0gramm 'me' cookie.

    The 'me' cookie is URL-encoded JSON, e.g.:
    {"n":"Username","id":"0123456789abcdef0123456789abcdef","a":1,...}
    The first 16 characters of the 'id' field form the nonce for POST requests.
    """
    if not me_cookie or not me_cookie.strip():
        return None, None

    cookie_val = me_cookie.strip()
    # Handle if user supplied full 'me=...' or just the value
    if cookie_val.startswith("me="):
        cookie_val = cookie_val[3:]

    # Decode URL encoding if present
    try:
        decoded = urllib.parse.unquote(cookie_val)
        data = json.loads(decoded)
        if isinstance(data, dict):
            user_id = str(data.get("id", ""))
            username = str(data.get("n", ""))
            nonce = user_id[:16] if len(user_id) >= 16 else None
            return username or None, nonce
    except Exception as e:
        logger.warning("Could not parse 'me' cookie: %s", e)

    return None, None


class Pr0API:
    """REST API Client for pr0gramm (pr0.app)."""

    def __init__(self, me_cookie: str | None = None, timeout: float = 10.0):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.me_cookie = me_cookie
        self.username, self.nonce = parse_me_cookie(me_cookie)

        if self.me_cookie:
            # Clean cookie value
            clean_cookie = self.me_cookie.strip()
            if clean_cookie.startswith("me="):
                clean_cookie = clean_cookie[3:]
            self.session.cookies.set("me", clean_cookie, domain="pr0.app")

    def update_cookie(self, me_cookie: str | None) -> None:
        """Update active me-cookie and credentials."""
        self.me_cookie = me_cookie
        self.username, self.nonce = parse_me_cookie(me_cookie)
        if self.me_cookie:
            clean_cookie = self.me_cookie.strip()
            if clean_cookie.startswith("me="):
                clean_cookie = clean_cookie[3:]
            self.session.cookies.set("me", clean_cookie, domain="pr0.app")
        else:
            self.session.cookies.clear()

    @property
    def is_authenticated(self) -> bool:
        """Returns True if a valid user session / nonce is configured."""
        return bool(self.nonce and self.username)

    def get_items(
        self,
        promoted: int = 1,
        flags: int = FLAG_SFW,
        older: int | None = None,
        tags: str | None = None,
    ) -> dict[str, Any]:
        """Fetch feed items from /api/items/get.

        :param promoted: 1 for 'Beliebt' (top), 0 for 'Neu' (newest)
        :param flags: Bitmask of flags (1=SFW, 2=NSFW, 4=NSFL, 8=NSFP)
        :param older: Item-ID for pagination (loads items older than this ID)
        :param tags: Optional search query / tags filter
        :return: Dict containing 'items' list and 'atEnd' boolean
        """
        params: dict[str, Any] = {
            "promoted": int(promoted),
            "flags": int(flags),
        }
        if older is not None:
            params["older"] = int(older)
        if tags:
            params["tags"] = str(tags)

        url = f"{API_BASE}/items/get"
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return {
                "items": data.get("items", []),
                "atEnd": bool(data.get("atEnd", False)),
                "error": None,
            }
        except Exception as e:
            logger.error("Error fetching items: %s", e)
            return {"items": [], "atEnd": False, "error": str(e)}

    def get_info(self, item_id: int) -> dict[str, Any]:
        """Fetch tags and comments for a post from /api/items/info.

        :param item_id: The ID of the post
        :return: Dict with 'tags' and 'comments' lists
        """
        url = f"{API_BASE}/items/info"
        params = {"itemId": int(item_id)}
        try:
            resp = self.session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return {
                "tags": data.get("tags", []),
                "comments": data.get("comments", []),
                "error": None,
            }
        except Exception as e:
            logger.error("Error fetching item info for %d: %s", item_id, e)
            return {"tags": [], "comments": [], "error": str(e)}

    def vote(self, item_id: int, vote_val: int) -> dict[str, Any]:
        """Vote on an item: 1 (Upvote / Blussi), -1 (Downvote), 0 (Neutralize).

        Requires authentication (nonce).
        """
        if not self.nonce:
            return {
                "success": False,
                "error": "Login erforderlich! 'me_cookie' in config.json fehlt.",
            }

        url = f"{API_BASE}/items/vote"
        data = {
            "id": int(item_id),
            "vote": int(vote_val),
            "_nonce": self.nonce,
        }
        try:
            resp = self.session.post(url, data=data, timeout=self.timeout)
            resp.raise_for_status()
            result = resp.json()
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            logger.error("Error voting on item %d: %s", item_id, e)
            return {"success": False, "error": str(e)}

    @staticmethod
    def is_video(item: dict[str, Any]) -> bool:
        """Check if an item is a video (.mp4 or .webm)."""
        image_path = str(item.get("image", "")).lower()
        return image_path.endswith((".mp4", ".webm"))

    @staticmethod
    def get_thumb_url(item: dict[str, Any]) -> str:
        """Get the full CDN URL for an item's thumbnail."""
        thumb = item.get("thumb", "")
        return f"{CDN_THUMB}/{thumb}" if thumb else ""

    @staticmethod
    def get_media_url(item: dict[str, Any]) -> str:
        """Get the full CDN URL for an item's full-size media (image or video)."""
        image_path = item.get("image", "")
        if not image_path:
            return ""
        if Pr0API.is_video(item):
            return f"{CDN_VID}/{image_path}"
        return f"{CDN_IMG}/{image_path}"

    @staticmethod
    def get_flag_string(flags: int) -> str:
        """Convert flag bitmask to human-readable string (e.g. SFW, NSFW)."""
        active = []
        for bit, label in FLAG_NAMES.items():
            if flags & bit:
                active.append(label)
        return "+".join(active) if active else "None"

    def fetch_captcha(self) -> dict[str, Any]:
        """Fetch a new captcha challenge from /api/user/captcha.

        Returns dict with:
        'token': str, 'captcha': str (data:image/png;base64,...), 'error': str | None
        """
        url = f"{API_BASE}/user/captcha"
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return {
                "token": str(data.get("token", "")),
                "captcha": str(data.get("captcha", "")),
                "error": None,
            }
        except Exception as e:
            logger.error("Failed to fetch captcha: %s", e)
            return {"token": "", "captcha": "", "error": str(e)}

    def login(
        self,
        username: str,
        password: str,
        token: str,
        captcha: str,
    ) -> dict[str, Any]:
        """Attempt user authentication via /api/user/login.

        Returns dict with:
        'success': bool, 'username': str | None, 'me_cookie': str | None, 'error': str | None
        """
        url = f"{API_BASE}/user/login"
        data = {
            "name": username.strip(),
            "password": password,
            "token": token.strip(),
            "captcha": captcha.strip(),
        }
        try:
            resp = self.session.post(url, data=data, timeout=self.timeout)
            resp_data = resp.json() if resp.text else {}

            if resp.status_code == 200 and resp_data.get("success"):
                # Extract 'me' cookie from session or response headers
                me_val = self.session.cookies.get("me")
                if not me_val:
                    me_val = resp.cookies.get("me")

                if me_val:
                    self.update_cookie(me_val)
                    return {
                        "success": True,
                        "username": self.username or username,
                        "me_cookie": me_val,
                        "error": None,
                    }
                else:
                    return {
                        "success": False,
                        "username": None,
                        "me_cookie": None,
                        "error": "Server meldete Erfolg, aber kein 'me'-Cookie erhalten.",
                    }
            else:
                err_code = resp_data.get("error", "unknown")
                err_msgs = {
                    "invalidCaptcha": "Falscher Captcha-Code. Bitte erneut versuchen.",
                    "invalidLogin": "Benutzername oder Passwort ist nicht korrekt.",
                    "emailNotConfirmed": "E-Mail-Adresse ist noch nicht bestätigt.",
                    "banned": "Dieser Account ist gesperrt.",
                    "badRequest": "Ungültige Anfrage.",
                }
                msg = err_msgs.get(err_code, f"Fehler bei Anmeldung: {err_code}")
                return {
                    "success": False,
                    "username": None,
                    "me_cookie": None,
                    "error": msg,
                }
        except Exception as e:
            logger.error("Login request failed: %s", e)
            return {
                "success": False,
                "username": None,
                "me_cookie": None,
                "error": f"Verbindungsfehler: {e}",
            }

    def logout(self) -> None:
        """Clear active user credentials and session cookies."""
        self.update_cookie(None)

