"""pr0gramm REST API Client for pr0-retroconsole.

Sprache: Deutsch (pr0-Amtssprache) • Architektur: 100% zertifizierter Vibecode.
Handles fetching items, post details, comment trees, tags, voting,
and cookie authentication with automatic nonce extraction.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
from typing import Any
import requests

logger = logging.getLogger("pr0.api")

API_HOSTS = [
    "https://pr0gramm.com/api",
    "https://pr0.app/api",
]
API_BASE = API_HOSTS[0]

CDN_THUMB = "https://thumb.pr0gramm.com"
CDN_IMG = "https://img.pr0gramm.com"
CDN_VID = "https://vid.pr0gramm.com"

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


def clean_cookie_val(val: str | None, prefix: str = "") -> str:
    """Strip whitespace and optional cookie key prefix (e.g. 'me=' or 'av=')."""
    if not val:
        return ""
    v = val.strip()
    if prefix and v.startswith(prefix):
        v = v[len(prefix):].strip()
    return v


class Pr0API:
    """REST API Client for pr0gramm (pr0gramm.com / pr0.app)."""

    def __init__(
        self,
        me_cookie: str | None = None,
        av_cookie: str | None = None,
        timeout: float = 10.0,
    ):
        self.timeout = timeout
        self.api_base = API_HOSTS[0]
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

        self.me_cookie = me_cookie
        self.av_cookie = av_cookie
        self.username, self.nonce = parse_me_cookie(me_cookie)

        if self.me_cookie:
            clean_me = clean_cookie_val(self.me_cookie, "me=")
            self.session.cookies.set("me", clean_me, domain="pr0.app")
            self.session.cookies.set("me", clean_me, domain="pr0gramm.com")
            if self.av_cookie:
                clean_av = clean_cookie_val(self.av_cookie, "av=")
                self.session.cookies.set("av", clean_av, domain="pr0.app")
                self.session.cookies.set("av", clean_av, domain="pr0gramm.com")
            # Automatically synchronize session to obtain latest av cookie
            self.sync_user_session()

    def _request_with_fallback(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> requests.Response:
        """Execute HTTP request with automatic domain fallback and retry on network/DNS errors."""
        last_exception: Exception | None = None
        hosts_to_try = [self.api_base] + [h for h in API_HOSTS if h != self.api_base]
        req_timeout = kwargs.pop("timeout", self.timeout)

        for host in hosts_to_try:
            url = f"{host}{path}"
            for attempt in range(max_retries):
                try:
                    resp = self.session.request(method, url, timeout=req_timeout, **kwargs)
                    resp.raise_for_status()
                    if host != self.api_base:
                        logger.info("Switched active API host to %s", host)
                        self.api_base = host
                    return resp
                except (requests.ConnectionError, requests.Timeout) as e:
                    last_exception = e
                    logger.warning("Connection/DNS error to %s (attempt %d/%d): %s", url, attempt + 1, max_retries, e)
                    if attempt < max_retries - 1:
                        time.sleep(1.0)
                except requests.HTTPError as e:
                    raise e

        if last_exception:
            raise last_exception
        raise RuntimeError(f"Request failed for {path} across all endpoints.")

    def sync_user_session(self) -> dict[str, Any]:
        """Synchronize user session with pr0gramm API.

        Fetches user info and extracts the essential 'av' (age-verification) cookie
        required by CDN servers for accessing NSFW and NSFL media (videos & images).
        """
        if not self.me_cookie:
            self.av_cookie = None
            return {}

        clean_me = clean_cookie_val(self.me_cookie, "me=")
        self.session.cookies.set("me", clean_me, domain="pr0.app")
        self.session.cookies.set("me", clean_me, domain="pr0gramm.com")

        try:
            resp = self._request_with_fallback("GET", "/user/me", timeout=min(5.0, self.timeout))
            if resp.status_code == 200:
                # Look for av cookie in response cookies
                av_found = resp.cookies.get("av") or self.session.cookies.get("av")
                if not av_found and "set-cookie" in resp.headers:
                    m = re.search(r'\bav=([^;,\s]+)', resp.headers["set-cookie"])
                    if m:
                        av_found = m.group(1)
                if av_found:
                    self.av_cookie = clean_cookie_val(av_found, "av=")
                    self.session.cookies.set("av", self.av_cookie, domain="pr0.app")
                    self.session.cookies.set("av", self.av_cookie, domain="pr0gramm.com")
                    logger.info("Retrieved age-verification (av) cookie for NSFW/NSFL media")

                # Check for updated me cookie from server
                me_new = resp.cookies.get("me")
                if me_new:
                    self.me_cookie = clean_cookie_val(me_new, "me=")
                    self.username, self.nonce = parse_me_cookie(self.me_cookie)

                return resp.json()
        except Exception as e:
            logger.debug("Failed session sync: %s", e)

        return {}

    def update_cookie(self, me_cookie: str | None, av_cookie: str | None = None) -> None:
        """Update active me-cookie and credentials."""
        self.me_cookie = me_cookie
        self.av_cookie = av_cookie
        self.username, self.nonce = parse_me_cookie(me_cookie)
        if self.me_cookie:
            clean_me = clean_cookie_val(self.me_cookie, "me=")
            self.session.cookies.set("me", clean_me, domain="pr0.app")
            self.session.cookies.set("me", clean_me, domain="pr0gramm.com")
            if self.av_cookie:
                clean_av = clean_cookie_val(self.av_cookie, "av=")
                self.session.cookies.set("av", clean_av, domain="pr0.app")
                self.session.cookies.set("av", clean_av, domain="pr0gramm.com")
            self.sync_user_session()
        else:
            self.session.cookies.clear()

    def get_cookie_header(self) -> str:
        """Build RFC 6265 Cookie header string containing me and av cookies."""
        parts = []
        if self.me_cookie:
            c = clean_cookie_val(self.me_cookie, "me=")
            if c:
                parts.append(f"me={c}")
        if self.av_cookie:
            a = clean_cookie_val(self.av_cookie, "av=")
            if a:
                parts.append(f"av={a}")
        return "; ".join(parts)

    @property
    def is_authenticated(self) -> bool:
        """Returns True if a valid user session / nonce is configured."""
        return bool(self.nonce and self.username)

    @property
    def is_age_verified(self) -> bool:
        """Returns True if age-verification cookie is available for NSFW/NSFL media."""
        return bool(self.av_cookie)

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

        try:
            resp = self._request_with_fallback("GET", "/items/get", params=params)
            data = resp.json()
            api_err = data.get("error")
            if api_err in ("forbidden", "nsfwRequiresLogin"):
                logger.info("Feed access restricted: %s (%s)", api_err, data.get("msg", "Nicht eingeloggt"))
                return {
                    "items": [],
                    "atEnd": False,
                    "error": "auth_required",
                    "msg": data.get("msg", "Nicht eingeloggt"),
                }
            return {
                "items": data.get("items", []),
                "atEnd": bool(data.get("atEnd", False)),
                "error": api_err,
            }
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 403:
                logger.info("Feed access forbidden (403): User not logged in for requested flags=%d", flags)
                return {
                    "items": [],
                    "atEnd": False,
                    "error": "auth_required",
                    "msg": "Nicht eingeloggt",
                }
            logger.error("HTTP error fetching items: %s", e)
            return {"items": [], "atEnd": False, "error": str(e)}
        except Exception as e:
            logger.error("Error fetching items: %s", e)
            return {"items": [], "atEnd": False, "error": str(e)}

    def get_info(self, item_id: int) -> dict[str, Any]:
        """Fetch tags and comments for a post from /api/items/info.

        :param item_id: The ID of the post
        :return: Dict with 'tags' and 'comments' lists
        """
        params = {"itemId": int(item_id)}
        try:
            resp = self._request_with_fallback("GET", "/items/info", params=params)
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

        data = {
            "id": int(item_id),
            "vote": int(vote_val),
            "_nonce": self.nonce,
        }
        try:
            resp = self._request_with_fallback("POST", "/items/vote", data=data)
            result = resp.json()
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            logger.error("Error voting on item %d: %s", item_id, e)
            return {"success": False, "error": str(e)}

    def vote_comment(self, comment_id: int, vote_val: int) -> dict[str, Any]:
        """Vote on a comment: 1 (Upvote / Blussi), -1 (Downvote), 0 (Neutralize).

        Requires authentication (nonce).
        """
        if not self.nonce:
            return {
                "success": False,
                "error": "Login erforderlich! 'me_cookie' in config.json fehlt.",
            }

        data = {
            "id": int(comment_id),
            "vote": int(vote_val),
            "_nonce": self.nonce,
        }
        try:
            resp = self._request_with_fallback("POST", "/comments/vote", data=data)
            result = resp.json()
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            logger.error("Error voting on comment %d: %s", comment_id, e)
            return {"success": False, "error": str(e)}

    def post_comment(self, item_id: int, parent_id: int, text: str) -> dict[str, Any]:
        """Post a comment or reply to an existing comment.

        :param item_id: ID of the post
        :param parent_id: ID of parent comment (0 for top-level comment)
        :param text: Text content of the comment
        """
        if not self.nonce:
            return {
                "success": False,
                "error": "Login erforderlich! 'me_cookie' in config.json fehlt.",
            }

        text = text.strip()
        if not text:
            return {"success": False, "error": "Kommentar darf nicht leer sein."}

        data = {
            "itemId": int(item_id),
            "parentId": int(parent_id),
            "comment": text,
            "_nonce": self.nonce,
        }
        try:
            resp = self._request_with_fallback("POST", "/comments/post", data=data)
            result = resp.json()
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            logger.error("Error posting comment on item %d: %s", item_id, e)
            return {"success": False, "error": str(e)}
            resp.raise_for_status()
            result = resp.json()
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            logger.error("Error posting comment on item %d: %s", item_id, e)
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
        try:
            resp = self._request_with_fallback("GET", "/user/captcha")
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
        data = {
            "name": username.strip(),
            "password": password,
            "token": token.strip(),
            "captcha": captcha.strip(),
        }
        try:
            resp = self._request_with_fallback("POST", "/user/login", data=data)
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

