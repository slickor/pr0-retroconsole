"""Entry Point and Main Loop for pr0-retroconsole.

Implements the application state-machine between Grid-View, Single-Post-View,
and Comment-Tree Overlay with asynchronous API calls, caching, and SDL2 gamepad controls.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import queue
import sys
import threading
import time
from pathlib import Path
from typing import Any

# Ensure root, src/ and libs/ are on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ROOT_DIR / "src") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "src"))
if str(ROOT_DIR / "libs") not in sys.path:
    sys.path.insert(0, str(ROOT_DIR / "libs"))

# On Linux handhelds (muOS, TrimUI, Knulli, ArkOS), preload native system libSDL2
# before pygame loads so hardware Mali/KMSDRM drivers are used instead of offscreen
try:
    from tools.patch_sdl2 import preload_system_sdl2
    preload_system_sdl2()
except Exception:
    pass

import pygame

from api import Pr0API, FLAG_SFW, FLAG_NSFW, FLAG_NSFL, FLAG_NSFP
from cache import MediaCache
from input import (
    InputManager,
    ACTION_QUIT,
    ACTION_UP,
    ACTION_DOWN,
    ACTION_LEFT,
    ACTION_RIGHT,
    ACTION_SCROLL_UP,
    ACTION_SCROLL_DOWN,
    ACTION_SELECT,
    ACTION_BACK,
    ACTION_INFO,
    ACTION_SETTINGS,
    ACTION_TOGGLE_MODE,
    ACTION_SOLO_FLAG,
    ACTION_UPVOTE,
    ACTION_DOWNVOTE,
)
import base64
import io

from ui import UIRenderer, COLOR_GREEN, COLOR_RED, COLOR_ORANGE, THEMES, ACCENTS
from video import VideoPlayer, InlineVideoPlayer
from version import VERSION
from auth_server import AuthCompanionServer
from keyboard import VirtualKeyboard
from qr_helper import generate_qr_surface

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pr0.main")

# State constants
STATE_GRID = "grid"
STATE_POST = "post"
STATE_SETTINGS = "settings"
STATE_BUTTON_TEST = "button_test"
STATE_LOGIN = "login"


DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "pr0_dark",
    "accent": "orange",
    "autoplay_video": True,
    "autoplay_audio": True,
    "scroll_speed": "normal",
    "resolution": "auto",
    "width": 640,
    "height": 480,
    "fullscreen": True if platform.system() == "Linux" else False,
    "promoted": 1,
    "flags": 1,
    "me_cookie": "",
    "av_cookie": "",
    "cache_dir": "/tmp/pr0cache",
    "max_cache_files": 100,
    "button_layout": "auto",
    "fps": 30,
}


def load_config(config_path: Path) -> dict[str, Any]:
    """Load configuration JSON with graceful fallback and automatic initial creation.

    - If config.json exists: load it and fill in any newly added default keys.
    - If config.json does NOT exist: create it automatically from config.example.json
      (or DEFAULT_CONFIG) and save it to disk, so user settings (and login tokens)
      are preserved across updates.
    """
    config: dict[str, Any] = {}
    is_new = False

    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            logger.info("Loaded existing configuration from %s", config_path)
        except Exception as e:
            logger.error("Failed to parse config %s: %s", config_path, e)
            config = {}

    if not config:
        # config.json does not exist or was corrupted -> initialize new config.json
        is_new = True
        example = config_path.parent / "config.example.json"
        if example.is_file():
            try:
                config = json.loads(example.read_text(encoding="utf-8"))
                logger.info("Initializing new config.json from config.example.json template")
            except Exception as e:
                logger.error("Failed to load example config %s: %s", example, e)
                config = {}

        if not config:
            config = dict(DEFAULT_CONFIG)
            logger.info("Initializing new config.json from built-in defaults")

    # Ensure all required default keys are present (for backwards compatibility)
    updated = False
    for k, v in DEFAULT_CONFIG.items():
        if k not in config:
            config[k] = v
            updated = True

    # If this is a newly created config or new default keys were added, save to disk
    if is_new or updated:
        try:
            save_config(config, config_path)
            if is_new:
                logger.info("Created initial configuration at %s", config_path)
        except Exception as e:
            logger.warning("Could not write initial config to %s: %s", config_path, e)

    return config


def save_config(config_data: dict[str, Any], config_path: Path) -> bool:
    """Save configuration JSON to disk."""
    try:
        config_path.write_text(json.dumps(config_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved configuration to %s", config_path)
        return True
    except Exception as e:
        logger.error("Failed to save config %s: %s", config_path, e)
        return False


class Pr0App:
    """Main application orchestrator."""

    def __init__(self, config: dict[str, Any], config_path: Path):
        self.config = config
        self.config_path = config_path

        # Core subsystems
        self.me_cookie = str(self.config.get("me_cookie", ""))
        self.av_cookie = str(self.config.get("av_cookie", ""))
        self.api = Pr0API(me_cookie=self.me_cookie, av_cookie=self.av_cookie)
        if self.api.av_cookie:
            self.av_cookie = self.api.av_cookie
            if self.config.get("av_cookie") != self.av_cookie:
                self.config["av_cookie"] = self.av_cookie
                save_config(self.config, self.config_path)

        self.cache = MediaCache(
            cache_dir=self.config.get("cache_dir", "/tmp/pr0cache"),
            max_files=self.config.get("max_cache_files", 100),
            me_cookie=self.me_cookie,
            av_cookie=self.av_cookie,
        )
        preferred_player = self.config.get("video_player") or self.config.get("video_player_path")
        self.button_layout = str(self.config.get("button_layout", "auto"))
        self.video = VideoPlayer(
            preferred_player=preferred_player,
            button_layout=self.button_layout,
            me_cookie=self.me_cookie,
            av_cookie=self.av_cookie,
        )
        self.autoplay_audio = bool(self.config.get("autoplay_audio", True))
        self.inline_player = InlineVideoPlayer(
            video_player=self.video,
            enable_audio=self.autoplay_audio,
            me_cookie=self.me_cookie,
            av_cookie=self.av_cookie,
        )
        self.input_mgr = InputManager(axis_threshold=0.45, layout=self.button_layout)

        # Feed & Content State
        self.promoted: int = int(self.config.get("promoted", 1))  # 1 = Beliebt, 0 = Neu
        self.flags: int = int(self.config.get("flags", FLAG_SFW))
        self.items: list[dict[str, Any]] = []
        self.selected_idx: int = 0
        self.grid_scroll_row: int = 0
        self.at_end: bool = False
        self.header_focus: bool = False
        self.header_idx: int = 2  # 0=neu, 1=beliebt, 2=sfw, 3=nsfw, 4=nsfl, 5=pol

        # Post & Overlay State
        self.state: str = STATE_GRID
        self.post_scroll_y: int = 0
        self.is_tapete: bool = False
        self.max_post_scroll: int = 0

        self.overlay_open: bool = False
        self.overlay_scroll_y: int = 0
        self.max_overlay_scroll: int = 0
        self.current_post_info: dict[str, Any] = {"tags": [], "comments": []}
        self.is_loading_info: bool = False

        # Settings & Theme State
        self.theme: str = str(self.config.get("theme", "pr0_dark"))
        self.accent: str = str(self.config.get("accent", "orange"))
        self.autoplay_video: bool = bool(self.config.get("autoplay_video", True))
        self.images_only: bool = bool(self.config.get("images_only", False))
        self.scroll_speed: str = str(self.config.get("scroll_speed", "normal"))
        self.scroll_step: int = 45 if self.scroll_speed == "normal" else (85 if self.scroll_speed == "schnell" else 150)
        self.settings_idx: int = 0
        self.last_api_item_id: int | None = None

        # Feedback & Toast
        self.toast_msg: str | None = None
        self.toast_time: float = 0.0
        self.toast_color: tuple[int, int, int] = COLOR_ORANGE
        self.input_freeze_until: float = 0.0
        self.exit_confirm_time: float = 0.0
        self._cached_progress: tuple[int, int, float] = (0, 0, 1.0)
        self._last_progress_calc: float = 0.0

        # Threading / Background tasks
        self.task_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.is_fetching_feed: bool = False

        # Account Login State
        self.login_mode: str = "qr"
        self.auth_server: AuthCompanionServer | None = None
        self.auth_url: str = ""
        self.qr_surface: pygame.Surface | None = None

        self.direct_username: str = ""
        self.direct_password: str = ""
        self.direct_captcha_code: str = ""
        self.direct_captcha_token: str = ""
        self.direct_captcha_surface: pygame.Surface | None = None
        self.direct_sel_idx: int = 0
        self.is_fetching_captcha: bool = False

        self.virtual_keyboard: VirtualKeyboard | None = None
        self.keyboard_target_field: str | None = None

        # Comment Interaction & Navigation State
        self.post_focus_idx: int = 0
        self.post_focus_targets: dict[int, tuple[int, int]] = {}
        self.comment_modal_open: bool = False
        self.comment_modal_idx: int = 0
        self.comment_modal_target: dict[str, Any] | None = None
        self.comment_reply_parent_id: int | None = None
        self.comment_reply_author: str | None = None

        self.login_status_msg: str | None = None
        self.login_status_color: tuple[int, int, int] | None = None
        self.login_success_pending: tuple[str, str] | None = None

        # Feed error & network auto-retry tracking
        self.feed_error: str | None = None
        self._last_feed_retry: float = time.time()
        self._feed_retry_count: int = 0

        # Pygame & Display Setup
        pygame.init()
        # Release audio device in Pygame so external players (mpv) have exclusive ALSA access on Linux handhelds
        if pygame.mixer.get_init():
            try:
                pygame.mixer.quit()
            except Exception:
                pass

        self.width, self.height, self.fullscreen = self._setup_resolution()
        is_handheld = (os.name != "nt") and self.video.is_handheld

        if os.name == "nt":
            flags = pygame.FULLSCREEN if self.fullscreen else pygame.RESIZABLE
            self.screen = pygame.display.set_mode((self.width, self.height), flags)
        else:
            # On Linux handhelds (TrimUI / muOS / ArkOS / Knulli), ensure a REAL physical display is used
            flags = (pygame.FULLSCREEN | pygame.DOUBLEBUF) if (self.fullscreen or is_handheld) else 0
            res_cfg = str(self.config.get("resolution", "auto")).lower()
            scaled_flag = getattr(pygame, "SCALED", 0)

            def try_create_surface(req_w: int, req_h: int, fl: int) -> pygame.Surface | None:
                # Prioritize (0, 0) native panel resolution when auto, but also test exact (req_w, req_h)
                sizes_to_test = [(0, 0), (req_w, req_h)] if (res_cfg == "auto" and (fl & pygame.FULLSCREEN)) else [(req_w, req_h), (0, 0)]
                for sz in sizes_to_test:
                    for test_fl in [fl, fl | scaled_flag, fl & ~pygame.DOUBLEBUF]:
                        try:
                            surf = pygame.display.set_mode(sz, test_fl)
                            drv = pygame.display.get_driver() if hasattr(pygame.display, "get_driver") else ""
                            if drv not in ("offscreen", "dummy"):
                                return surf
                        except Exception as ex:
                            logger.debug("try_create_surface failed (%s, flags=%d): %s", sz, test_fl, ex)
                return None

            # First attempt: Try current SDL driver / environment
            self.screen = try_create_surface(self.width, self.height, flags)

            # If current driver is offscreen/dummy or failed, try hardware display backends
            if self.screen is None:
                logger.warning("Default display driver is not a physical screen (or failed). Trying hardware video backends...")
                # Note: Prioritize 'mali' for TrimUI (muOS, Knulli, CrossMix) and 'kmsdrm' for ArkOS
                hw_drivers = ["mali", "kmsdrm", "fbcon", "wayland", "x11"]
                for hw_cand in hw_drivers:
                    try:
                        os.environ["SDL_VIDEODRIVER"] = hw_cand
                        if hw_cand == "kmsdrm":
                            os.environ.setdefault("SDL_KMSDRM_DEVICE_INDEX", "0")
                        pygame.display.quit()
                        pygame.display.init()
                        test_drv = pygame.display.get_driver() if hasattr(pygame.display, "get_driver") else ""
                        if test_drv not in ("offscreen", "dummy"):
                            self.screen = try_create_surface(self.width, self.height, flags)
                            if self.screen is not None:
                                logger.info("Successfully activated hardware display backend: %s (driver=%s)", hw_cand, test_drv)
                                break
                    except Exception as ex_drv:
                        logger.info("Hardware driver candidate '%s' not usable: %s", hw_cand, ex_drv)
                        continue

            # Fallback if no candidate worked
            if self.screen is None:
                logger.warning("Hardware display drivers exhausted, falling back to basic display init")
                os.environ.pop("SDL_VIDEODRIVER", None)
                try:
                    pygame.display.quit()
                    pygame.display.init()
                except Exception:
                    pass
                try:
                    self.screen = pygame.display.set_mode((self.width, self.height), pygame.FULLSCREEN if self.fullscreen else 0)
                except Exception:
                    self.screen = pygame.display.set_mode((self.width, self.height))

        # Query actual surface dimensions in case SDL adapted to physical display
        real_w, real_h = self.screen.get_size()
        if real_w != self.width or real_h != self.height:
            logger.info("Display surface adapted to native %dx%d (requested %dx%d)", real_w, real_h, self.width, self.height)
            self.width, self.height = real_w, real_h

        driver = pygame.display.get_driver() if hasattr(pygame.display, "get_driver") else "unknown"
        logger.info("Pygame display initialized: %dx%d (fullscreen=%s, driver=%s)",
                    self.width, self.height, self.fullscreen, driver)
        pygame.display.set_caption("pr0-retroconsole")

        self.clock = pygame.time.Clock()
        self.fps = int(self.config.get("fps", 30))
        self.running = True

        self.ui = UIRenderer(self.screen, self.width, self.height)
        self.ui.set_theme(self.theme, self.accent)

    def _setup_resolution(self) -> tuple[int, int, bool]:
        """Detect and set up display resolution."""
        res_cfg = str(self.config.get("resolution", "auto")).lower()
        w = int(self.config.get("width", 640))
        h = int(self.config.get("height", 480))
        fs = bool(self.config.get("fullscreen", False))

        # On Linux handhelds (TrimUI / R36S / muOS / ArkOS), always enforce fullscreen!
        is_handheld = (os.name != "nt") and self.video.is_handheld
        if is_handheld:
            fs = True

        if res_cfg == "640x480":
            return 640, 480, fs
        elif res_cfg == "1280x720":
            return 1280, 720, fs
        elif res_cfg == "1024x768":
            return 1024, 768, fs
        elif res_cfg == "auto":
            # Auto-detect display modes
            try:
                desktop_sizes = pygame.display.get_desktop_sizes()
                if desktop_sizes and desktop_sizes[0][0] > 0 and desktop_sizes[0][1] > 0:
                    dw, dh = desktop_sizes[0]
                    logger.info("Detected desktop native resolution: %dx%d", dw, dh)
                    return dw, dh, fs
            except Exception:
                pass

            try:
                display_info = pygame.display.Info()
                cur_w, cur_h = display_info.current_w, display_info.current_h
                if cur_w > 0 and cur_h > 0:
                    logger.info("Detected display info resolution: %dx%d", cur_w, cur_h)
                    return cur_w, cur_h, fs
            except Exception:
                pass

        return w, h, fs

    def set_toast(self, message: str, color: tuple[int, int, int] = COLOR_ORANGE, duration: float = 2.0) -> None:
        """Display a temporary toast notification."""
        self.toast_msg = message
        self.toast_color = color
        self.toast_time = time.time() + duration

    # -------------------------------------------------------------------------
    # Background Task Runner (ha-retroconsole pattern)
    # -------------------------------------------------------------------------

    def _start_background_task(self, task_type: str, target_func: Any, *args: Any, **kwargs: Any) -> None:
        """Execute a function in a background thread and deliver its result to the queue."""
        def wrapper() -> None:
            try:
                res = target_func(*args, **kwargs)
                self.task_queue.put({"status": "success", "type": task_type, "result": res})
            except Exception as e:
                logger.error("Background task %s failed: %s", task_type, e)
                self.task_queue.put({"status": "error", "type": task_type, "error": str(e)})

        t = threading.Thread(target=wrapper, daemon=True)
        t.start()

    def fetch_feed(self, append: bool = False) -> None:
        """Fetch feed items from API asynchronously."""
        if self.is_fetching_feed:
            return
        self.is_fetching_feed = True

        if not append:
            self.last_api_item_id = None

        older_id = self.last_api_item_id if (append and self.last_api_item_id) else (self.items[-1]["id"] if (append and self.items) else None)

        def do_fetch() -> dict[str, Any]:
            return self.api.get_items(
                promoted=self.promoted,
                flags=self.flags,
                older=older_id,
            )

        task_type = "feed_append" if append else "feed_fresh"
        self._start_background_task(task_type, do_fetch)

    def fetch_post_info(self, item_id: int) -> None:
        """Fetch tags and comments for post details overlay."""
        self.is_loading_info = True
        self.current_post_info = {"tags": [], "comments": []}

        def do_fetch_info() -> dict[str, Any]:
            return self.api.get_info(item_id)

        self._start_background_task("post_info", do_fetch_info)

    def cast_vote(self, item_id: int, vote_val: int) -> None:
        """Cast upvote/downvote asynchronously."""
        if not self.api.is_authenticated:
            self.set_toast("Login erforderlich für Voting!", COLOR_RED, duration=2.5)
            return

        def do_vote() -> dict[str, Any]:
            return self.api.vote(item_id, vote_val)

        self._start_background_task("vote", do_vote)
        if vote_val == 1:
            self.set_toast("+1 Blussi vergeben!", COLOR_GREEN, duration=1.8)
        elif vote_val == -1:
            self.set_toast("-1 Downvote vergeben!", COLOR_RED, duration=1.8)

    def cast_comment_vote(self, comment_id: int, vote_val: int) -> None:
        """Cast comment upvote/downvote asynchronously with optimistic UI update."""
        if not self.api.is_authenticated:
            self.set_toast("Login erforderlich für Voting!", COLOR_RED, duration=2.5)
            return

        # Optimistically update in self.current_post_info["comments"]
        for c in self.current_post_info.get("comments", []):
            if c.get("id") == comment_id:
                prev_vote = c.get("user_vote", 0)
                if prev_vote == vote_val:
                    # Neutralize vote
                    new_vote = 0
                    if vote_val == 1:
                        c["up"] = max(0, c.get("up", 0) - 1)
                    else:
                        c["down"] = max(0, c.get("down", 0) - 1)
                else:
                    new_vote = vote_val
                    if prev_vote == 1:
                        c["up"] = max(0, c.get("up", 0) - 1)
                    elif prev_vote == -1:
                        c["down"] = max(0, c.get("down", 0) - 1)

                    if vote_val == 1:
                        c["up"] = c.get("up", 0) + 1
                    elif vote_val == -1:
                        c["down"] = c.get("down", 0) + 1

                c["user_vote"] = new_vote
                break

        # Clear layout cache for this post so updated score is rendered immediately
        if self.items and self.selected_idx < len(self.items):
            post_id = self.items[self.selected_idx]["id"]
            self.ui.clear_comment_cache(post_id)

        if vote_val == 1:
            self.set_toast("+1 Blussi vergeben!", COLOR_GREEN, duration=1.8)
        elif vote_val == -1:
            self.set_toast("-1 Downvote vergeben!", COLOR_RED, duration=1.8)

        def do_vote_comment() -> dict[str, Any]:
            return self.api.vote_comment(comment_id, vote_val)

        self._start_background_task("vote_comment", do_vote_comment)

    def _commit_comment_keyboard(self) -> None:
        """Submit typed comment or reply to pr0gramm API."""
        if not self.virtual_keyboard:
            return

        text = self.virtual_keyboard.text.strip()
        parent_id = self.comment_reply_parent_id or 0
        self.virtual_keyboard = None
        self.comment_reply_parent_id = None
        self.comment_reply_author = None

        if not text:
            self.set_toast("Kommentar darf nicht leer sein!", COLOR_RED, duration=2.0)
            return

        if not self.items or self.selected_idx >= len(self.items):
            return

        post_id = self.items[self.selected_idx]["id"]
        self.set_toast("Sende Kommentar...", COLOR_ORANGE, duration=2.0)

        def do_post_comment() -> dict[str, Any]:
            res = self.api.post_comment(item_id=post_id, parent_id=parent_id, text=text)
            return {"post_id": post_id, "res": res}

        self._start_background_task("post_comment", do_post_comment)

    def _handle_comment_modal_choice(self, choice_idx: int) -> None:
        """Handle selected option in comment action modal."""
        self.comment_modal_open = False
        target = self.comment_modal_target
        if not target:
            return

        comment_id = target.get("id", 0)
        author = target.get("name", "unbekannt")

        if choice_idx == 0:  # ✎ Antworten
            if not self.api.is_authenticated:
                self.set_toast("Login erforderlich zum Kommentieren!", COLOR_RED, duration=2.5)
                return
            self.comment_reply_parent_id = comment_id
            self.comment_reply_author = author
            self.virtual_keyboard = VirtualKeyboard(
                title=f"Antwort an @{author}",
                initial_text="",
                is_password=False,
                max_length=500,
            )
        elif choice_idx == 1:  # ▲ +1 (Blussi)
            self.cast_comment_vote(comment_id, 1)
        elif choice_idx == 2:  # ▼ -1 (Downvote)
            self.cast_comment_vote(comment_id, -1)
        elif choice_idx == 3:  # ✕ Abbrechen
            pass

    def _auto_scroll_post_focus(self) -> None:
        """Adjust post_scroll_y smoothly to keep currently focused element within viewport."""
        if self.post_focus_idx == 0:
            self.post_scroll_y = 0
            return

        if self.post_focus_idx not in self.post_focus_targets:
            return

        target_y, target_h = self.post_focus_targets[self.post_focus_idx]
        viewport_h = self.height - self.ui.header_height - self.ui.footer_height

        # If target starts above visible area
        if target_y < self.post_scroll_y + 10:
            self.post_scroll_y = max(0, target_y - 20)
        # If target extends below visible area
        elif target_y + target_h > self.post_scroll_y + viewport_h - 10:
            self.post_scroll_y = min(self.max_post_scroll, target_y + target_h - viewport_h + 30)

    def _update_inline_video(self) -> None:
        """Start inline video playback if current post is a video and autoplay is enabled."""
        if self.state == STATE_POST and self.items and self.autoplay_video:
            item = self.items[self.selected_idx]
            if Pr0API.is_video(item):
                is_nsfw = bool(item.get("flags", 1) & (FLAG_NSFW | FLAG_NSFL))
                if is_nsfw and not self.api.is_age_verified and not self.av_cookie:
                    self.set_toast("NSFW: Altersverifikation auf pr0gramm.com nötig!", COLOR_RED, duration=3.0)
                media_url = Pr0API.get_media_url(item)
                local_path = self.cache.get_local_path(media_url)
                stream_target = local_path if local_path else media_url
                orig_w = item.get("width") or 16
                orig_h = item.get("height") or 9
                max_w = min(640, self.width - 24)
                max_h = int((self.height - self.ui.header_height - self.ui.footer_height) * 0.72)
                scale = min(max_w / orig_w, max_h / orig_h)
                tw = max(100, int(orig_w * scale))
                th = max(60, int(orig_h * scale))
                self.inline_player.play_inline(stream_target, tw, th)
                return
        self.inline_player.stop()

    # -------------------------------------------------------------------------
    # State Transitions & Input Dispatch
    # -------------------------------------------------------------------------

    def handle_actions(self) -> None:
        """Poll input and dispatch based on current state."""
        if time.time() < self.input_freeze_until:
            self.input_mgr.clear_events()
            return

        actions = self.input_mgr.poll_actions()

        # Smooth continuous scrolling in post view when holding analog stick
        if self.state == STATE_POST and not self.virtual_keyboard and not self.comment_modal_open:
            if abs(self.input_mgr.stick_ry) > self.input_mgr.axis_threshold or abs(self.input_mgr.stick_ly) > self.input_mgr.axis_threshold:
                cont_y = self.input_mgr.stick_ry if abs(self.input_mgr.stick_ry) > self.input_mgr.axis_threshold else self.input_mgr.stick_ly
                speed_factor = 0.28 if self.scroll_speed == "normal" else (0.45 if self.scroll_speed == "schnell" else 0.75)
                scroll_delta = int(cont_y * self.scroll_step * speed_factor)
                if scroll_delta != 0:
                    self.post_scroll_y = max(0, min(self.max_post_scroll, self.post_scroll_y + scroll_delta))

        # Handle physical keyboard typing when virtual keyboard is active
        if self.virtual_keyboard:
            for k_ev in self.input_mgr.last_key_events:
                res = self.virtual_keyboard.handle_physical_key(k_ev)
                if res == "DONE":
                    if self.state == STATE_LOGIN:
                        self._commit_keyboard()
                    elif self.state == STATE_POST:
                        self._commit_comment_keyboard()
                    break
                elif res == "CANCEL":
                    if self.state == STATE_LOGIN:
                        self.virtual_keyboard = None
                        self.keyboard_target_field = None
                    elif self.state == STATE_POST:
                        self.virtual_keyboard = None
                        self.comment_reply_parent_id = None
                        self.comment_reply_author = None
                    break

        for action in actions:
            if action == ACTION_QUIT:
                self.running = False
                return

            old_state = self.state
            if self.state == STATE_GRID:
                self._handle_grid_action(action)
            elif self.state == STATE_POST:
                self._handle_post_action(action)
            elif self.state == STATE_SETTINGS:
                self._handle_settings_action(action)
            elif self.state == STATE_BUTTON_TEST:
                self._handle_button_test_action(action)
            elif self.state == STATE_LOGIN:
                self._handle_login_action(action)

            # Prevent action bleeding across state transitions
            if self.state != old_state:
                self.input_mgr.clear_events()
                self.input_freeze_until = time.time() + 0.25
                break

    def _start_login_flow(self) -> None:
        """Start login process: launch companion web server and fetch initial captcha."""
        self.state = STATE_LOGIN
        self.login_mode = "qr"
        self.login_status_msg = "Warte auf Verbindung..."
        self.login_status_color = None
        self.virtual_keyboard = None
        self.keyboard_target_field = None
        self.direct_sel_idx = 0
        self.direct_captcha_code = ""

        # Callback from companion web server
        def on_success(name: str, cookie: str) -> None:
            self.login_success_pending = (name, cookie)

        # Start companion server
        self.auth_server = AuthCompanionServer(self.api, on_success)
        ip, port = self.auth_server.start()
        self.auth_url = f"http://{ip}:{port}"
        if generate_qr_surface:
            self.qr_surface = generate_qr_surface(self.auth_url, target_size=int(170 * self.ui.scale))

        # Pre-fetch captcha for direct mode in background
        threading.Thread(target=self._fetch_direct_captcha, daemon=True).start()

    def _stop_login_flow(self) -> None:
        """Tear down companion web server and virtual keyboard."""
        if self.auth_server:
            self.auth_server.stop()
            self.auth_server = None
        self.virtual_keyboard = None
        self.keyboard_target_field = None

    def _fetch_direct_captcha(self) -> None:
        """Fetch and decode captcha for direct handheld login."""
        if self.is_fetching_captcha:
            return
        self.is_fetching_captcha = True
        try:
            res = self.api.fetch_captcha()
            token = res.get("token", "")
            b64_str = res.get("captcha", "")
            if token and "," in b64_str:
                raw_data = base64.b64decode(b64_str.split(",", 1)[1])
                surf = pygame.image.load(io.BytesIO(raw_data))
                self.direct_captcha_token = token
                self.direct_captcha_surface = surf
                self.direct_captcha_code = ""
        except Exception as e:
            logger.error("Error fetching direct captcha: %s", e)
        finally:
            self.is_fetching_captcha = False

    def _handle_direct_login_submission(self) -> None:
        """Execute direct login with user-provided credentials."""
        uname = self.direct_username.strip()
        pwd = self.direct_password
        captcha = self.direct_captcha_code.strip()

        if not uname:
            self.login_status_msg = "Bitte Benutzernamen eingeben!"
            self.login_status_color = COLOR_RED
            return
        if not pwd:
            self.login_status_msg = "Bitte Passwort eingeben!"
            self.login_status_color = COLOR_RED
            return
        if not captcha:
            self.login_status_msg = "Bitte Captcha-Code eingeben!"
            self.login_status_color = COLOR_RED
            return

        self.login_status_msg = "Anmeldung läuft..."
        self.login_status_color = COLOR_ORANGE

        def do_login():
            res = self.api.login(uname, pwd, self.direct_captcha_token, captcha)
            if res.get("success"):
                self.login_success_pending = (res.get("username", uname), res.get("me_cookie", ""))
            else:
                self.login_status_msg = res.get("error", "Anmeldung fehlgeschlagen.")
                self.login_status_color = COLOR_RED
                self._fetch_direct_captcha()

        threading.Thread(target=do_login, daemon=True).start()

    def _open_keyboard(self, field_id: str, title: str, initial_val: str, is_pw: bool = False) -> None:
        self.keyboard_target_field = field_id
        self.virtual_keyboard = VirtualKeyboard(title=title, initial_text=initial_val, is_password=is_pw)

    def _commit_keyboard(self) -> None:
        if not self.virtual_keyboard or not self.keyboard_target_field:
            return
        val = self.virtual_keyboard.text
        if self.keyboard_target_field == "username":
            self.direct_username = val
        elif self.keyboard_target_field == "password":
            self.direct_password = val
        elif self.keyboard_target_field == "captcha":
            self.direct_captcha_code = val
        self.virtual_keyboard = None
        self.keyboard_target_field = None

    def _handle_login_action(self, action: str) -> None:
        """Handle input when in STATE_LOGIN."""
        # If virtual keyboard is open
        if self.virtual_keyboard:
            res = self.virtual_keyboard.handle_action(action)
            if res == "DONE":
                self._commit_keyboard()
            elif res == "CANCEL":
                self.virtual_keyboard = None
                self.keyboard_target_field = None
            return

        # Cancel / Back
        if action == ACTION_BACK:
            self._stop_login_flow()
            self.state = STATE_SETTINGS
            return

        # Switch between QR / Direct mode (X Button / ACTION_INFO)
        if action in (ACTION_INFO,):
            self.login_mode = "direct" if self.login_mode == "qr" else "qr"
            self.login_status_msg = None
            self.login_status_color = None
            return

        if self.login_mode == "direct":
            # Refresh Captcha (Y Button / ACTION_TOGGLE_MODE)
            if action == ACTION_TOGGLE_MODE:
                threading.Thread(target=self._fetch_direct_captcha, daemon=True).start()
                return

            # Navigate between fields (0=user, 1=pass, 2=captcha, 3=login_btn, 4=refresh_btn)
            if action == ACTION_UP:
                self.direct_sel_idx = (self.direct_sel_idx - 1) % 5
            elif action == ACTION_DOWN:
                self.direct_sel_idx = (self.direct_sel_idx + 1) % 5
            elif action in (ACTION_LEFT, ACTION_RIGHT):
                if self.direct_sel_idx in (3, 4):
                    self.direct_sel_idx = 4 if self.direct_sel_idx == 3 else 3

            elif action == ACTION_SELECT:
                if self.direct_sel_idx == 0:
                    self._open_keyboard("username", "Benutzername eingeben", self.direct_username)
                elif self.direct_sel_idx == 1:
                    self._open_keyboard("password", "Passwort eingeben", self.direct_password, is_pw=True)
                elif self.direct_sel_idx == 2:
                    self._open_keyboard("captcha", "Captcha-Code eingeben", self.direct_captcha_code)
                elif self.direct_sel_idx == 3:
                    self._handle_direct_login_submission()
                elif self.direct_sel_idx == 4:
                    threading.Thread(target=self._fetch_direct_captcha, daemon=True).start()


    def _handle_button_test_action(self, action: str) -> None:
        """Handle actions during Button Test mode."""
        # START or 2x B exits the test
        if action == ACTION_BACK:
            now = time.time()
            if self.exit_confirm_time > 0 and (now - self.exit_confirm_time) < 2.5:
                self.state = STATE_SETTINGS
                self.exit_confirm_time = 0.0
                self.input_mgr.clear_events()
                self.input_freeze_until = time.time() + 0.25
                return
            else:
                self.exit_confirm_time = now
                self.set_toast("B erneut drücken zum Beenden", COLOR_ORANGE, duration=2.5)
                return

        if self.input_mgr.last_diag.get("button_label") == "START":
            self.state = STATE_SETTINGS
            self.exit_confirm_time = 0.0
            self.input_mgr.clear_events()
            self.input_freeze_until = time.time() + 0.25
            return

    def _handle_grid_action(self, action: str) -> None:
        cols = self.ui.grid_cols
        total = len(self.items)

        if action != ACTION_BACK:
            self.exit_confirm_time = 0.0

        # -------------------------------------------------------------
        # 1. Header Focus Navigation (Interactive Filter & Mode Bar)
        # -------------------------------------------------------------
        if self.header_focus:
            header_items = ["neu", "beliebt", "sfw", "nsfw", "nsfl", "pol"]
            if action == ACTION_LEFT:
                self.header_idx = (self.header_idx - 1) % len(header_items)
                return
            elif action == ACTION_RIGHT:
                self.header_idx = (self.header_idx + 1) % len(header_items)
                return
            elif action in (ACTION_DOWN, ACTION_BACK):
                self.header_focus = False
                if total > 0:
                    col = max(0, self.header_idx - 2) if self.header_idx >= 2 else 0
                    self.selected_idx = min(total - 1, min(cols - 1, col))
                return
            elif action == ACTION_SELECT:
                target = header_items[self.header_idx]
                if target == "neu":
                    if self.promoted != 0:
                        self.promoted = 0
                        self.set_toast("Modus: Neu", COLOR_ORANGE, duration=1.5)
                        self.items = []
                        self.selected_idx = 0
                        self.grid_scroll_row = 0
                        self.fetch_feed(append=False)
                elif target == "beliebt":
                    if self.promoted != 1:
                        self.promoted = 1
                        self.set_toast("Modus: Beliebt", COLOR_ORANGE, duration=1.5)
                        self.items = []
                        self.selected_idx = 0
                        self.grid_scroll_row = 0
                        self.fetch_feed(append=False)
                else:
                    flag_mask_map = {
                        "sfw": FLAG_SFW,
                        "nsfw": 2,
                        "nsfl": 4,
                        "pol": 8,
                    }
                    mask = flag_mask_map.get(target, 0)
                    new_flags = self.flags ^ mask
                    if new_flags == 0:
                        self.set_toast("Mindestens ein Filter muss aktiv bleiben!", COLOR_RED, duration=1.5)
                    else:
                        self.flags = new_flags
                        self.config["flags"] = self.flags
                        save_config(self.config, self.config_path)
                        flag_name = Pr0API.get_flag_string(self.flags)
                        if not self.api.is_authenticated and (self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP)):
                            if not (self.flags & FLAG_SFW):
                                self.set_toast(f"Filter: {flag_name} (Login in [START] nötig!)", COLOR_ORANGE, duration=2.5)
                            else:
                                self.set_toast(f"Filter: {flag_name} (NSFW erfordert Login)", COLOR_ORANGE, duration=2.0)
                        elif self.flags == 2:
                            self.set_toast("Filter: Nur NSFW", COLOR_ORANGE, duration=1.5)
                        elif self.flags == 4:
                            self.set_toast("Filter: Nur NSFL", COLOR_ORANGE, duration=1.5)
                        else:
                            self.set_toast(f"Filter: {flag_name}", COLOR_ORANGE, duration=1.5)
                        self.items = []
                        self.selected_idx = 0
                        self.grid_scroll_row = 0
                        self.fetch_feed(append=False)
                return
            elif action in (ACTION_SOLO_FLAG, ACTION_TOGGLE_MODE):
                # Solo-Select flag with Y button (or toggle Neu/Beliebt)
                target = header_items[self.header_idx]
                flag_mask_map = {
                    "sfw": FLAG_SFW,
                    "nsfw": 2,
                    "nsfl": 4,
                    "pol": 8,
                }
                if target in flag_mask_map:
                    self.flags = flag_mask_map[target]
                    self.config["flags"] = self.flags
                    save_config(self.config, self.config_path)
                    flag_name = Pr0API.get_flag_string(self.flags)
                    if not self.api.is_authenticated and target in ("nsfw", "nsfl", "pol"):
                        self.set_toast(f"Filter: Nur {flag_name} (Login in [START] nötig!)", COLOR_ORANGE, duration=3.0)
                    else:
                        self.set_toast(f"Filter: Nur {flag_name}", COLOR_ORANGE, duration=1.5)
                    self.items = []
                    self.selected_idx = 0
                    self.grid_scroll_row = 0
                    self.fetch_feed(append=False)
                elif target in ("neu", "beliebt"):
                    self.promoted = 0 if self.promoted == 1 else 1
                    mode_name = "Neu" if self.promoted == 0 else "Beliebt"
                    self.set_toast(f"Modus: {mode_name}", COLOR_ORANGE, duration=1.5)
                    self.items = []
                    self.selected_idx = 0
                    self.grid_scroll_row = 0
                    self.fetch_feed(append=False)
                return
            elif action == ACTION_SETTINGS:
                self.state = STATE_SETTINGS
                self.settings_idx = 0
                return
            return

        # -------------------------------------------------------------
        # 2. Grid View Navigation
        # -------------------------------------------------------------
        if action == ACTION_UP:
            if total > 0 and self.selected_idx >= cols:
                self.selected_idx -= cols
            else:
                # Reached top row (or feed is empty): jump into interactive header!
                self.header_focus = True
                col = (self.selected_idx % cols) if total > 0 else 0
                self.header_idx = min(5, max(2, col + 2))
                return
        elif action == ACTION_DOWN and total > 0:
            if self.selected_idx + cols < total:
                self.selected_idx += cols
            elif self.selected_idx < total - 1:
                self.selected_idx = total - 1
        elif action == ACTION_LEFT and total > 0:
            if self.selected_idx % cols > 0:
                self.selected_idx -= 1
        elif action == ACTION_RIGHT and total > 0:
            if self.selected_idx % cols < cols - 1 and self.selected_idx < total - 1:
                self.selected_idx += 1
        elif action == ACTION_SELECT:
            if total > 0:
                # Open selected post
                self.state = STATE_POST
                self.post_scroll_y = 0
                self.post_focus_idx = 0
                self.comment_modal_open = False
                self.virtual_keyboard = None
                # Preload full image or video and fetch tags & comments
                item = self.items[self.selected_idx]
                self.cache.request_download(Pr0API.get_media_url(item), priority=0)
                self.fetch_post_info(item["id"])
                self._update_inline_video()
                return
            else:
                # Feed is empty: if login is required for current filter, open Settings/Login directly
                if (not self.api.is_authenticated) and (
                    self.feed_error == "auth_required"
                    or bool(self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP) and not (self.flags & FLAG_SFW))
                ):
                    self.state = STATE_SETTINGS
                    self.settings_idx = 0
                    self.set_toast("Bitte zuerst anmelden für NSFW/NSFL!", COLOR_ORANGE, duration=2.5)
                    return

                # Otherwise manual reload
                self.set_toast("Verbinde mit pr0gramm...", COLOR_ORANGE, duration=2.5)
                self._last_feed_retry = time.time()
                self._feed_retry_count = 0
                self.fetch_feed(append=False)
                return
        elif action == ACTION_SETTINGS:
            # Open Settings with START
            self.state = STATE_SETTINGS
            self.settings_idx = 0
            return
        elif action == ACTION_TOGGLE_MODE:
            # Switch between Beliebt and Neu (via L2 / R2)
            self.promoted = 0 if self.promoted == 1 else 1
            mode_name = "Neu" if self.promoted == 0 else "Beliebt"
            self.set_toast(f"Modus: {mode_name}", COLOR_ORANGE, duration=1.5)
            self.items = []
            self.selected_idx = 0
            self.grid_scroll_row = 0
            self.fetch_feed(append=False)
            return
        elif action in (ACTION_UPVOTE, ACTION_DOWNVOTE):
            # Quick-cycle content filter (Flags): SFW (1) -> Nur NSFW (2) -> SFW+NSFW (3) -> SFW+NSFW+NSFL (7) -> Alle (15)
            flag_cycle = [1, 2, 3, 7, 15]
            curr_idx = flag_cycle.index(self.flags) if self.flags in flag_cycle else 0
            delta = 1 if action == ACTION_UPVOTE else -1
            self.flags = flag_cycle[(curr_idx + delta) % len(flag_cycle)]
            self.config["flags"] = self.flags
            save_config(self.config, self.config_path)

            flag_name = Pr0API.get_flag_string(self.flags)
            if not self.api.is_authenticated and (self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP)):
                if not (self.flags & FLAG_SFW):
                    self.set_toast(f"Filter: {flag_name} (Login in [START] nötig!)", COLOR_ORANGE, duration=2.5)
                else:
                    self.set_toast(f"Filter: {flag_name} (NSFW erfordert Login)", COLOR_ORANGE, duration=2.0)
            elif self.flags == 2:
                self.set_toast("Filter: Nur NSFW", COLOR_ORANGE, duration=1.5)
            elif self.flags == 4:
                self.set_toast("Filter: Nur NSFL", COLOR_ORANGE, duration=1.5)
            else:
                self.set_toast(f"Filter: {flag_name}", COLOR_ORANGE, duration=1.5)
            self.items = []
            self.selected_idx = 0
            self.grid_scroll_row = 0
            self.fetch_feed(append=False)
            return
        elif action == ACTION_BACK:
            now = time.time()
            if self.exit_confirm_time > 0 and (now - self.exit_confirm_time) < 2.5:
                self.running = False
                return
            else:
                self.exit_confirm_time = now
                self.set_toast("B erneut drücken zum Beenden", COLOR_ORANGE, duration=2.5)
                return

        # Keep selected item visible in grid scroll
        curr_row = self.selected_idx // cols
        visible_rows = max(1, (self.height - self.ui.header_height - self.ui.footer_height) // (self.ui.card_size + self.ui.grid_gap))

        if curr_row < self.grid_scroll_row:
            self.grid_scroll_row = curr_row
        elif curr_row >= self.grid_scroll_row + visible_rows:
            self.grid_scroll_row = curr_row - visible_rows + 1

        # Fluid Auto-Paging: Load older items when reaching near bottom
        if not self.at_end and not self.is_fetching_feed and (total - self.selected_idx) < (cols * 2):
            self.fetch_feed(append=True)

    def _handle_post_action(self, action: str) -> None:
        if not self.items:
            self.state = STATE_GRID
            return

        # Handle active comment VirtualKeyboard
        if self.virtual_keyboard:
            res = self.virtual_keyboard.handle_action(action)
            if res == "DONE":
                self._commit_comment_keyboard()
            elif res == "CANCEL":
                self.virtual_keyboard = None
                self.comment_reply_parent_id = None
                self.comment_reply_author = None
            return

        # Handle active Comment Modal
        if self.comment_modal_open:
            if action == ACTION_UP:
                self.comment_modal_idx = (self.comment_modal_idx - 1) % 4
            elif action == ACTION_DOWN:
                self.comment_modal_idx = (self.comment_modal_idx + 1) % 4
            elif action == ACTION_SELECT:
                self._handle_comment_modal_choice(self.comment_modal_idx)
            elif action in (ACTION_UPVOTE, ACTION_SOLO_FLAG):
                self._handle_comment_modal_choice(1)
            elif action in (ACTION_DOWNVOTE, ACTION_INFO):
                self._handle_comment_modal_choice(2)
            elif action == ACTION_BACK:
                self.comment_modal_open = False
            return

        item = self.items[self.selected_idx]

        # 1. Navigate between posts: Left (previous) / Right (next)
        if action == ACTION_LEFT:
            if self.selected_idx > 0:
                self.selected_idx -= 1
                self.post_scroll_y = 0
                self.post_focus_idx = 0
                self.comment_modal_open = False
                self.virtual_keyboard = None
                prev_item = self.items[self.selected_idx]
                if not Pr0API.is_video(prev_item):
                    self.cache.request_download(Pr0API.get_media_url(prev_item), priority=0)
                self.fetch_post_info(prev_item["id"])
                self._update_inline_video()
            return

        elif action == ACTION_RIGHT:
            if self.selected_idx < len(self.items) - 1:
                self.selected_idx += 1
                self.post_scroll_y = 0
                self.post_focus_idx = 0
                self.comment_modal_open = False
                self.virtual_keyboard = None
                next_item = self.items[self.selected_idx]
                if not Pr0API.is_video(next_item):
                    self.cache.request_download(Pr0API.get_media_url(next_item), priority=0)
                self.fetch_post_info(next_item["id"])
                self._update_inline_video()
                # Auto-paging near end of feed
                if not self.at_end and (len(self.items) - self.selected_idx) < 4:
                    self.fetch_feed(append=True)
            return

        # 2. Focus navigation between Media (0) -> New Comment (1) -> Comments (2..N+1)
        comments = self.current_post_info.get("comments", [])
        max_focus_idx = 1 + len(comments)

        if action == ACTION_DOWN:
            if self.post_focus_idx == 0:
                target_h = self.post_focus_targets.get(0, (0, 0))[1]
                viewport_h = self.height - self.ui.header_height - self.ui.footer_height
                if target_h > viewport_h and self.post_scroll_y + viewport_h < target_h + 30:
                    self.post_scroll_y = min(self.max_post_scroll, self.post_scroll_y + 120)
                    return
                else:
                    self.post_focus_idx = min(self.post_focus_idx + 1, max_focus_idx)
            else:
                self.post_focus_idx = min(self.post_focus_idx + 1, max_focus_idx)

            self._auto_scroll_post_focus()
            return

        elif action == ACTION_UP:
            if self.post_focus_idx == 0:
                if self.post_scroll_y > 0:
                    self.post_scroll_y = max(0, self.post_scroll_y - 120)
                    return
            else:
                self.post_focus_idx = max(0, self.post_focus_idx - 1)

            self._auto_scroll_post_focus()
            return

        # 3. Actions: Play Video in external player (Fullscreen/Audio), Open New Comment, or Comment Modal
        elif action == ACTION_SELECT:
            if self.post_focus_idx == 0:
                if Pr0API.is_video(item):
                    is_nsfw = bool(item.get("flags", 1) & (FLAG_NSFW | FLAG_NSFL))
                    if is_nsfw and not self.api.is_age_verified and not self.av_cookie:
                        self.set_toast("NSFW: Altersverifikation auf pr0gramm.com nötig!", COLOR_RED, duration=3.0)
                    media_url = Pr0API.get_media_url(item)
                    local_path = self.cache.get_local_path(media_url)
                    if not self.autoplay_video and not self.inline_player._running:
                        # Manually start inline video if autoplay is off
                        stream_target = local_path if local_path else media_url
                        orig_w = item.get("width") or 16
                        orig_h = item.get("height") or 9
                        max_w = min(640, self.width - 24)
                        max_h = int((self.height - self.ui.header_height - self.ui.footer_height) * 0.72)
                        scale = min(max_w / orig_w, max_h / orig_h)
                        tw = max(100, int(orig_w * scale))
                        th = max(60, int(orig_h * scale))
                        self.inline_player.play_inline(stream_target, tw, th)
                    else:
                        self.inline_player.stop()
                        play_target = local_path if local_path else media_url
                        played = self.video.play(play_target, self.width, self.height)
                        if pygame.display.get_surface():
                            self.screen = pygame.display.get_surface()
                            self.ui.screen = self.screen
                        if not played:
                            self.set_toast("mpv/ffplay nicht installiert!", COLOR_RED, duration=2.0)
                        self._update_inline_video()

            elif self.post_focus_idx == 1:
                if not self.api.is_authenticated:
                    self.set_toast("Login erforderlich zum Kommentieren!", COLOR_RED, duration=2.5)
                    return
                self.comment_reply_parent_id = 0
                self.comment_reply_author = None
                self.virtual_keyboard = VirtualKeyboard(
                    title="Neuer Kommentar",
                    initial_text="",
                    is_password=False,
                    max_length=500,
                )

            elif self.post_focus_idx >= 2:
                c_idx = self.post_focus_idx - 2
                if 0 <= c_idx < len(comments):
                    self.comment_modal_target = comments[c_idx]
                    self.comment_modal_idx = 0
                    self.comment_modal_open = True

        # 4. Upvote (+1) via R1 or Y
        elif action in (ACTION_UPVOTE, ACTION_SOLO_FLAG):
            if self.post_focus_idx >= 2:
                c_idx = self.post_focus_idx - 2
                if 0 <= c_idx < len(comments):
                    self.cast_comment_vote(comments[c_idx]["id"], 1)
            else:
                self.cast_vote(item["id"], 1)

        # 5. Downvote (-1) via L1 or X
        elif action in (ACTION_DOWNVOTE, ACTION_INFO):
            if self.post_focus_idx >= 2:
                c_idx = self.post_focus_idx - 2
                if 0 <= c_idx < len(comments):
                    self.cast_comment_vote(comments[c_idx]["id"], -1)
            else:
                self.cast_vote(item["id"], -1)

        elif action == ACTION_SETTINGS:
            self.inline_player.stop()
            self.state = STATE_SETTINGS
            self.settings_idx = 0

        elif action == ACTION_BACK:
            self.inline_player.stop()
            self.comment_modal_open = False
            self.virtual_keyboard = None
            self.post_focus_idx = 0
            self.state = STATE_GRID

    # -------------------------------------------------------------------------
    # Settings Menu & Configuration Logic
    # -------------------------------------------------------------------------

    def _build_settings_menu(self) -> list[dict[str, Any]]:
        """Construct setting entries with current values, choices, and swatches."""
        theme_keys = list(THEMES.keys())
        accent_keys = list(ACCENTS.keys())
        scroll_keys = ["normal", "schnell", "turbo"]
        flags_options = [
            (FLAG_SFW, "SFW (1)"),
            (2, "Nur NSFW (2)"),
            (FLAG_SFW | 2, "SFW + NSFW (3)"),
            (4, "Nur NSFL (4)"),
            (FLAG_SFW | 2 | 4, "SFW + NSFW + NSFL (7)"),
            (15, "Alle Flags (15)"),
        ]

        flag_display = "SFW (1)"
        for f_val, f_lbl in flags_options:
            if f_val == self.flags:
                flag_display = f_lbl
                if not self.api.is_authenticated and (f_val & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP)):
                    flag_display += " (Login nötig)"
                break

        if self.api.is_authenticated:
            account_display = f"★ {self.api.username} [A: Abmelden]"
        else:
            account_display = "Nicht angemeldet [A: Anmelden]"

        # Determine player display
        if self.video.has_player():
            player_disp = f"{self.video.player_type.upper()} ({Path(self.video.player_path).name})"
        elif self.inline_player.is_available:
            player_disp = "Inline (ffmpeg)"
        else:
            player_disp = "Nicht gefunden"

        return [
            {
                "id": "account",
                "label": "pr0gramm Account",
                "type": "action",
                "display_value": account_display,
            },
            {
                "id": "theme",
                "label": "Farbschema (Theme)",
                "type": "choice",
                "value": self.theme,
                "display_value": THEMES.get(self.theme, {}).get("name", self.theme),
                "options": theme_keys,
                "swatch_color": THEMES.get(self.theme, {}).get("card"),
            },
            {
                "id": "accent",
                "label": "Akzentfarbe",
                "type": "choice",
                "value": self.accent,
                "display_value": ACCENTS.get(self.accent, {}).get("name", self.accent),
                "options": accent_keys,
                "swatch_color": ACCENTS.get(self.accent, {}).get("color"),
            },
            {
                "id": "images_only",
                "label": "Nur Bilder laden",
                "type": "choice",
                "value": self.images_only,
                "display_value": "Aktiviert (Keine Videos)" if self.images_only else "Deaktiviert (Alle Medien)",
                "options": [False, True],
            },
            {
                "id": "autoplay_video",
                "label": "Video Autoplay",
                "type": "choice",
                "value": self.autoplay_video,
                "display_value": "Aktiviert" if self.autoplay_video else "Deaktiviert",
                "options": [True, False],
            },
            {
                "id": "autoplay_audio",
                "label": "Sound in Vorschau",
                "type": "choice",
                "value": self.autoplay_audio,
                "display_value": "Aktiviert" if self.autoplay_audio else "Deaktiviert",
                "options": [True, False],
            },
            {
                "id": "video_player_info",
                "label": "Videoplayer",
                "type": "action",
                "display_value": f"[{player_disp}]",
            },
            {
                "id": "promoted",
                "label": "Standard-Feed",
                "type": "choice",
                "value": self.promoted,
                "display_value": "Beliebt" if self.promoted == 1 else "Neu",
                "options": [1, 0],
            },
            {
                "id": "flags",
                "label": "Content Filter (Flags)",
                "type": "choice",
                "value": self.flags,
                "display_value": flag_display,
                "options": [opt[0] for opt in flags_options],
            },
            {
                "id": "scroll_speed",
                "label": "Scroll-Tempo",
                "type": "choice",
                "value": self.scroll_speed,
                "display_value": "Normal (45px)" if self.scroll_speed == "normal" else ("Schnell (85px)" if self.scroll_speed == "schnell" else "Turbo (150px)"),
                "options": scroll_keys,
            },
            {
                "id": "button_layout",
                "label": "Knopfbelegung",
                "type": "choice",
                "value": self.input_mgr.button_layout,
                "display_value": "Standard (A=Öffnen, B=Zurück)" if self.input_mgr.button_layout == "standard" else "Invertiert (B=Öffnen, A=Zurück)",
                "options": ["standard", "inverted"],
            },
            {
                "id": "button_test",
                "label": "Tasten-Test / Diagnose",
                "type": "action",
                "display_value": "[A: Starten]",
            },
            {
                "id": "clear_cache",
                "label": "Cache leeren",
                "type": "action",
                "display_value": "[A: Jetzt bereinigen]",
            },
            {
                "id": "version_info",
                "label": "Version",
                "type": "info",
                "display_value": f"v{VERSION}",
            },
            {
                "id": "save_exit",
                "label": "Zurück zum Grid",
                "type": "action",
                "display_value": "[B / A: Speichern & Zurück]",
            },
            {
                "id": "quit_app",
                "label": "App beenden",
                "type": "action",
                "display_value": "[A: Beenden]",
            },
        ]

    def _save_settings_and_return(self) -> None:
        """Persist current settings to config.json and return to grid."""
        old_flags = int(self.config.get("flags", 1))
        old_promoted = int(self.config.get("promoted", 1))
        old_images_only = bool(self.config.get("images_only", False))

        self.config["theme"] = self.theme
        self.config["accent"] = self.accent
        self.config["images_only"] = self.images_only
        self.config["autoplay_video"] = self.autoplay_video
        self.config["autoplay_audio"] = self.autoplay_audio
        self.config["promoted"] = self.promoted
        self.config["flags"] = self.flags
        self.config["scroll_speed"] = self.scroll_speed
        self.config["button_layout"] = self.button_layout
        save_config(self.config, self.config_path)
        self.set_toast("Einstellungen gespeichert!", COLOR_GREEN, duration=2.0)
        self.state = STATE_GRID

        # Reload feed if flags, promoted or images_only changed in settings
        if old_flags != self.flags or old_promoted != self.promoted or old_images_only != self.images_only:
            self.items = []
            self.last_api_item_id = None
            self.selected_idx = 0
            self.grid_scroll_row = 0
            self.fetch_feed(append=False)

    def _handle_settings_action(self, action: str) -> None:
        """Handle inputs in the settings view."""
        menu = self._build_settings_menu()
        total_items = len(menu)
        curr_item = menu[self.settings_idx]

        if action == ACTION_UP:
            self.settings_idx = (self.settings_idx - 1) % total_items
            return
        elif action == ACTION_DOWN:
            self.settings_idx = (self.settings_idx + 1) % total_items
            return

        # Left / Right: Cycle option values
        if action in (ACTION_LEFT, ACTION_RIGHT):
            if curr_item.get("type") == "choice":
                opts = curr_item["options"]
                curr_val = curr_item["value"]
                curr_i = opts.index(curr_val) if curr_val in opts else 0
                delta = -1 if action == ACTION_LEFT else 1
                new_val = opts[(curr_i + delta) % len(opts)]

                item_id = curr_item["id"]
                if item_id == "theme":
                    self.theme = new_val
                    self.ui.set_theme(self.theme, self.accent)
                elif item_id == "accent":
                    self.accent = new_val
                    self.ui.set_theme(self.theme, self.accent)
                elif item_id == "images_only":
                    self.images_only = bool(new_val)
                elif item_id == "autoplay_video":
                    self.autoplay_video = bool(new_val)
                elif item_id == "autoplay_audio":
                    self.autoplay_audio = bool(new_val)
                    self.inline_player.enable_audio = self.autoplay_audio
                elif item_id == "promoted":
                    self.promoted = int(new_val)
                elif item_id == "flags":
                    self.flags = int(new_val)
                    if not self.api.is_authenticated and (self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP)):
                        if not (self.flags & FLAG_SFW):
                            self.set_toast("Hinweis: Reines NSFW/NSFL erfordert Anmeldung!", COLOR_ORANGE, duration=2.5)
                        else:
                            self.set_toast("Hinweis: NSFW erfordert Anmeldung!", COLOR_ORANGE, duration=2.0)
                elif item_id == "scroll_speed":
                    self.scroll_speed = str(new_val)
                    self.scroll_step = 45 if self.scroll_speed == "normal" else (85 if self.scroll_speed == "schnell" else 150)
                elif item_id == "button_layout":
                    self.button_layout = str(new_val)
                    self.input_mgr.set_layout(self.button_layout)
                    self.video.button_layout = self.button_layout
                    disp = "Standard (A=Öffnen, B=Zurück)" if self.input_mgr.button_layout == "standard" else "Invertiert (B=Öffnen, A=Zurück)"
                    self.set_toast(f"Knöpfe: {disp}", COLOR_ORANGE, duration=1.5)
            return

        # Select (A)
        if action == ACTION_SELECT:
            item_id = curr_item["id"]
            if item_id == "account":
                if self.api.is_authenticated:
                    self.api.logout()
                    self.config["me_cookie"] = ""
                    self.config["av_cookie"] = ""
                    self.me_cookie = ""
                    self.av_cookie = ""
                    self.cache.set_cookie("", "")
                    self.video.set_cookie("", "")
                    self.inline_player.set_cookie("", "")
                    save_config(self.config, self.config_path)
                    self.set_toast("Erfolgreich abgemeldet.", COLOR_RED, duration=2.0)
                else:
                    self._start_login_flow()
                return
            elif item_id == "video_player_info":
                if self.video.has_player():
                    self.set_toast(f"Pfad: {self.video.player_path}", COLOR_GREEN, duration=3.0)
                elif self.inline_player.is_available:
                    self.set_toast(f"FFmpeg: {self.inline_player.ffmpeg_bin}", COLOR_GREEN, duration=3.0)
                else:
                    self.set_toast("Weder mpv noch ffmpeg gefunden!", COLOR_RED, duration=3.0)
                return
            elif item_id == "button_test":
                self.state = STATE_BUTTON_TEST
                self.input_mgr.clear_events()
                self.input_freeze_until = time.time() + 0.2
                return
            elif item_id == "clear_cache":
                count = self.cache.clear_all()
                self.set_toast(f"Cache geleert ({count} Dateien)!", COLOR_GREEN, duration=2.0)
                return
            elif item_id == "save_exit":
                self._save_settings_and_return()
                return
            elif item_id == "version_info":
                self.set_toast(f"pr0-retroconsole v{VERSION}", COLOR_ORANGE, duration=2.0)
                return
            elif item_id == "quit_app":
                self.config["theme"] = self.theme
                self.config["accent"] = self.accent
                self.config["images_only"] = self.images_only
                self.config["autoplay_video"] = self.autoplay_video
                self.config["autoplay_audio"] = self.autoplay_audio
                self.config["promoted"] = self.promoted
                self.config["flags"] = self.flags
                self.config["scroll_speed"] = self.scroll_speed
                self.config["button_layout"] = self.button_layout
                save_config(self.config, self.config_path)
                self.running = False
                return
            elif curr_item.get("type") == "choice":
                opts = curr_item["options"]
                curr_val = curr_item["value"]
                curr_i = opts.index(curr_val) if curr_val in opts else 0
                new_val = opts[(curr_i + 1) % len(opts)]

                item_id = curr_item["id"]
                if item_id == "theme":
                    self.theme = new_val
                    self.ui.set_theme(self.theme, self.accent)
                elif item_id == "accent":
                    self.accent = new_val
                    self.ui.set_theme(self.theme, self.accent)
                elif item_id == "images_only":
                    self.images_only = bool(new_val)
                elif item_id == "autoplay_video":
                    self.autoplay_video = bool(new_val)
                elif item_id == "autoplay_audio":
                    self.autoplay_audio = bool(new_val)
                    self.inline_player.enable_audio = self.autoplay_audio
                elif item_id == "promoted":
                    self.promoted = int(new_val)
                elif item_id == "flags":
                    self.flags = int(new_val)
                    if not self.api.is_authenticated and (self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP)):
                        if not (self.flags & FLAG_SFW):
                            self.set_toast("Hinweis: Reines NSFW/NSFL erfordert Anmeldung!", COLOR_ORANGE, duration=2.5)
                        else:
                            self.set_toast("Hinweis: NSFW erfordert Anmeldung!", COLOR_ORANGE, duration=2.0)
                elif item_id == "scroll_speed":
                    self.scroll_speed = str(new_val)
                    self.scroll_step = 45 if self.scroll_speed == "normal" else (85 if self.scroll_speed == "schnell" else 150)
                elif item_id == "button_layout":
                    self.button_layout = str(new_val)
                    self.input_mgr.set_layout(self.button_layout)
                    self.video.button_layout = self.button_layout
                    disp = "Standard (A=Öffnen, B=Zurück)" if self.input_mgr.button_layout == "standard" else "Invertiert (B=Öffnen, A=Zurück)"
                    self.set_toast(f"Knöpfe: {disp}", COLOR_ORANGE, duration=1.5)
                return

        # Back (B) or START to save & close
        if action in (ACTION_BACK, ACTION_SETTINGS):
            self._save_settings_and_return()
            return

    # -------------------------------------------------------------------------
    # Main Loop & Render Dispatch
    # -------------------------------------------------------------------------

    def _process_background_tasks(self) -> None:
        """Process completed tasks from the worker queue."""
        while True:
            try:
                task = self.task_queue.get_nowait()
            except queue.Empty:
                break

            status = task.get("status")
            task_type = task.get("type")

            if status == "success":
                result = task.get("result", {})
                if task_type in ("feed_fresh", "feed_append"):
                    raw_items = result.get("items", [])
                    err = result.get("error")
                    if err == "auth_required":
                        self.feed_error = "auth_required"
                        logger.info("Feed error: Authentication required for active flags=%d", self.flags)
                        if task_type == "feed_fresh" and not self.items:
                            self.set_toast("Anmeldung erforderlich für NSFW/NSFL!", COLOR_ORANGE, duration=3.0)
                    elif raw_items:
                        self.feed_error = None
                    else:
                        self.feed_error = err

                    self.at_end = result.get("atEnd", False)
                    if raw_items:
                        self.last_api_item_id = raw_items[-1]["id"]
                    elif task_type == "feed_fresh":
                        self.last_api_item_id = None

                    if self.images_only:
                        new_items = [it for it in raw_items if not Pr0API.is_video(it)]
                    else:
                        new_items = raw_items

                    if task_type == "feed_fresh":
                        self.items = new_items
                    else:
                        # Append unique items
                        existing_ids = {it["id"] for it in self.items}
                        for it in new_items:
                            if it["id"] not in existing_ids:
                                self.items.append(it)
                    self.is_fetching_feed = False
                    if self.items:
                        self._feed_retry_count = 0
                    logger.info("Feed updated: %d total items (atEnd=%s, images_only=%s)", len(self.items), self.at_end, self.images_only)
                    # Trigger background thumbnail preload for upcoming items
                    self.cache.preload_items(self.items, count=len(self.items))
                elif task_type == "post_info":
                    self.current_post_info = result
                    self.is_loading_info = False
                elif task_type in ("vote", "vote_comment"):
                    res = result.get("result", {})
                    logger.info("Vote cast result: %s", res)
                elif task_type == "post_comment":
                    p_id = result.get("post_id")
                    res = result.get("res", {})
                    if res.get("success"):
                        self.set_toast("Kommentar erfolgreich gesendet!", COLOR_GREEN, duration=2.5)
                        if p_id:
                            self.ui.clear_comment_cache(p_id)
                            self.fetch_post_info(p_id)
                    else:
                        err = res.get("error", "Fehler beim Senden")
                        self.set_toast(f"Fehler: {err}", COLOR_RED, duration=3.0)
            else:
                err = task.get("error", "Unknown error")
                logger.error("Task %s failed: %s", task_type, err)
                if task_type in ("feed_fresh", "feed_append"):
                    self.is_fetching_feed = False
                    if self.items:
                        self._feed_retry_count = 0
                    if not self.items and (not self.api.is_authenticated and (self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP)) and not (self.flags & FLAG_SFW)):
                        self.feed_error = "auth_required"
                        self.set_toast("Anmeldung erforderlich für NSFW/NSFL!", COLOR_ORANGE, duration=3.0)
                    else:
                        self.set_toast("Fehler beim Laden des Feeds!", COLOR_RED, duration=2.5)
                elif task_type == "post_info":
                    self.is_loading_info = False
                    self.set_toast("Fehler beim Laden der Kommentare!", COLOR_RED, duration=2.0)
                elif task_type == "vote_comment":
                    self.set_toast("Fehler beim Bewerten!", COLOR_RED, duration=2.0)
                elif task_type == "post_comment":
                    self.set_toast("Fehler beim Senden des Kommentars!", COLOR_RED, duration=2.5)

    def render(self) -> None:
        """Render current scene based on active state."""
        mode_label = "Beliebt" if self.promoted == 1 else "Neu"
        flags_label = Pr0API.get_flag_string(self.flags)
        toast_active = self.toast_msg if (self.toast_msg and time.time() < self.toast_time) else None

        # Periodically recalculate cache progress for the footer bar
        now = time.time()
        if now - self._last_progress_calc > 0.25 and self.items:
            self._last_progress_calc = now
            self._cached_progress = self.cache.get_progress(self.items)

        if self.state == STATE_GRID:
            # 1. Grid View
            self.ui.render_grid(
                self.items,
                self.selected_idx,
                self.cache,
                self.grid_scroll_row,
                header_focused=self.header_focus,
                is_loading=self.is_fetching_feed,
                is_authenticated=self.api.is_authenticated,
                flags=self.flags,
                feed_error=self.feed_error,
            )
            self.ui.render_header(
                mode_label=mode_label,
                flags_label=flags_label,
                current_idx=self.selected_idx,
                total_items=len(self.items),
                username=self.api.username,
                is_loading=self.is_fetching_feed,
                promoted=self.promoted,
                flags=self.flags,
                header_focused=self.header_focus,
                header_idx=self.header_idx,
            )
            if not self.items:
                requires_login = (not self.api.is_authenticated) and (
                    self.feed_error == "auth_required"
                    or bool(self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP) and not (self.flags & FLAG_SFW))
                )
                if requires_login:
                    footer_hints = [
                        ("START", "Setup / Login"),
                        ("A", "Anmelden"),
                        ("B", "Beenden"),
                    ]
                else:
                    footer_hints = [
                        ("A", "Neu laden"),
                        ("START", "Setup"),
                        ("B", "Beenden"),
                    ]
            elif self.header_focus:
                footer_hints = [
                    ("D-Pad", "Wählen"),
                    ("A", "An/Aus"),
                    ("Y", "Solo"),
                    ("Runter/B", "Grid"),
                    ("START", "Setup"),
                ]
            else:
                footer_hints = [
                    ("D-Pad", "Nav"),
                    ("Hoch", "Filter/Header"),
                    ("A", "Öffnen"),
                    ("L1/R1", "Filter"),
                    ("L2/R2", "Modus"),
                    ("START", "Setup"),
                ]
            self.ui.render_footer(
                hints=footer_hints,
                toast_message=toast_active,
                toast_color=self.toast_color,
                cache_progress=self._cached_progress,
            )

        elif self.state == STATE_SETTINGS:
            # 2. Settings View
            menu_items = self._build_settings_menu()
            self.ui.render_settings(
                menu_items=menu_items,
                selected_idx=self.settings_idx,
                toast_message=toast_active,
                toast_color=self.toast_color,
            )

        elif self.state == STATE_BUTTON_TEST:
            # 3. Gamepad Button Test & Diagnostics View
            layout_disp = "Standard (A=Öffnen, B=Zurück)" if self.input_mgr.button_layout == "standard" else "Invertiert (B=Öffnen, A=Zurück)"
            self.ui.render_button_test(
                diag=self.input_mgr.last_diag,
                layout_name=layout_disp,
                toast_message=toast_active,
                toast_color=self.toast_color,
            )

        elif self.state == STATE_POST and self.items:
            # 3. Single Post View (Continuous vertical scroll: media -> meta -> tags -> comments)
            item = self.items[self.selected_idx]
            self.max_post_scroll, self.post_focus_targets = self.ui.render_post(
                item=item,
                tags=self.current_post_info.get("tags", []),
                comments=self.current_post_info.get("comments", []),
                cache_manager=self.cache,
                scroll_y=self.post_scroll_y,
                video_player_available=self.video.has_player(),
                is_loading_info=self.is_loading_info,
                inline_frame=self.inline_player.get_current_frame(),
                inline_progress=self.inline_player.get_progress(),
                focused_idx=self.post_focus_idx,
            )

            self.ui.render_header(
                mode_label=mode_label,
                flags_label=flags_label,
                current_idx=self.selected_idx,
                total_items=len(self.items),
                username=self.api.username,
                is_loading=self.is_fetching_feed,
                promoted=self.promoted,
                flags=self.flags,
            )

            # Modal or Keyboard Overlay
            if self.comment_modal_open and self.comment_modal_target:
                self.ui.render_comment_modal(
                    comment=self.comment_modal_target,
                    selected_idx=self.comment_modal_idx,
                )
                hints = [
                    ("▲/▼", "Auswahl"),
                    ("A", "Auswählen"),
                    ("Y", "+1"),
                    ("X", "-1"),
                    ("B", "Abbrechen"),
                ]
            elif self.virtual_keyboard:
                self.ui.render_keyboard_modal(self.virtual_keyboard)
                hints = [
                    ("D-Pad", "Navigieren"),
                    ("A", "Tippen"),
                    ("X", "Shift"),
                    ("Y", "Löschen"),
                    ("B", "Abbrechen"),
                ]
            else:
                is_vid = Pr0API.is_video(item)
                hints = [
                    ("◄/►", "Post"),
                    ("▲/▼", "Fokus"),
                ]
                if self.post_focus_idx == 0:
                    if is_vid:
                        hints.append(("A", "Vollbild"))
                    hints.extend([
                        ("Y/R1", "+1"),
                        ("X/L1", "-1"),
                    ])
                elif self.post_focus_idx == 1:
                    hints.append(("A", "Kommentieren"))
                else:
                    hints.extend([
                        ("A", "Aktionen"),
                        ("Y/R1", "+1"),
                        ("X/L1", "-1"),
                    ])

                hints.extend([
                    ("B", "Grid"),
                    ("START", "Setup"),
                ])

            self.ui.render_footer(
                hints=hints,
                toast_message=toast_active,
                toast_color=self.toast_color,
                cache_progress=self._cached_progress,
            )

        elif self.state == STATE_LOGIN:
            self.ui.render_login(
                mode=self.login_mode,
                url=self.auth_url,
                qr_surface=self.qr_surface,
                direct_fields={
                    "username": self.direct_username,
                    "password": self.direct_password,
                    "captcha_code": self.direct_captcha_code,
                    "captcha_surface": self.direct_captcha_surface,
                    "selected_field_idx": self.direct_sel_idx,
                },
                active_keyboard=self.virtual_keyboard,
                status_message=self.login_status_msg,
                status_color=self.login_status_color,
                toast_message=toast_active,
                toast_color=self.toast_color,
            )

        pygame.display.flip()

    def run(self) -> None:
        """Main game loop."""
        logger.info("Starting pr0-retroconsole main loop...")
        self.fetch_feed(append=False)

        while self.running:
            # Check if login completed asynchronously (e.g. from companion phone server or background thread)
            if self.login_success_pending:
                uname, cookie = self.login_success_pending
                self.login_success_pending = None
                self.config["me_cookie"] = cookie
                self.me_cookie = cookie
                self.api.update_cookie(cookie)
                self.av_cookie = self.api.av_cookie or ""
                self.config["av_cookie"] = self.av_cookie
                self.cache.set_cookie(self.me_cookie, self.av_cookie)
                self.video.set_cookie(self.me_cookie, self.av_cookie)
                self.inline_player.set_cookie(self.me_cookie, self.av_cookie)
                save_config(self.config, self.config_path)
                self._stop_login_flow()
                self.set_toast(f"Eingeloggt als {uname}!", COLOR_GREEN, duration=3.0)
                self.state = STATE_GRID

            self._process_background_tasks()

            # Auto-retry initial feed load if empty and not currently fetching (e.g. WiFi connects a few seconds after boot)
            is_auth_needed = (not self.api.is_authenticated) and (
                self.feed_error == "auth_required"
                or bool(self.flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP) and not (self.flags & FLAG_SFW))
            )
            if not self.items and not self.is_fetching_feed and self.state == STATE_GRID and self._feed_retry_count < 6 and not is_auth_needed:
                now = time.time()
                if now - self._last_feed_retry > 3.0:
                    self._last_feed_retry = now
                    self._feed_retry_count += 1
                    logger.info("Auto-retrying feed fetch (attempt %d/6)...", self._feed_retry_count)
                    self.fetch_feed(append=False)

            completed_urls = self.cache.process_completed()
            if completed_urls and self.state == STATE_POST and self.items and self.autoplay_video:
                curr_item = self.items[self.selected_idx]
                if Pr0API.is_video(curr_item):
                    m_url = Pr0API.get_media_url(curr_item)
                    if m_url in completed_urls and self.inline_player._active_url != self.cache.get_local_path(m_url):
                        self._update_inline_video()
            self.handle_actions()
            self.render()
            self.clock.tick(self.fps)

        # Cleanup
        logger.info("Shutting down pr0-retroconsole...")
        self._stop_login_flow()
        self.inline_player.stop()
        self.cache.stop()
        pygame.quit()


def parse_args() -> argparse.Namespace:
    """Parse command line flags."""
    parser = argparse.ArgumentParser(description="pr0-retroconsole: Handheld pr0gramm Client")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--promoted", type=int, choices=[0, 1], help="Feed mode: 1=Beliebt, 0=Neu")
    parser.add_argument("--flags", type=int, help="Bitmask flags (1=SFW, 2=NSFW, 4=NSFL, 8=NSFP)")
    parser.add_argument("--resolution", help="Display resolution, e.g. 640x480, 1280x720, or auto")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_file = Path(args.config)
    config = load_config(config_file)

    if args.promoted is not None:
        config["promoted"] = args.promoted
    if args.flags is not None:
        config["flags"] = args.flags
    if args.resolution is not None:
        config["resolution"] = args.resolution

    app = Pr0App(config, config_file)
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
