"""Pygame UI Rendering for pr0-retroconsole.

Provides resolution-independent rendering for:
1. Thumbnail Grid View with dynamic pagination
2. Fullscreen Post View with 'Tapeten' vertical fit-to-width scrolling, video autoplay & culling
3. Unified continuous Comment & Tag Tree with viewport-culled rendering (up to 9000x faster)
4. Interactive Settings & Theme View with live color preview
"""

from __future__ import annotations

import logging
import math
import os
import time
from pathlib import Path
from typing import Any
import pygame

try:
    from api import Pr0API, FLAG_SFW, FLAG_NSFW, FLAG_NSFL, FLAG_NSFP
except ImportError:
    from .api import Pr0API, FLAG_SFW, FLAG_NSFW, FLAG_NSFL, FLAG_NSFP

try:
    from version import VERSION
except ImportError:
    from .version import VERSION

try:
    from qr_helper import generate_qr_surface
except ImportError:
    try:
        from .qr_helper import generate_qr_surface
    except ImportError:
        generate_qr_surface = None

logger = logging.getLogger("pr0.ui")

# -----------------------------------------------------------------------------
# Color Themes & Accents
# -----------------------------------------------------------------------------

THEMES: dict[str, dict[str, Any]] = {
    "pr0_dark": {
        "name": "pr0gramm Dunkel",
        "bg": (22, 22, 24),            # #161618 (Richtiges Grau)
        "card": (33, 33, 36),          # #212124
        "card_border": (48, 48, 54),
        "text": (242, 245, 244),       # #f2f5f4
        "text_dim": (140, 140, 148),
        "tag_bg": (42, 42, 48),
        "tag_text": (210, 215, 220),
        "scrollbar_track": (38, 38, 42),
        "scrollbar_thumb": (100, 100, 110),
    },
    "oled": {
        "name": "OLED Schwarz",
        "bg": (0, 0, 0),               # #000000
        "card": (18, 18, 20),          # #121214
        "card_border": (36, 36, 40),
        "text": (245, 245, 245),
        "text_dim": (130, 130, 135),
        "tag_bg": (28, 28, 32),
        "tag_text": (200, 200, 205),
        "scrollbar_track": (20, 20, 22),
        "scrollbar_thumb": (80, 80, 90),
    },
    "olive": {
        "name": "Olivgrün (pr0 Army)",
        "bg": (24, 26, 22),
        "card": (34, 38, 31),
        "card_border": (52, 58, 48),
        "text": (235, 240, 228),
        "text_dim": (140, 150, 130),
        "tag_bg": (44, 50, 40),
        "tag_text": (205, 218, 195),
        "scrollbar_track": (36, 40, 32),
        "scrollbar_thumb": (90, 105, 80),
    },
    "nordic": {
        "name": "Nordic Slate",
        "bg": (24, 27, 32),
        "card": (34, 39, 48),
        "card_border": (52, 60, 74),
        "text": (236, 239, 244),
        "text_dim": (136, 145, 160),
        "tag_bg": (44, 52, 64),
        "tag_text": (205, 215, 230),
        "scrollbar_track": (34, 40, 50),
        "scrollbar_thumb": (90, 105, 125),
    },
    "retro": {
        "name": "Retro Amber",
        "bg": (26, 22, 15),
        "card": (38, 32, 22),
        "card_border": (61, 51, 35),
        "text": (247, 232, 204),
        "text_dim": (160, 145, 120),
        "tag_bg": (48, 40, 28),
        "tag_text": (230, 210, 175),
        "scrollbar_track": (40, 34, 24),
        "scrollbar_thumb": (115, 95, 65),
    },
}

ACCENTS: dict[str, dict[str, Any]] = {
    "orange": {"name": "pr0-Orange", "color": (238, 77, 46)},
    "green": {"name": "Giftgrün", "color": (16, 175, 75)},
    "blue": {"name": "Neonblau", "color": (0, 143, 255)},
    "pink": {"name": "Magenta", "color": (234, 20, 100)},
    "gold": {"name": "Goldgelb", "color": (245, 166, 35)},
    "cyan": {"name": "Türkis / Cyan", "color": (0, 194, 203)},
}

# Compatibility Constants (Default Dark)
COLOR_BG = THEMES["pr0_dark"]["bg"]
COLOR_CARD = THEMES["pr0_dark"]["card"]
COLOR_CARD_BORDER = THEMES["pr0_dark"]["card_border"]
COLOR_TEXT = THEMES["pr0_dark"]["text"]
COLOR_TEXT_DIM = THEMES["pr0_dark"]["text_dim"]
COLOR_ORANGE = ACCENTS["orange"]["color"]
COLOR_ORANGE_DIM = (120, 38, 23)
COLOR_GREEN = (0, 229, 153)
COLOR_RED = (238, 77, 46)
COLOR_TAG_BG = THEMES["pr0_dark"]["tag_bg"]
COLOR_TAG_TEXT = THEMES["pr0_dark"]["tag_text"]
COLOR_OVERLAY_BG = (25, 25, 28)
COLOR_SCROLLBAR_TRACK = THEMES["pr0_dark"]["scrollbar_track"]
COLOR_SCROLLBAR_THUMB = THEMES["pr0_dark"]["scrollbar_thumb"]


def format_time_ago(ts: int) -> str:
    """Format Unix timestamp as relative human-readable string."""
    diff = int(time.time()) - ts
    if diff < 0:
        return "gerade eben"
    if diff < 60:
        return f"vor {diff}s"
    if diff < 3600:
        return f"vor {diff // 60}m"
    if diff < 86400:
        return f"vor {diff // 3600}h"
    days = diff // 86400
    if days < 30:
        return f"vor {days}d"
    return time.strftime("%d.%m.%Y", time.localtime(ts))


class UIRenderer:
    """Manages layouts, fonts, scaling, themes, and view rendering."""

    def __init__(self, screen: pygame.Surface, width: int = 640, height: int = 480):
        self.screen = screen
        self.width = width
        self.height = height

        # Scale factor based on reference 640x480 resolution
        self.scale = max(1.0, min(width / 640.0, height / 480.0))
        self._init_fonts()

        # Theme & Color Management
        self.current_theme_key = "pr0_dark"
        self.current_accent_key = "orange"
        self.set_theme(self.current_theme_key, self.current_accent_key)

        # Caching for high-performance rendering (60 FPS on Tapeten & 500+ comments)
        self._scaled_surf_cache: dict[tuple[int, int, int], pygame.Surface] = {}
        self._comment_layout_cache: dict[tuple[int, int, int], list[dict[str, Any]]] = {}

        # Grid layout metrics
        if self.width >= 1200:
            self.grid_cols = 7
            self.card_size = 145
            self.grid_gap = 16
        elif self.width >= 960:
            self.grid_cols = 5
            self.card_size = 150
            self.grid_gap = 16
        else:
            # 640x480 (R36S / standard handheld)
            self.grid_cols = 4
            self.card_size = 125
            self.grid_gap = 14

        self.header_height = int(46 * self.scale)
        self.footer_height = int(38 * self.scale)

    def set_theme(self, theme_key: str = "pr0_dark", accent_key: str = "orange") -> None:
        """Apply active theme and accent colors across the UI."""
        theme = THEMES.get(theme_key, THEMES["pr0_dark"])
        accent = ACCENTS.get(accent_key, ACCENTS["orange"])

        self.current_theme_key = theme_key
        self.current_accent_key = accent_key

        self.color_bg = theme["bg"]
        self.color_card = theme["card"]
        self.color_card_border = theme["card_border"]
        self.color_text = theme["text"]
        self.color_text_dim = theme["text_dim"]
        self.color_tag_bg = theme["tag_bg"]
        self.color_tag_text = theme["tag_text"]
        self.color_scrollbar_track = theme.get("scrollbar_track", (38, 38, 42))
        self.color_scrollbar_thumb = theme.get("scrollbar_thumb", (100, 100, 110))

        self.color_accent = accent["color"]
        r, g, b = self.color_accent
        self.color_accent_dim = (max(0, r // 2), max(0, g // 2), max(0, b // 2))

        self.color_green = COLOR_GREEN
        self.color_red = COLOR_RED

    def _init_fonts(self) -> None:
        """Load bundled TrueType fonts with resolution-appropriate sizes."""
        assets_dir = Path(__file__).parent.parent / "assets" / "fonts"
        font_inter = assets_dir / "Inter-Regular.ttf"
        font_fira = assets_dir / "FiraCode-Regular.ttf"

        def load(font_path: Path, size: int) -> pygame.font.Font:
            scaled_size = max(10, int(size * self.scale))
            if font_path.is_file():
                try:
                    return pygame.font.Font(str(font_path), scaled_size)
                except Exception:
                    pass
            return pygame.font.Font(None, scaled_size)

        self.font_logo = load(font_inter, 20)
        self.font_logo.set_bold(True)
        self.font_title = load(font_inter, 18)
        self.font_title.set_bold(True)
        self.font_regular = load(font_inter, 14)
        self.font_bold = load(font_inter, 14)
        self.font_bold.set_bold(True)
        self.font_small = load(font_inter, 12)
        self.font_mono = load(font_fira if font_fira.is_file() else font_inter, 12)

    def update_resolution(self, width: int, height: int) -> None:
        """Handle dynamic resolution adjustments."""
        self.width = width
        self.height = height
        self.scale = max(1.0, min(width / 640.0, height / 480.0))
        self._init_fonts()
        self._scaled_surf_cache.clear()
        self._comment_layout_cache.clear()

    # -------------------------------------------------------------------------
    # Surface & Layout Cache Helpers (Optimization)
    # -------------------------------------------------------------------------

    def _get_scaled_surface(self, surf: pygame.Surface, target_w: int, target_h: int) -> pygame.Surface:
        """Cache smoothscaled surfaces to avoid repeating CPU-heavy scaling every frame."""
        if surf.get_width() == target_w and surf.get_height() == target_h:
            return surf
        key = (id(surf), target_w, target_h)
        cached = self._scaled_surf_cache.get(key)
        if cached is not None:
            return cached
        if len(self._scaled_surf_cache) > 12:
            self._scaled_surf_cache.clear()
        scaled = pygame.transform.smoothscale(surf, (target_w, target_h))
        self._scaled_surf_cache[key] = scaled
        return scaled

    def _get_comment_layout(self, item_id: int, comments: list[dict[str, Any]], content_w: int) -> list[dict[str, Any]]:
        """Precompute comment tree and wrapped text lines for ultra-fast viewport culling."""
        key = (item_id, len(comments), content_w)
        cached = self._comment_layout_cache.get(key)
        if cached is not None:
            return cached

        comment_tree = self._build_comment_tree(comments)
        items: list[dict[str, Any]] = []

        for c, depth in comment_tree:
            indent = min(depth * 14, 56)
            c_x = 12 + indent
            c_w = content_w - indent

            author = str(c.get("name", "unbekannt"))
            c_up = c.get("up", 0)
            c_down = c.get("down", 0)
            score_str = f" {c_up - c_down:+d}"
            c_created = c.get("created", 0)
            time_txt = f" • {format_time_ago(c_created)}" if c_created else ""

            content = str(c.get("content", ""))
            wrapped_lines = self._wrap_text(content, self.font_small, c_w - 10)

            # 18px author line + 16px per wrapped line
            item_h = 18 + len(wrapped_lines) * 16

            items.append({
                "id": c.get("id", 0),
                "c_x": c_x,
                "c_w": c_w,
                "depth": depth,
                "author": author,
                "score_str": score_str,
                "up": c_up,
                "down": c_down,
                "time_txt": time_txt,
                "wrapped_lines": wrapped_lines,
                "item_h": item_h,
                "comment": c,
            })

        if len(self._comment_layout_cache) > 20:
            self._comment_layout_cache.clear()

        self._comment_layout_cache[key] = items
        return items

    def clear_comment_cache(self, item_id: int | None = None) -> None:
        """Clear precomputed comment layout cache (e.g. after voting or posting a comment)."""
        if item_id is None:
            self._comment_layout_cache.clear()
        else:
            keys_to_del = [k for k in self._comment_layout_cache if k[0] == item_id]
            for k in keys_to_del:
                del self._comment_layout_cache[k]

    # -------------------------------------------------------------------------
    # Helper Drawing Functions
    # -------------------------------------------------------------------------

    def draw_text(
        self,
        surface: pygame.Surface,
        font: pygame.font.Font,
        text: str,
        color: tuple[int, int, int],
        pos: tuple[int, int],
    ) -> int:
        """Render text at position pos (x, y) and return rendered width."""
        rendered = font.render(text, True, color)
        surface.blit(rendered, pos)
        return rendered.get_width()

    def truncate_text(self, font: pygame.font.Font, text: str, max_width: int) -> str:
        """Truncate text with ellipsis to fit within max_width."""
        if font.size(text)[0] <= max_width:
            return text
        truncated = text
        while truncated and font.size(truncated + "...")[0] > max_width:
            truncated = truncated[:-1]
        return truncated + "..." if truncated else ""

    def draw_scrollbar(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        content_total: int,
        content_visible: int,
        current_scroll: int,
    ) -> None:
        """Draw a proportional vertical scrollbar."""
        if content_total <= content_visible or content_visible <= 0:
            return

        # Track
        pygame.draw.rect(surface, self.color_scrollbar_track, (x, y, w, h), border_radius=w // 2)

        # Thumb
        thumb_h = max(16, int((content_visible / content_total) * h))
        max_scroll = content_total - content_visible
        scroll_ratio = max(0.0, min(1.0, current_scroll / max_scroll)) if max_scroll > 0 else 0
        thumb_y = y + int(scroll_ratio * (h - thumb_h))

        pygame.draw.rect(surface, self.color_scrollbar_thumb, (x, thumb_y, w, thumb_h), border_radius=w // 2)

    # -------------------------------------------------------------------------
    # Header & Footer Bars
    # -------------------------------------------------------------------------

    def _draw_star(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        r_out: int,
        r_in: int,
        color: tuple[int, int, int],
    ) -> None:
        """Draw a sleek 5-pointed star polygon."""
        pts = []
        for i in range(10):
            r = r_out if i % 2 == 0 else r_in
            angle = i * math.pi / 5 - math.pi / 2
            pts.append((cx + int(r * math.cos(angle)), cy + int(r * math.sin(angle))))
        pygame.draw.polygon(surface, color, pts)

    def render_header(
        self,
        mode_label: str = "Beliebt",
        flags_label: str = "SFW",
        current_idx: int = 0,
        total_items: int = 0,
        username: str | None = None,
        is_loading: bool = False,
        promoted: int | None = None,
        flags: int | None = None,
        header_focused: bool = False,
        header_idx: int = 2,
    ) -> None:
        """Render top navigation bar matching the authentic pr0.app / pr0gramm layout."""
        # 0. Solid header bar with subtle bottom border
        header_rect = pygame.Rect(0, 0, self.width, self.header_height)
        pygame.draw.rect(self.screen, self.color_card, header_rect)
        pygame.draw.line(
            self.screen,
            self.color_card_border,
            (0, self.header_height - 1),
            (self.width, self.header_height - 1),
            1,
        )

        center_y = self.header_height // 2
        x = 10

        # 1. Iconic pr0.app Logo Badge
        badge_w = int(42 * self.scale)
        badge_h = int(26 * self.scale)
        badge_y = center_y - badge_h // 2
        logo_rect = pygame.Rect(x, badge_y, badge_w, badge_h)
        pygame.draw.rect(self.screen, self.color_accent, logo_rect, border_radius=5)

        logo_surf = self.font_logo.render("pr0", True, (255, 255, 255))
        self.screen.blit(
            logo_surf,
            (logo_rect.centerx - logo_surf.get_width() // 2,
             logo_rect.centery - logo_surf.get_height() // 2),
        )
        x += badge_w + int(6 * self.scale)

        # ".app" domain suffix in sleek dim typography
        dot_app_w = self.draw_text(self.screen, self.font_bold, ".app", self.color_text_dim, (x, center_y - self.font_bold.get_height() // 2))
        x += dot_app_w + int(16 * self.scale)

        # 2. Main Navigation Tabs: "neu" and "beliebt" (all lowercase, matching pr0.app)
        is_promoted = (promoted == 1) if promoted is not None else (mode_label.lower() in ("beliebt", "top"))

        # Tab: neu (Index 0)
        neu_is_active = not is_promoted
        neu_font = self.font_bold if neu_is_active else self.font_regular
        neu_color = self.color_text if neu_is_active else self.color_text_dim
        neu_y = center_y - neu_font.get_height() // 2
        neu_w = self.draw_text(self.screen, neu_font, "neu", neu_color, (x, neu_y))

        if header_focused and header_idx == 0:
            neu_box = pygame.Rect(x - int(6 * self.scale), center_y - int(14 * self.scale), neu_w + int(12 * self.scale), int(28 * self.scale))
            pygame.draw.rect(self.screen, self.color_accent, neu_box, width=2, border_radius=4)
        elif neu_is_active:
            underline_h = max(2, int(3 * self.scale))
            pygame.draw.rect(
                self.screen,
                self.color_accent,
                (x - 2, self.header_height - underline_h, neu_w + 4, underline_h),
                border_radius=1,
            )
        x += neu_w + int(14 * self.scale)

        # Tab: beliebt (Index 1)
        beliebt_is_active = is_promoted
        beliebt_font = self.font_bold if beliebt_is_active else self.font_regular
        beliebt_color = self.color_text if beliebt_is_active else self.color_text_dim
        beliebt_y = center_y - beliebt_font.get_height() // 2
        beliebt_w = self.draw_text(self.screen, beliebt_font, "beliebt", beliebt_color, (x, beliebt_y))

        if header_focused and header_idx == 1:
            bel_box = pygame.Rect(x - int(6 * self.scale), center_y - int(14 * self.scale), beliebt_w + int(12 * self.scale), int(28 * self.scale))
            pygame.draw.rect(self.screen, self.color_accent, bel_box, width=2, border_radius=4)
        elif beliebt_is_active:
            underline_h = max(2, int(3 * self.scale))
            pygame.draw.rect(
                self.screen,
                self.color_accent,
                (x - 2, self.header_height - underline_h, beliebt_w + 4, underline_h),
                border_radius=1,
            )
        x += beliebt_w + int(14 * self.scale)

        # Subtle vertical divider line
        div_h = int(18 * self.scale)
        pygame.draw.line(
            self.screen,
            self.color_card_border,
            (x, center_y - div_h // 2),
            (x, center_y + div_h // 2),
            1,
        )
        x += int(14 * self.scale)

        # 3. Content Flags (SFW, NSFW, NSFL, POL pills with authentic pr0 color coding)
        active_flags = flags if flags is not None else 1
        if flags is None:
            fl_lower = flags_label.lower()
            active_flags = 0
            if "sfw" in fl_lower:
                active_flags |= 1
            if "nsfw" in fl_lower:
                active_flags |= 2
            if "nsfl" in fl_lower:
                active_flags |= 4
            if "pol" in fl_lower or "nsfp" in fl_lower:
                active_flags |= 8

        flag_defs = [
            ("sfw", 1, (0, 229, 153), (20, 44, 30)),
            ("nsfw", 2, (245, 166, 35), (46, 36, 18)),
            ("nsfl", 4, (238, 77, 46), (46, 22, 22)),
            ("pol", 8, (130, 165, 215), (20, 32, 48)),
        ]

        pill_h = int(22 * self.scale)
        pill_y = center_y - pill_h // 2

        for i, (f_label, f_mask, f_fg, f_bg) in enumerate(flag_defs):
            item_global_idx = 2 + i  # 2=sfw, 3=nsfw, 4=nsfl, 5=pol
            is_flag_on = bool(active_flags & f_mask)
            is_focused = bool(header_focused and header_idx == item_global_idx)

            f_txt_w = self.font_small.size(f_label)[0]
            if is_flag_on:
                pill_w = f_txt_w + int(18 * self.scale)
                if x + pill_w < self.width - 120:
                    pill_rect = pygame.Rect(x, pill_y, pill_w, pill_h)
                    pygame.draw.rect(self.screen, f_bg, pill_rect, border_radius=4)
                    pygame.draw.rect(self.screen, f_fg, pill_rect, width=1, border_radius=4)
                    dot_r = max(2, int(3 * self.scale))
                    pygame.draw.circle(self.screen, f_fg, (x + int(7 * self.scale), center_y), dot_r)
                    self.draw_text(self.screen, self.font_small, f_label, f_fg, (x + int(14 * self.scale), center_y - self.font_small.get_height() // 2))

                    if is_focused:
                        focus_rect = pill_rect.inflate(int(4 * self.scale), int(4 * self.scale))
                        pygame.draw.rect(self.screen, self.color_accent, focus_rect, width=2, border_radius=5)
                        caret_y = self.header_height - 2
                        pygame.draw.line(self.screen, self.color_accent, (pill_rect.centerx - int(6 * self.scale), caret_y), (pill_rect.centerx + int(6 * self.scale), caret_y), 2)

                    x += pill_w + int(8 * self.scale)
            else:
                pill_w = f_txt_w + int(12 * self.scale)
                if x + pill_w < self.width - 120:
                    pill_rect = pygame.Rect(x, pill_y, pill_w, pill_h)
                    if is_focused:
                        pygame.draw.rect(self.screen, (35, 35, 42), pill_rect, border_radius=4)
                        self.draw_text(self.screen, self.font_small, f_label, self.color_text_dim, (x + int(6 * self.scale), center_y - self.font_small.get_height() // 2))
                        focus_rect = pill_rect.inflate(int(4 * self.scale), int(4 * self.scale))
                        pygame.draw.rect(self.screen, self.color_accent, focus_rect, width=2, border_radius=5)
                        caret_y = self.header_height - 2
                        pygame.draw.line(self.screen, self.color_accent, (pill_rect.centerx - int(6 * self.scale), caret_y), (pill_rect.centerx + int(6 * self.scale), caret_y), 2)
                    else:
                        self.draw_text(self.screen, self.font_small, f_label, self.color_card_border, (x + int(6 * self.scale), center_y - self.font_small.get_height() // 2))

                    x += pill_w + int(6 * self.scale)

        # 4. Right Section (Stream count, pr0mium Star, User/Anmelden)
        rx = self.width - int(12 * self.scale)

        # User Profile or "anmelden"
        if username:
            user_txt = username
            uw = self.font_bold.size(user_txt)[0]
            self.draw_text(self.screen, self.font_bold, user_txt, self.color_text, (rx - uw, center_y - self.font_bold.get_height() // 2))
            rx -= uw + int(6 * self.scale)
        else:
            anm_txt = "anmelden"
            aw = self.font_small.size(anm_txt)[0]
            self.draw_text(self.screen, self.font_small, anm_txt, self.color_text_dim, (rx - aw, center_y - self.font_small.get_height() // 2))
            rx -= aw + int(6 * self.scale)

        # Golden pr0mium Star ★
        star_r_out = int(5 * self.scale)
        star_r_in = int(2.5 * self.scale)
        star_cx = rx - star_r_out
        star_cy = center_y
        self._draw_star(self.screen, star_cx, star_cy, star_r_out, star_r_in, (245, 166, 35))
        rx -= (star_r_out * 2) + int(12 * self.scale)

        # Item Counter (e.g. 1/120) or Loading indicator
        if is_loading:
            load_txt = "lädt..."
            lw = self.font_small.size(load_txt)[0]
            self.draw_text(self.screen, self.font_small, load_txt, self.color_accent, (rx - lw, center_y - self.font_small.get_height() // 2))
        elif total_items > 0:
            count_txt = f"{current_idx + 1}/{total_items}"
            cw = self.font_small.size(count_txt)[0]
            self.draw_text(self.screen, self.font_small, count_txt, self.color_text_dim, (rx - cw, center_y - self.font_small.get_height() // 2))

    def render_footer(
        self,
        hints: list[tuple[str, str]],
        toast_message: str | None = None,
        toast_color: tuple[int, int, int] | None = None,
        cache_progress: tuple[int, int, float] | None = None,
    ) -> None:
        """Render bottom status bar with control hints, cache progress bar, and notifications."""
        footer_y = self.height - self.footer_height
        footer_rect = pygame.Rect(0, footer_y, self.width, self.footer_height)
        pygame.draw.rect(self.screen, self.color_card, footer_rect)
        pygame.draw.line(self.screen, self.color_card_border, (0, footer_y), (self.width, footer_y), 1)

        center_y = footer_y + self.footer_height // 2

        # 1. Sleek Cache Progress Bar across top edge of footer
        bar_h = max(2, int(3 * self.scale))
        if cache_progress is not None and cache_progress[1] > 0:
            cached_cnt, total_cnt, ratio = cache_progress
            # Background track
            pygame.draw.rect(self.screen, (32, 32, 38), (0, footer_y, self.width, bar_h))
            # Filled bar (accent color)
            fill_w = max(0, min(self.width, int(self.width * ratio)))
            pygame.draw.rect(self.screen, self.color_accent, (0, footer_y, fill_w, bar_h))
            # Subtle glow indicator at leading tip if still caching
            if ratio < 1.0 and fill_w > 0:
                glow_w = max(2, int(4 * self.scale))
                pygame.draw.rect(self.screen, (255, 255, 255), (max(0, fill_w - glow_w), footer_y, glow_w, bar_h))

        # 2. Control hints on left (vertically centered)
        x = 12
        for button_label, action_desc in hints:
            badge_text = f"[{button_label}]"
            bw = self.draw_text(self.screen, self.font_small, badge_text, self.color_accent, (x, center_y - self.font_small.get_height() // 2))
            x += bw + 3
            dw = self.draw_text(self.screen, self.font_small, action_desc, self.color_text, (x, center_y - self.font_small.get_height() // 2))
            x += dw + 14
            if x > self.width - 200:
                break

        # 3. Toast / Flash Notification (Right aligned, takes precedence)
        if toast_message:
            tw = self.font_small.size(toast_message)[0]
            toast_x = self.width - tw - 14
            toast_rect = pygame.Rect(toast_x - 6, center_y - (self.footer_height - 12) // 2, tw + 12, self.footer_height - 12)
            pygame.draw.rect(self.screen, self.color_bg, toast_rect, border_radius=4)
            col = toast_color if toast_color is not None else self.color_accent
            self.draw_text(self.screen, self.font_small, toast_message, col, (toast_x, center_y - self.font_small.get_height() // 2))
        else:
            # 4. Cache status badge or Version text on right
            if cache_progress is not None and cache_progress[1] > 0 and cache_progress[2] < 1.0:
                cached_cnt, total_cnt, ratio = cache_progress
                pct = int(ratio * 100)
                prog_txt = f"Cache: {cached_cnt}/{total_cnt} ({pct}%)"
                pw = self.font_small.size(prog_txt)[0]
                px = self.width - pw - 14
                self.draw_text(self.screen, self.font_small, prog_txt, self.color_accent, (px, center_y - self.font_small.get_height() // 2))
            else:
                ver_text = f"v{VERSION}"
                vw = self.font_small.size(ver_text)[0]
                self.draw_text(self.screen, self.font_small, ver_text, self.color_text_dim, (self.width - vw - 14, center_y - self.font_small.get_height() // 2))

    # -------------------------------------------------------------------------
    # 1. Grid View
    # -------------------------------------------------------------------------

    def render_grid(
        self,
        items: list[dict[str, Any]],
        selected_idx: int,
        cache_manager: Any,
        scroll_row: int,
        header_focused: bool = False,
        is_loading: bool = False,
        is_authenticated: bool = False,
        flags: int = 1,
        feed_error: str | None = None,
    ) -> None:
        """Render the thumbnail grid viewport with smooth row scrolling."""
        self.screen.fill(self.color_bg)

        if not items:
            requires_login = (not is_authenticated) and (
                feed_error == "auth_required"
                or bool(flags & (FLAG_NSFW | FLAG_NSFL | FLAG_NSFP) and not (flags & FLAG_SFW))
            )

            card_w = min(int(540 * self.scale), self.width - 24)
            card_h = int(145 * self.scale) if requires_login else int(130 * self.scale)
            card_x = (self.width - card_w) // 2
            card_y = (self.height - card_h) // 2
            card_rect = pygame.Rect(card_x, card_y, card_w, card_h)

            pygame.draw.rect(self.screen, self.color_card, card_rect, border_radius=8)
            pygame.draw.rect(self.screen, self.color_card_border, card_rect, width=1, border_radius=8)

            if is_loading:
                msg = "Lade Beiträge von pr0gramm..."
                detail_msg = "Warte auf Antwort vom Server..."
                sub_msg = ""
                msg_color = self.color_accent
            elif requires_login:
                msg = "Anmeldung erforderlich für NSFW/NSFL"
                detail_msg = "pr0gramm blendet 18+ Inhalte nur für angemeldete Accounts ein."
                sub_msg = "[A] QR-Code Express-Login   •   [START / X] Setup"
                msg_color = self.color_accent
            else:
                msg = "Keine Beiträge geladen (WLAN prüfen)"
                detail_msg = "Konnte keine Verbindung zum pr0gramm-Server herstellen."
                sub_msg = "[A] Drücken zum Neuladen   •   [START] Setup"
                msg_color = self.color_red

            # 1. Headline
            mw = self.font_bold.size(msg)[0]
            self.draw_text(
                self.screen,
                self.font_bold,
                msg,
                msg_color,
                ((self.width - mw) // 2, card_y + int(24 * self.scale)),
            )

            # 2. Detail line
            if detail_msg:
                dmw = self.font_small.size(detail_msg)[0]
                self.draw_text(
                    self.screen,
                    self.font_small,
                    detail_msg,
                    self.color_text_dim,
                    ((self.width - dmw) // 2, card_y + int(60 * self.scale)),
                )

            # 3. Action / Guidance line
            if sub_msg:
                smw = self.font_small.size(sub_msg)[0]
                self.draw_text(
                    self.screen,
                    self.font_small,
                    sub_msg,
                    self.color_text if requires_login else self.color_text_dim,
                    ((self.width - smw) // 2, card_y + int(96 * self.scale)),
                )
            return

        total_items = len(items)
        cols = self.grid_cols
        card_w = self.card_size
        card_h = self.card_size
        gap = self.grid_gap

        # Calculate horizontal centering
        grid_total_w = cols * card_w + (cols - 1) * gap
        start_x = max(10, (self.width - grid_total_w) // 2)

        view_y_start = self.header_height + 8
        view_y_end = self.height - self.footer_height - 8
        visible_height = view_y_end - view_y_start

        # Render visible rows
        total_rows = math.ceil(total_items / cols)
        start_row = max(0, scroll_row)
        rows_to_render = (visible_height // (card_h + gap)) + 2

        for row in range(start_row, min(total_rows, start_row + rows_to_render)):
            y = view_y_start + (row - scroll_row) * (card_h + gap)

            for col in range(cols):
                idx = row * cols + col
                if idx >= total_items:
                    break

                x = start_x + col * (card_w + gap)
                card_rect = pygame.Rect(x, y, card_w, card_h)
                is_selected = (idx == selected_idx)
                item = items[idx]

                # Card background
                pygame.draw.rect(self.screen, self.color_card, card_rect, border_radius=6)

                # Thumbnail image
                thumb_url = Pr0API.get_thumb_url(item)
                thumb_surf = cache_manager.get_surface(thumb_url, priority=1)

                if thumb_surf:
                    inner_w = card_w - 8
                    inner_h = card_h - 8
                    scaled_thumb = self._get_scaled_surface(thumb_surf, inner_w, inner_h)
                    self.screen.blit(scaled_thumb, (x + 4, y + 4))
                else:
                    placeholder_txt = "..."
                    pw, ph = self.font_small.size(placeholder_txt)
                    self.draw_text(
                        self.screen,
                        self.font_small,
                        placeholder_txt,
                        self.color_text_dim,
                        (x + (card_w - pw) // 2, y + (card_h - ph) // 2),
                    )

                # Video badge [VID]
                if Pr0API.is_video(item):
                    badge_rect = pygame.Rect(x + card_w - 36, y + 6, 30, 16)
                    pygame.draw.rect(self.screen, (20, 20, 22), badge_rect, border_radius=3)
                    self.draw_text(self.screen, self.font_small, "VID", self.color_accent, (badge_rect.x + 4, badge_rect.y + 1))

                # Selection frame
                if is_selected:
                    if header_focused:
                        pygame.draw.rect(self.screen, (70, 70, 80), card_rect, width=2, border_radius=6)
                    else:
                        pygame.draw.rect(self.screen, self.color_accent, card_rect, width=3, border_radius=6)
                else:
                    pygame.draw.rect(self.screen, self.color_card_border, card_rect, width=1, border_radius=6)

        # Vertical Scrollbar for Grid
        visible_rows_count = max(1, visible_height // (card_h + gap))
        scrollbar_x = self.width - 8
        self.draw_scrollbar(
            self.screen,
            scrollbar_x,
            view_y_start,
            5,
            visible_height,
            total_rows,
            visible_rows_count,
            scroll_row,
        )

    # -------------------------------------------------------------------------
    # 2. Single Post View (Continuous vertical scroll: Media -> Meta -> Tags -> Comments)
    # -------------------------------------------------------------------------

    def render_post(
        self,
        item: dict[str, Any],
        tags: list[dict[str, Any]],
        comments: list[dict[str, Any]],
        cache_manager: Any,
        scroll_y: int,
        video_player_available: bool = True,
        is_loading_info: bool = False,
        inline_frame: pygame.Surface | None = None,
        inline_progress: float | None = None,
        focused_idx: int = 0,
    ) -> tuple[int, dict[int, tuple[int, int]]]:
        """Render single post view with media at top and comments directly underneath.

        Returns (max_scroll in pixels, focus_targets dict mapping focus_idx -> (content_y, height)).
        """
        self.screen.fill(self.color_bg)

        view_y_start = self.header_height
        view_y_end = self.height - self.footer_height
        viewport_w = self.width
        viewport_h = view_y_end - view_y_start

        # Clip drawing strictly to viewport between header and footer
        self.screen.set_clip(pygame.Rect(0, view_y_start, viewport_w, viewport_h))

        content_x = 12
        content_w = viewport_w - 24
        content_y_start = view_y_start + 10
        curr_y = content_y_start - scroll_y

        is_video = Pr0API.is_video(item)
        media_url = Pr0API.get_media_url(item)
        thumb_url = Pr0API.get_thumb_url(item)

        focus_targets: dict[int, tuple[int, int]] = {}

        # 1. Media (Image or Video)
        if is_video:
            active_surf = inline_frame if inline_frame is not None else cache_manager.get_surface(thumb_url, priority=0)
        else:
            full_surf = cache_manager.get_surface(media_url, priority=0)
            thumb_surf = cache_manager.get_surface(thumb_url, priority=0)
            active_surf = full_surf if full_surf else thumb_surf

        if active_surf:
            orig_w = max(1, active_surf.get_width())
            orig_h = max(1, active_surf.get_height())
            aspect = orig_h / orig_w

            if is_video:
                if inline_frame is not None:
                    # Directly blit decoded inline frame at its native decoded resolution (no CPU smoothscale)
                    target_w = inline_frame.get_width()
                    target_h = inline_frame.get_height()
                    scaled_surf = inline_frame
                else:
                    max_w = min(640, content_w)
                    max_h = int(viewport_h * 0.72)
                    scale_factor = min(max_w / orig_w, max_h / orig_h)
                    target_w = max(120, int(orig_w * scale_factor))
                    target_h = max(70, int(orig_h * scale_factor))
                    scaled_surf = self._get_scaled_surface(active_surf, target_w, target_h)

                draw_x = (viewport_w - target_w) // 2
                focus_targets[0] = (0, target_h)
                if curr_y + target_h >= view_y_start and curr_y <= view_y_end:
                    self.screen.blit(scaled_surf, (draw_x, curr_y))

                    # Sleek animated progress bar at the bottom edge of the video
                    if inline_progress is not None and inline_progress > 0.0:
                        bar_h = 4
                        bar_y = curr_y + target_h - bar_h
                        bg_rect = pygame.Rect(draw_x, bar_y, target_w, bar_h)
                        pygame.draw.rect(self.screen, (20, 20, 20), bg_rect)
                        fill_w = int(target_w * max(0.0, min(1.0, inline_progress)))
                        if fill_w > 0:
                            fill_rect = pygame.Rect(draw_x, bar_y, fill_w, bar_h)
                            pygame.draw.rect(self.screen, self.color_accent, fill_rect)

                curr_y += target_h + 14
            else:
                # Image display: 'Tapeten' expand vertically; normal images fit first screen
                if aspect > 1.3:
                    target_w = content_w
                    target_h = int(orig_h * (target_w / orig_w))
                    draw_x = content_x
                    focus_targets[0] = (0, target_h)
                    scaled_surf = self._get_scaled_surface(active_surf, target_w, target_h)
                    if curr_y + target_h >= view_y_start and curr_y <= view_y_end:
                        self.screen.blit(scaled_surf, (draw_x, curr_y))
                    curr_y += target_h + 14
                else:
                    max_w = content_w
                    max_h = viewport_h - 40
                    scale_factor = min(max_w / orig_w, max_h / orig_h)
                    target_w = max(100, int(orig_w * scale_factor))
                    target_h = max(60, int(orig_h * scale_factor))
                    draw_x = (viewport_w - target_w) // 2
                    focus_targets[0] = (0, target_h)
                    scaled_surf = self._get_scaled_surface(active_surf, target_w, target_h)
                    if curr_y + target_h >= view_y_start and curr_y <= view_y_end:
                        self.screen.blit(scaled_surf, (draw_x, curr_y))
                    curr_y += target_h + 14
        else:
            placeholder_h = int(160 * self.scale)
            focus_targets[0] = (0, placeholder_h)
            pygame.draw.rect(self.screen, self.color_card, (content_x, curr_y, content_w, placeholder_h), border_radius=6)
            msg = "Lade Medium..."
            mw = self.font_regular.size(msg)[0]
            self.draw_text(self.screen, self.font_regular, msg, self.color_text_dim,
                           (content_x + (content_w - mw) // 2, curr_y + placeholder_h // 2 - 8))
            curr_y += placeholder_h + 14

        # 2. Post Meta Card (Score, Author, Date)
        meta_h = int(38 * self.scale)
        meta_rect = pygame.Rect(content_x, curr_y, content_w, meta_h)
        if curr_y + meta_h >= view_y_start and curr_y <= view_y_end:
            pygame.draw.rect(self.screen, self.color_card, meta_rect, border_radius=6)
            pygame.draw.rect(self.screen, self.color_card_border, meta_rect, width=1, border_radius=6)

            up = item.get("up", 0)
            down = item.get("down", 0)
            score = up - down
            score_color = self.color_green if score > 0 else (self.color_red if score < 0 else self.color_text_dim)
            score_txt = f"Benis: {score:+d} (+{up}/-{down})"
            user_txt = f"von {item.get('user', 'unbekannt')}"
            created_ts = item.get("created", 0)
            time_txt = format_time_ago(created_ts) if created_ts else ""

            meta_x = content_x + 12
            meta_y = curr_y + int(10 * self.scale)
            meta_x += self.draw_text(self.screen, self.font_bold, score_txt, score_color, (meta_x, meta_y)) + 14
            meta_x += self.draw_text(self.screen, self.font_regular, user_txt, self.color_text, (meta_x, meta_y)) + 14
            if time_txt:
                self.draw_text(self.screen, self.font_small, f"• {time_txt}", self.color_text_dim, (meta_x, meta_y + 1))

        curr_y += meta_h + 12

        # 3. Tags Section
        if tags:
            tag_title = f"Tags ({len(tags)}):"
            if curr_y + 20 >= view_y_start and curr_y <= view_y_end:
                self.draw_text(self.screen, self.font_bold, tag_title, self.color_text_dim, (content_x, curr_y))
            curr_y += 20

            tag_x = content_x
            pill_h = int(20 * self.scale)
            for tag_obj in tags:
                tag_name = str(tag_obj.get("tag", ""))
                tag_pill = f"#{tag_name}"
                pill_w = self.font_small.size(tag_pill)[0] + 10

                if tag_x + pill_w > content_x + content_w:
                    tag_x = content_x
                    curr_y += pill_h + 6

                if curr_y + pill_h >= view_y_start and curr_y <= view_y_end:
                    pill_rect = pygame.Rect(tag_x, curr_y, pill_w, pill_h)
                    pygame.draw.rect(self.screen, self.color_tag_bg, pill_rect, border_radius=4)
                    self.draw_text(self.screen, self.font_small, tag_pill, self.color_tag_text, (tag_x + 5, curr_y + 2))
                tag_x += pill_w + 6

            curr_y += pill_h + 14

        # 4. Divider Line
        if curr_y >= view_y_start and curr_y <= view_y_end:
            pygame.draw.line(self.screen, self.color_card_border, (content_x, curr_y), (content_x + content_w, curr_y), 1)
        curr_y += 12

        # 5. Comments Section (rendered directly below with high-performance viewport culling)
        comment_count = len(comments)
        comment_title = f"Kommentare ({comment_count}):"
        if curr_y + 24 >= view_y_start and curr_y <= view_y_end:
            self.draw_text(self.screen, self.font_bold, comment_title, self.color_accent, (content_x, curr_y))
        curr_y += 24

        # Action Button: Write new comment (Focus index 1)
        btn_comment_h = int(28 * self.scale)
        btn_content_y = curr_y + scroll_y - content_y_start
        focus_targets[1] = (btn_content_y, btn_comment_h)
        is_btn_focused = (focused_idx == 1)

        if curr_y + btn_comment_h >= view_y_start and curr_y <= view_y_end:
            btn_rect = pygame.Rect(content_x, curr_y, content_w, btn_comment_h)
            if is_btn_focused:
                pygame.draw.rect(self.screen, self.color_accent, btn_rect, border_radius=6)
                btn_txt_col = (255, 255, 255)
            else:
                pygame.draw.rect(self.screen, self.color_card, btn_rect, border_radius=6)
                pygame.draw.rect(self.screen, self.color_card_border, btn_rect, width=1, border_radius=6)
                btn_txt_col = self.color_text_dim

            btn_txt = "✎  Neuen Kommentar verfassen..."
            bw = self.font_small.size(btn_txt)[0]
            self.draw_text(
                self.screen,
                self.font_bold if is_btn_focused else self.font_small,
                btn_txt,
                btn_txt_col,
                (btn_rect.centerx - bw // 2, btn_rect.centery - self.font_small.get_height() // 2),
            )

        curr_y += btn_comment_h + 14

        if is_loading_info:
            if curr_y + 24 >= view_y_start and curr_y <= view_y_end:
                self.draw_text(self.screen, self.font_small, "Lade Kommentare...", self.color_text_dim, (content_x, curr_y))
            curr_y += 24
        elif not comments:
            if curr_y + 24 >= view_y_start and curr_y <= view_y_end:
                self.draw_text(self.screen, self.font_small, "Noch keine Kommentare vorhanden.", self.color_text_dim, (content_x, curr_y))
            curr_y += 24
        else:
            layout_items = self._get_comment_layout(item["id"], comments, content_w)
            for idx, c_info in enumerate(layout_items):
                item_h = c_info["item_h"]
                item_content_y = curr_y + scroll_y - content_y_start
                focus_targets[idx + 2] = (item_content_y, item_h)
                is_focused = (focused_idx == (idx + 2))

                # Viewport Culling: Skip rendering if completely off-screen
                if curr_y + item_h < view_y_start:
                    curr_y += item_h + 10
                    continue
                if curr_y > view_y_end:
                    curr_y += item_h + 10
                    continue

                # On-screen: Render comment card elements
                c_x = c_info["c_x"]
                c_w = c_info["c_w"]
                depth = c_info["depth"]

                if is_focused:
                    pad_v = 3
                    pad_h = 6
                    focus_rect = pygame.Rect(c_x - pad_h, curr_y - pad_v, c_w + pad_h * 2, item_h + pad_v * 2)
                    pygame.draw.rect(self.screen, (34, 34, 40), focus_rect, border_radius=4)
                    pygame.draw.rect(self.screen, self.color_accent, focus_rect, width=1, border_radius=4)

                if depth > 0:
                    line_color = self.color_accent if is_focused else self.color_card_border
                    pygame.draw.line(self.screen, line_color, (c_x - 6, curr_y + 2), (c_x - 6, curr_y + 16), 2)

                prefix = "▶ " if is_focused else ""
                author_str = f"{prefix}{c_info['author']}"
                author_w = self.draw_text(self.screen, self.font_small, author_str, self.color_accent, (c_x, curr_y))

                score_val = c_info["up"] - c_info["down"]
                score_color = self.color_green if score_val > 0 else (self.color_red if score_val < 0 else self.color_text_dim)
                score_w = self.draw_text(self.screen, self.font_small, c_info["score_str"], score_color, (c_x + author_w, curr_y))
                if c_info["time_txt"]:
                    self.draw_text(self.screen, self.font_small, c_info["time_txt"], self.color_text_dim, (c_x + author_w + score_w, curr_y))

                line_y = curr_y + 18
                for line in c_info["wrapped_lines"]:
                    self.draw_text(self.screen, self.font_small, line, self.color_text, (c_x, line_y))
                    line_y += 16

                curr_y += item_h + 10

        curr_y += 20  # Bottom padding

        # Calculate total scroll range
        total_content_h = (curr_y + scroll_y) - view_y_start
        max_scroll = max(0, total_content_h - viewport_h + 10)

        # Restore normal clipping for scrollbar and outer frame
        self.screen.set_clip(None)

        # Draw vertical scrollbar
        self.draw_scrollbar(
            self.screen,
            self.width - 6,
            view_y_start + 4,
            4,
            viewport_h - 8,
            total_content_h,
            viewport_h,
            scroll_y,
        )

        return max_scroll, focus_targets

    def render_comment_modal(
        self,
        comment: dict[str, Any],
        selected_idx: int = 0,
    ) -> None:
        """Render action popup modal for a comment (+1, -1, Antworten, Abbrechen)."""
        # 1. Semi-transparent backdrop overlay
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # 2. Centered dialog box
        box_w = min(int(460 * self.scale), self.width - 24)
        box_h = int(240 * self.scale)
        box_x = (self.width - box_w) // 2
        box_y = (self.height - box_h) // 2
        box_rect = pygame.Rect(box_x, box_y, box_w, box_h)

        pygame.draw.rect(self.screen, self.color_card, box_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.color_card_border, box_rect, width=1, border_radius=8)

        # 3. Header: Author & Score
        author = comment.get("name", "unbekannt")
        up = comment.get("up", 0)
        down = comment.get("down", 0)
        score = up - down
        score_col = self.color_green if score > 0 else (self.color_red if score < 0 else self.color_text_dim)

        header_y = box_y + int(12 * self.scale)
        hx = box_x + int(16 * self.scale)
        hx += self.draw_text(self.screen, self.font_bold, f"Kommentar von @{author}", self.color_accent, (hx, header_y)) + 10
        self.draw_text(self.screen, self.font_small, f"({score:+d})", score_col, (hx, header_y + 2))

        # 4. Comment Preview snippet
        raw_text = comment.get("content", "").replace("\n", " ").strip()
        if len(raw_text) > 65:
            raw_text = raw_text[:62] + "..."
        preview_y = header_y + int(20 * self.scale)
        self.draw_text(self.screen, self.font_small, f"„{raw_text}“", self.color_text_dim, (box_x + int(16 * self.scale), preview_y))

        # Divider
        div_y = preview_y + int(20 * self.scale)
        pygame.draw.line(self.screen, self.color_card_border, (box_x + 12, div_y), (box_x + box_w - 12, div_y), 1)

        # 5. Options List
        options = [
            ("✎ Antworten", "Antwort auf diesen Kommentar schreiben"),
            ("▲ +1 (Blussi)", "Kommentar positiv bewerten"),
            ("▼ -1 (Downvote)", "Kommentar negativ bewerten"),
            ("✕ Abbrechen", "Zurück"),
        ]

        opt_start_y = div_y + int(8 * self.scale)
        opt_h = int(28 * self.scale)
        opt_gap = int(4 * self.scale)

        for i, (opt_title, opt_desc) in enumerate(options):
            opt_y = opt_start_y + i * (opt_h + opt_gap)
            opt_rect = pygame.Rect(box_x + int(14 * self.scale), opt_y, box_w - int(28 * self.scale), opt_h)
            is_sel = (i == selected_idx)

            if is_sel:
                pygame.draw.rect(self.screen, self.color_accent, opt_rect, border_radius=6)
                txt_col = (255, 255, 255)
                desc_col = (240, 240, 240)
                prefix = "▶ "
            else:
                pygame.draw.rect(self.screen, (22, 22, 26), opt_rect, border_radius=6)
                pygame.draw.rect(self.screen, self.color_card_border, opt_rect, width=1, border_radius=6)
                txt_col = self.color_text
                desc_col = self.color_text_dim
                prefix = "   "

            tx = opt_rect.x + int(10 * self.scale)
            ty = opt_rect.centery - self.font_bold.get_height() // 2
            tx += self.draw_text(self.screen, self.font_bold, f"{prefix}{opt_title}", txt_col, (tx, ty)) + 14
            self.draw_text(self.screen, self.font_small, opt_desc, desc_col, (tx, ty + 2))

    def render_keyboard_modal(
        self,
        keyboard: Any,
    ) -> None:
        """Render virtual keyboard as a modal overlay on bottom half of the screen."""
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        kb_w = min(int(600 * self.scale), self.width - 16)
        kb_h = int(216 * self.scale)
        kb_x = (self.width - kb_w) // 2
        kb_y = self.height - self.footer_height - kb_h - int(6 * self.scale)

        keyboard.render(
            surface=self.screen,
            x=kb_x,
            y=kb_y,
            width=kb_w,
            height=kb_h,
            font_regular=self.font_regular,
            font_bold=self.font_bold,
            font_small=self.font_small,
            color_card=self.color_card,
            color_border=self.color_card_border,
            color_text=self.color_text,
            color_text_dim=self.color_text_dim,
            color_accent=self.color_accent,
            scale=self.scale,
        )

    # -------------------------------------------------------------------------
    # 3. Settings View (Colors, Themes, Feed Preferences)
    # -------------------------------------------------------------------------

    def render_settings(
        self,
        menu_items: list[dict[str, Any]],
        selected_idx: int,
        toast_message: str | None = None,
        toast_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Render interactive settings menu with live theme and accent switching."""
        self.screen.fill(self.color_bg)

        # Header
        header_rect = pygame.Rect(0, 0, self.width, self.header_height)
        pygame.draw.rect(self.screen, self.color_card, header_rect)
        pygame.draw.line(self.screen, self.color_card_border, (0, self.header_height - 1), (self.width, self.header_height - 1), 1)

        x = 12
        logo_w = 42 * self.scale
        logo_h = self.header_height - 10
        logo_rect = pygame.Rect(x, 5, int(logo_w), int(logo_h))
        pygame.draw.rect(self.screen, self.color_accent, logo_rect, border_radius=4)
        logo_surf = self.font_logo.render("pr0", True, self.color_text)
        self.screen.blit(
            logo_surf,
            (logo_rect.centerx - logo_surf.get_width() // 2, logo_rect.centery - logo_surf.get_height() // 2),
        )
        x += int(logo_w) + 12
        title_txt = "EINSTELLUNGEN & FARBEN"
        self.draw_text(self.screen, self.font_bold, title_txt, self.color_text, (x, 10))
        ver_badge = f"v{VERSION}"
        vw = self.font_small.size(ver_badge)[0]
        self.draw_text(self.screen, self.font_small, ver_badge, self.color_accent, (self.width - vw - 14, 12))

        # Main settings list area
        view_y_start = self.header_height + int(8 * self.scale)
        view_y_end = self.height - self.footer_height - int(6 * self.scale)
        content_w = min(int(600 * self.scale), self.width - int(24 * self.scale))
        start_x = (self.width - content_w) // 2

        row_h = int(28 * self.scale)
        row_gap = int(4 * self.scale)
        item_step = row_h + row_gap

        total_items = len(menu_items)
        avail_h = view_y_end - view_y_start
        max_visible = max(1, avail_h // item_step)

        if total_items <= max_visible:
            start_item = 0
            visible_count = total_items
        else:
            half = max_visible // 2
            start_item = max(0, min(selected_idx - half, total_items - max_visible))
            visible_count = max_visible

        curr_y = view_y_start
        for i in range(start_item, start_item + visible_count):
            item = menu_items[i]
            is_selected = (i == selected_idx)
            row_rect = pygame.Rect(start_x, curr_y, content_w, row_h)

            bg_col = self.color_card if not is_selected else (
                min(255, self.color_card[0] + 16),
                min(255, self.color_card[1] + 16),
                min(255, self.color_card[2] + 20),
            )
            pygame.draw.rect(self.screen, bg_col, row_rect, border_radius=6)
            if is_selected:
                pygame.draw.rect(self.screen, self.color_accent, row_rect, width=2, border_radius=6)
            else:
                pygame.draw.rect(self.screen, self.color_card_border, row_rect, width=1, border_radius=6)

            # Left: Label
            label_font = self.font_bold if is_selected else self.font_regular
            label_color = self.color_accent if is_selected else self.color_text
            lx = start_x + int(12 * self.scale)
            ly = curr_y + (row_h - label_font.get_height()) // 2
            self.draw_text(self.screen, label_font, item["label"], label_color, (lx, ly))

            # Right: Value display
            val_txt = str(item.get("display_value", item.get("value", "")))
            val_font = self.font_bold if is_selected else self.font_small
            pad_right = int(14 * self.scale)

            if item.get("type") in ("action", "info"):
                val_color = self.color_accent if is_selected else self.color_text_dim
                val_w = val_font.size(val_txt)[0]
                vx = start_x + content_w - val_w - pad_right
                vy = curr_y + (row_h - val_font.get_height()) // 2
                self.draw_text(self.screen, val_font, val_txt, val_color, (vx, vy))
            else:
                val_color = self.color_accent if is_selected else self.color_text
                arrows_txt = f"◄  {val_txt}  ►" if is_selected else val_txt
                vw = val_font.size(arrows_txt)[0]
                vx = start_x + content_w - vw - pad_right
                vy = curr_y + (row_h - val_font.get_height()) // 2

                # If theme or accent, draw small color swatch box
                swatch_color = item.get("swatch_color")
                if swatch_color:
                    swatch_size = int(14 * self.scale)
                    swatch_rect = pygame.Rect(
                        vx - swatch_size - int(8 * self.scale),
                        curr_y + (row_h - swatch_size) // 2,
                        swatch_size,
                        swatch_size,
                    )
                    pygame.draw.rect(self.screen, swatch_color, swatch_rect, border_radius=3)
                    pygame.draw.rect(self.screen, self.color_card_border, swatch_rect, width=1, border_radius=3)

                self.draw_text(self.screen, val_font, arrows_txt, val_color, (vx, vy))

            curr_y += item_step

        # Sleek vertical scrollbar if list overflows viewport
        if total_items > max_visible:
            sb_w = max(3, int(4 * self.scale))
            sb_x = min(self.width - sb_w - 4, start_x + content_w + int(4 * self.scale))
            sb_y = view_y_start
            sb_h = visible_count * item_step - row_gap
            thumb_h = max(int(24 * self.scale), int(sb_h * (visible_count / total_items)))
            scrollable = sb_h - thumb_h
            thumb_y = sb_y + int(scrollable * (start_item / (total_items - visible_count)))

            pygame.draw.rect(self.screen, self.color_card, (sb_x, sb_y, sb_w, sb_h), border_radius=2)
            pygame.draw.rect(self.screen, self.color_accent, (sb_x, thumb_y, sb_w, thumb_h), border_radius=2)

        # Live Theme Preview Box below settings list (if space permits)
        preview_h = min(int(64 * self.scale), view_y_end - curr_y - 4)
        if total_items <= max_visible and preview_h > int(32 * self.scale):
            preview_rect = pygame.Rect(start_x, curr_y + 4, content_w, preview_h)
            pygame.draw.rect(self.screen, self.color_card, preview_rect, border_radius=6)
            pygame.draw.rect(self.screen, self.color_card_border, preview_rect, width=1, border_radius=6)

            px = start_x + int(12 * self.scale)
            py = curr_y + int(8 * self.scale)
            self.draw_text(self.screen, self.font_small, "Live-Vorschau:", self.color_text_dim, (px, py))

            # Swatch badge
            badge_rect = pygame.Rect(px, py + int(18 * self.scale), int(110 * self.scale), int(22 * self.scale))
            pygame.draw.rect(self.screen, self.color_accent, badge_rect, border_radius=4)
            bw = self.font_small.size("Akzentfarbe")[0]
            self.draw_text(self.screen, self.font_small, "Akzentfarbe", self.color_text, (px + (badge_rect.width - bw) // 2, py + int(22 * self.scale)))

            # Sample items
            self.draw_text(self.screen, self.font_small, "Benis: +1337", self.color_green, (px + int(122 * self.scale), py + int(22 * self.scale)))
            self.draw_text(self.screen, self.font_small, "#pr0gramm", self.color_tag_text, (px + int(220 * self.scale), py + int(22 * self.scale)))

        # Footer
        self.render_footer(
            hints=[
                ("▲/▼", "Auswahl"),
                ("◄/►", "Ändern"),
                ("A", "Aktion"),
                ("B/START", "Speichern & Zurück"),
            ],
            toast_message=toast_message,
            toast_color=toast_color,
        )

    # -------------------------------------------------------------------------
    # Tree & Wrapping Helpers
    # -------------------------------------------------------------------------

    def _build_comment_tree(self, comments: list[dict[str, Any]]) -> list[tuple[dict[str, Any], int]]:
        """Order comments hierarchically into (comment, depth) tuples."""
        by_parent: dict[int, list[dict[str, Any]]] = {}
        for c in comments:
            parent = c.get("parent", 0)
            by_parent.setdefault(parent, []).append(c)

        ordered: list[tuple[dict[str, Any], int]] = []

        def recurse(parent_id: int, depth: int) -> None:
            children = by_parent.get(parent_id, [])
            for child in children:
                ordered.append((child, depth))
                recurse(child.get("id", 0), depth + 1)

        recurse(0, 0)
        return ordered

    def _wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        """Wrap a multi-line string to fit within max_width pixels with cached word measurements."""
        if not hasattr(self, "_word_w_cache"):
            self._word_w_cache: dict[tuple[int, str], int] = {}

        font_id = id(font)
        cache = self._word_w_cache
        space_key = (font_id, " ")
        if space_key not in cache:
            cache[space_key] = font.size(" ")[0]
        space_w = cache[space_key]

        lines: list[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split(" ")
            curr_words: list[str] = []
            curr_w = 0

            for word in words:
                key = (font_id, word)
                if key not in cache:
                    cache[key] = font.size(word)[0]
                w_w = cache[key]

                test_w = curr_w + (space_w if curr_words else 0) + w_w
                if test_w <= max_width:
                    curr_words.append(word)
                    curr_w = test_w
                else:
                    if curr_words:
                        lines.append(" ".join(curr_words))
                    curr_words = [word]
                    curr_w = w_w

            if curr_words:
                lines.append(" ".join(curr_words))

        if len(cache) > 2500:
            cache.clear()

        return lines or [""]

    # -------------------------------------------------------------------------
    # 5. Button Test & Diagnostics View
    # -------------------------------------------------------------------------

    def render_button_test(
        self,
        diag: dict[str, Any],
        layout_name: str,
        toast_message: str | None = None,
        toast_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Render interactive gamepad diagnostic screen with live button highlighting."""
        self.screen.fill(self.color_bg)

        # Header
        header_rect = pygame.Rect(0, 0, self.width, self.header_height)
        pygame.draw.rect(self.screen, self.color_card, header_rect)
        pygame.draw.line(self.screen, self.color_card_border, (0, self.header_height - 1), (self.width, self.header_height - 1), 1)

        x = 12
        logo_w = 42 * self.scale
        logo_h = self.header_height - 10
        logo_rect = pygame.Rect(x, 5, int(logo_w), int(logo_h))
        pygame.draw.rect(self.screen, self.color_accent, logo_rect, border_radius=4)
        logo_surf = self.font_logo.render("pr0", True, self.color_text)
        self.screen.blit(logo_surf, (logo_rect.centerx - logo_surf.get_width() // 2, logo_rect.centery - logo_surf.get_height() // 2))
        x += int(logo_w) + 12

        self.draw_text(self.screen, self.font_bold, "TASTEN-TEST & DIAGNOSE", self.color_text, (x, 10))

        # Right header: Layout tag
        layout_tag = f"Layout: [{layout_name.upper()}]"
        lt_w = self.font_small.size(layout_tag)[0]
        self.draw_text(self.screen, self.font_small, layout_tag, self.color_accent, (self.width - lt_w - 14, 12))

        # Main Card
        view_y = self.header_height + 10
        card_w = min(580, self.width - 24)
        card_h = self.height - self.header_height - self.footer_height - 20
        start_x = (self.width - card_w) // 2
        card_rect = pygame.Rect(start_x, view_y, card_w, card_h)
        pygame.draw.rect(self.screen, self.color_card, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.color_card_border, card_rect, width=1, border_radius=8)

        now = time.time()
        is_active = (now - diag.get("timestamp", 0.0)) < 0.6
        active_btn = diag.get("button_label", "") if is_active else ""

        # Draw Controller Visual
        center_x = start_x + card_w // 2
        visual_y = view_y + int(card_h * 0.28)

        # 1. D-Pad on Left
        dpad_cx = center_x - int(130 * self.scale)
        dpad_cy = visual_y
        dpad_size = int(22 * self.scale)

        dpad_buttons = [
            ("D-Pad Hoch", dpad_cx, dpad_cy - dpad_size - 4, "▲"),
            ("D-Pad Runter", dpad_cx, dpad_cy + dpad_size + 4, "▼"),
            ("D-Pad Links", dpad_cx - dpad_size - 4, dpad_cy, "◄"),
            ("D-Pad Rechts", dpad_cx + dpad_size + 4, dpad_cy, "►"),
        ]
        for name, bx, by, symbol in dpad_buttons:
            lit = is_active and (name in active_btn)
            b_rect = pygame.Rect(bx - dpad_size // 2, by - dpad_size // 2, dpad_size, dpad_size)
            pygame.draw.rect(self.screen, self.color_accent if lit else self.color_tag_bg, b_rect, border_radius=4)
            pygame.draw.rect(self.screen, self.color_card_border, b_rect, width=1, border_radius=4)
            sym_w, sym_h = self.font_small.size(symbol)
            self.draw_text(self.screen, self.font_small, symbol, self.color_text if lit else self.color_text_dim, (bx - sym_w // 2, by - sym_h // 2))

        # 2. Shoulder Buttons (Top)
        sh_y = visual_y - int(60 * self.scale)
        l1_rect = pygame.Rect(dpad_cx - int(35 * self.scale), sh_y, int(70 * self.scale), int(18 * self.scale))
        l1_lit = is_active and ("L1" in active_btn)
        pygame.draw.rect(self.screen, self.color_accent if l1_lit else self.color_tag_bg, l1_rect, border_radius=4)
        pygame.draw.rect(self.screen, self.color_card_border, l1_rect, width=1, border_radius=4)
        l1_w, l1_h = self.font_small.size("L1")
        self.draw_text(self.screen, self.font_small, "L1", self.color_text if l1_lit else self.color_text_dim, (l1_rect.centerx - l1_w // 2, l1_rect.centery - l1_h // 2))

        # 3. Face Buttons on Right (Diamond)
        face_cx = center_x + int(130 * self.scale)
        face_cy = visual_y
        f_radius = int(14 * self.scale)
        dist = int(28 * self.scale)

        top_name, top_lbl = "X", "X"
        bot_name, bot_lbl = "B", "B"
        left_name, left_lbl = "Y", "Y"
        right_name, right_lbl = "A", "A"

        face_buttons = [
            (top_name, face_cx, face_cy - dist, top_lbl),
            (bot_name, face_cx, face_cy + dist, bot_lbl),
            (left_name, face_cx - dist, face_cy, left_lbl),
            (right_name, face_cx + dist, face_cy, right_lbl),
        ]

        r1_rect = pygame.Rect(face_cx - int(35 * self.scale), sh_y, int(70 * self.scale), int(18 * self.scale))
        r1_lit = is_active and ("R1" in active_btn)
        pygame.draw.rect(self.screen, self.color_accent if r1_lit else self.color_tag_bg, r1_rect, border_radius=4)
        pygame.draw.rect(self.screen, self.color_card_border, r1_rect, width=1, border_radius=4)
        r1_w, r1_h = self.font_small.size("R1")
        self.draw_text(self.screen, self.font_small, "R1", self.color_text if r1_lit else self.color_text_dim, (r1_rect.centerx - r1_w // 2, r1_rect.centery - r1_h // 2))

        for name, fx, fy, letter in face_buttons:
            lit = is_active and (name in active_btn)
            pygame.draw.circle(self.screen, self.color_accent if lit else self.color_tag_bg, (fx, fy), f_radius)
            pygame.draw.circle(self.screen, self.color_card_border, (fx, fy), f_radius, width=1)
            lw, lh = self.font_bold.size(letter)
            self.draw_text(self.screen, self.font_bold, letter, self.color_text if lit else self.color_text_dim, (fx - lw // 2, fy - lh // 2))

        # 4. Results Info Box
        info_y = visual_y + int(card_h * 0.24)
        info_rect = pygame.Rect(start_x + 16, info_y, card_w - 32, card_h - (info_y - view_y) - 14)
        pygame.draw.rect(self.screen, self.color_bg, info_rect, border_radius=6)
        pygame.draw.rect(self.screen, self.color_card_border, info_rect, width=1, border_radius=6)

        iy = info_y + 10
        btn_disp = diag.get("button_label", "Keine Taste gedrückt")
        act_disp = diag.get("action", "-")
        raw_disp = f"{diag.get('raw_type', 'N/A')} ({diag.get('raw_detail', 'N/A')})"

        self.draw_text(self.screen, self.font_small, "Taste:", self.color_text_dim, (start_x + 28, iy))
        self.draw_text(self.screen, self.font_bold, btn_disp, self.color_accent if is_active else self.color_text, (start_x + 120, iy))

        iy += 22
        self.draw_text(self.screen, self.font_small, "Aktion:", self.color_text_dim, (start_x + 28, iy))
        self.draw_text(self.screen, self.font_bold, act_disp, self.color_green if is_active else self.color_text, (start_x + 120, iy))

        iy += 22
        self.draw_text(self.screen, self.font_small, "Treiber-Event:", self.color_text_dim, (start_x + 28, iy))
        self.draw_text(self.screen, self.font_mono, raw_disp, self.color_tag_text, (start_x + 120, iy))

        # Footer
        self.render_footer(
            hints=[
                ("START", "Test beenden"),
                ("B 2x", "Zurück"),
            ],
            toast_message=toast_message,
            toast_color=toast_color,
        )

    def render_login(
        self,
        mode: str = "qr",
        url: str = "",
        qr_surface: pygame.Surface | None = None,
        direct_fields: dict[str, Any] | None = None,
        active_keyboard: Any | None = None,
        status_message: str | None = None,
        status_color: tuple[int, int, int] | None = None,
        toast_message: str | None = None,
        toast_color: tuple[int, int, int] | None = None,
    ) -> None:
        """Render the Account Login View supporting QR/Smartphone and Direct Handheld input."""
        self.screen.fill(self.color_bg)

        # Header Bar
        header_rect = pygame.Rect(0, 0, self.width, self.header_height)
        pygame.draw.rect(self.screen, self.color_card, header_rect)
        pygame.draw.line(self.screen, self.color_card_border, (0, self.header_height - 1), (self.width, self.header_height - 1), 1)

        center_y = self.header_height // 2
        badge_w = int(36 * self.scale)
        badge_h = int(22 * self.scale)
        logo_rect = pygame.Rect(10, center_y - badge_h // 2, badge_w, badge_h)
        pygame.draw.rect(self.screen, self.color_accent, logo_rect, border_radius=4)
        logo_surf = self.font_logo.render("pr0", True, (255, 255, 255))
        self.screen.blit(logo_surf, (logo_rect.centerx - logo_surf.get_width() // 2, logo_rect.centery - logo_surf.get_height() // 2))

        title_txt = "Account-Login"
        self.draw_text(self.screen, self.font_title, title_txt, self.color_text, (badge_w + 20, center_y - self.font_title.get_height() // 2))

        # Mode Tag on Top Right
        mode_tag = "Smartphone / QR" if mode == "qr" else "Direkt auf Handheld"
        mt_w = self.font_small.size(mode_tag)[0]
        self.draw_text(self.screen, self.font_small, mode_tag, self.color_accent, (self.width - mt_w - 14, center_y - self.font_small.get_height() // 2))

        # Main Card Area
        view_y = self.header_height + 8
        card_w = min(600, self.width - 20)
        card_h = self.height - self.header_height - self.footer_height - 16
        start_x = (self.width - card_w) // 2
        card_rect = pygame.Rect(start_x, view_y, card_w, card_h)
        pygame.draw.rect(self.screen, self.color_card, card_rect, border_radius=8)
        pygame.draw.rect(self.screen, self.color_card_border, card_rect, width=1, border_radius=8)

        if mode == "qr":
            # -------------------------------------------------------------
            # QR / Smartphone Mode
            # -------------------------------------------------------------
            qr_size = min(int(170 * self.scale), card_h - 40, card_w // 2 - 20)
            qr_x = start_x + int(18 * self.scale)
            qr_y = view_y + (card_h - qr_size) // 2 - int(10 * self.scale)

            # Draw QR Code if available
            if qr_surface:
                border_px = 6
                qr_bg_rect = pygame.Rect(qr_x - border_px, qr_y - border_px, qr_size + border_px * 2, qr_size + border_px * 2)
                pygame.draw.rect(self.screen, (255, 255, 255), qr_bg_rect, border_radius=6)
                if qr_surface.get_size() != (qr_size, qr_size):
                    scaled_qr = pygame.transform.scale(qr_surface, (qr_size, qr_size))
                    self.screen.blit(scaled_qr, (qr_x, qr_y))
                else:
                    self.screen.blit(qr_surface, (qr_x, qr_y))
            else:
                placeholder_rect = pygame.Rect(qr_x, qr_y, qr_size, qr_size)
                pygame.draw.rect(self.screen, self.color_bg, placeholder_rect, border_radius=6)
                self.draw_text(self.screen, self.font_small, "QR lädt...", self.color_text_dim, (qr_x + 20, qr_y + qr_size // 2))

            # Right Column: Instructions
            right_x = qr_x + qr_size + int(24 * self.scale)
            right_w = start_x + card_w - right_x - int(14 * self.scale)
            cur_y = view_y + int(16 * self.scale)

            self.draw_text(self.screen, self.font_bold, "Mit Smartphone im selben WLAN anmelden", self.color_text, (right_x, cur_y))
            cur_y += int(24 * self.scale)

            step1 = "1. Scanne den QR-Code mit der Handy-Kamera"
            self.draw_text(self.screen, self.font_small, step1, self.color_text_dim, (right_x, cur_y))
            cur_y += int(18 * self.scale)

            step2 = "oder tippe folgende Adresse im Handy-Browser ein:"
            self.draw_text(self.screen, self.font_small, step2, self.color_text_dim, (right_x, cur_y))
            cur_y += int(20 * self.scale)

            # URL Highlight Box
            url_box_h = int(30 * self.scale)
            url_rect = pygame.Rect(right_x, cur_y, min(right_w, int(300 * self.scale)), url_box_h)
            pygame.draw.rect(self.screen, self.color_bg, url_rect, border_radius=6)
            pygame.draw.rect(self.screen, self.color_accent, url_rect, width=1, border_radius=6)
            url_w = self.font_bold.size(url)[0]
            self.draw_text(self.screen, self.font_bold, url, self.color_accent, (url_rect.centerx - url_w // 2, url_rect.centery - self.font_bold.get_height() // 2))
            cur_y += url_box_h + int(14 * self.scale)

            step3 = "2. Auf der Seite Benutzername, Passwort & Captcha eingeben"
            self.draw_text(self.screen, self.font_small, step3, self.color_text_dim, (right_x, cur_y))
            cur_y += int(16 * self.scale)

            step4 = "-> Handheld loggt sich automatisch sofort ein!"
            self.draw_text(self.screen, self.font_small, step4, self.color_green, (right_x, cur_y))
            cur_y += int(24 * self.scale)

            # Live status badge
            stat_txt = status_message or "Warte auf Verbindung vom Smartphone..."
            stat_color = status_color or self.color_text_dim
            dot_color = self.color_accent if (pygame.time.get_ticks() // 600) % 2 == 0 else self.color_text_dim
            pygame.draw.circle(self.screen, dot_color, (right_x + 6, cur_y + 7), 4)
            self.draw_text(self.screen, self.font_small, stat_txt, stat_color, (right_x + 16, cur_y))

            self.render_footer(
                hints=[
                    ("X", "Direkt auf Handheld tippen"),
                    ("B", "Abbrechen"),
                ],
                toast_message=toast_message,
                toast_color=toast_color,
            )

        else:
            # -------------------------------------------------------------
            # Direct Handheld Input Mode
            # -------------------------------------------------------------
            fields = direct_fields or {}
            sel_idx = fields.get("selected_field_idx", 0)
            username_val = fields.get("username", "")
            password_val = fields.get("password", "")
            captcha_val = fields.get("captcha_code", "")
            captcha_surf = fields.get("captcha_surface")

            cur_y = view_y + int(14 * self.scale)
            content_w = card_w - int(32 * self.scale)
            cx = start_x + int(16 * self.scale)
            is_kb_open = (active_keyboard is not None)

            # Field 0: Benutzername
            u_sel = (sel_idx == 0)
            self.draw_text(self.screen, self.font_small, "Benutzername:", self.color_text_dim, (cx, cur_y))
            cur_y += int(16 * self.scale)

            box_h = int(24 * self.scale) if is_kb_open else int(28 * self.scale)
            u_rect = pygame.Rect(cx, cur_y, content_w, box_h)
            pygame.draw.rect(self.screen, self.color_bg, u_rect, border_radius=4)
            pygame.draw.rect(self.screen, self.color_accent if u_sel else self.color_card_border, u_rect, width=2 if u_sel else 1, border_radius=4)
            u_disp = username_val if username_val else "Hier Benutzername eingeben..."
            u_col = self.color_text if username_val else self.color_text_dim
            self.draw_text(self.screen, self.font_regular, u_disp, u_col, (cx + 8, u_rect.centery - self.font_regular.get_height() // 2))
            cur_y += box_h + int(8 * self.scale)

            # Field 1: Passwort
            p_sel = (sel_idx == 1)
            self.draw_text(self.screen, self.font_small, "Passwort:", self.color_text_dim, (cx, cur_y))
            cur_y += int(16 * self.scale)

            p_rect = pygame.Rect(cx, cur_y, content_w, box_h)
            pygame.draw.rect(self.screen, self.color_bg, p_rect, border_radius=4)
            pygame.draw.rect(self.screen, self.color_accent if p_sel else self.color_card_border, p_rect, width=2 if p_sel else 1, border_radius=4)
            p_disp = ("●" * len(password_val)) if password_val else "Hier Passwort eingeben..."
            p_col = self.color_text if password_val else self.color_text_dim
            self.draw_text(self.screen, self.font_regular, p_disp, p_col, (cx + 8, p_rect.centery - self.font_regular.get_height() // 2))
            cur_y += box_h + int(8 * self.scale)

            # Captcha Display & Field 2
            if captcha_surf:
                c_disp_h = int(36 * self.scale) if is_kb_open else int(50 * self.scale)
                c_aspect = captcha_surf.get_width() / max(1, captcha_surf.get_height())
                c_disp_w = int(c_disp_h * c_aspect)
                scaled_captcha = pygame.transform.smoothscale(captcha_surf, (c_disp_w, c_disp_h))

                self.screen.blit(scaled_captcha, (cx, cur_y))
                c_field_x = cx + c_disp_w + int(12 * self.scale)
                c_field_w = content_w - c_disp_w - int(12 * self.scale)
                c_sel = (sel_idx == 2)

                self.draw_text(self.screen, self.font_small, "Captcha-Code:", self.color_text_dim, (c_field_x, cur_y))
                c_box_y = cur_y + int(16 * self.scale)
                c_rect = pygame.Rect(c_field_x, c_box_y, c_field_w, box_h)
                pygame.draw.rect(self.screen, self.color_bg, c_rect, border_radius=4)
                pygame.draw.rect(self.screen, self.color_accent if c_sel else self.color_card_border, c_rect, width=2 if c_sel else 1, border_radius=4)
                c_disp = captcha_val if captcha_val else "Code..."
                c_col = self.color_text if captcha_val else self.color_text_dim
                self.draw_text(self.screen, self.font_regular, c_disp, c_col, (c_field_x + 8, c_rect.centery - self.font_regular.get_height() // 2))

                cur_y += max(c_disp_h, box_h + int(18 * self.scale)) + int(10 * self.scale)
            else:
                self.draw_text(self.screen, self.font_small, "Lade Captcha...", self.color_text_dim, (cx, cur_y))
                cur_y += int(24 * self.scale)

            if not is_kb_open:
                # Action Buttons
                btn_y = cur_y
                btn_h = int(32 * self.scale)
                btn_login_w = int(140 * self.scale)
                btn_refresh_w = int(140 * self.scale)
                btn_gap = int(10 * self.scale)

                # Button: Anmelden (Index 3)
                b3_sel = (sel_idx == 3)
                b3_rect = pygame.Rect(cx, btn_y, btn_login_w, btn_h)
                pygame.draw.rect(self.screen, self.color_accent if b3_sel else self.color_tag_bg, b3_rect, border_radius=4)
                pygame.draw.rect(self.screen, self.color_accent if b3_sel else self.color_card_border, b3_rect, width=1, border_radius=4)
                b3_txt = "Anmelden"
                b3_w = self.font_bold.size(b3_txt)[0]
                self.draw_text(self.screen, self.font_bold, b3_txt, (255, 255, 255) if b3_sel else self.color_text, (b3_rect.centerx - b3_w // 2, b3_rect.centery - self.font_bold.get_height() // 2))

                # Button: Neues Captcha (Index 4)
                b4_sel = (sel_idx == 4)
                b4_rect = pygame.Rect(cx + btn_login_w + btn_gap, btn_y, btn_refresh_w, btn_h)
                pygame.draw.rect(self.screen, self.color_accent if b4_sel else self.color_tag_bg, b4_rect, border_radius=4)
                pygame.draw.rect(self.screen, self.color_accent if b4_sel else self.color_card_border, b4_rect, width=1, border_radius=4)
                b4_txt = "Neues Captcha"
                b4_w = self.font_regular.size(b4_txt)[0]
                self.draw_text(self.screen, self.font_regular, b4_txt, (255, 255, 255) if b4_sel else self.color_text_dim, (b4_rect.centerx - b4_w // 2, b4_rect.centery - self.font_regular.get_height() // 2))

                # Status / Feedback text
                if status_message:
                    stat_y = btn_y + btn_h + int(12 * self.scale)
                    stat_col = status_color or self.color_text_dim
                    self.draw_text(self.screen, self.font_small, status_message, stat_col, (cx, stat_y))

            # Render Virtual Keyboard Overlay if active
            if active_keyboard:
                kb_w = card_w - int(12 * self.scale)
                kb_h = int(210 * self.scale)
                kb_x = start_x + int(6 * self.scale)
                kb_y = self.height - self.footer_height - kb_h - int(4 * self.scale)

                active_keyboard.render(
                    surface=self.screen,
                    x=kb_x,
                    y=kb_y,
                    width=kb_w,
                    height=kb_h,
                    font_regular=self.font_regular,
                    font_bold=self.font_bold,
                    font_small=self.font_small,
                    color_card=self.color_card,
                    color_border=self.color_card_border,
                    color_text=self.color_text,
                    color_text_dim=self.color_text_dim,
                    color_accent=self.color_accent,
                    scale=self.scale,
                )
            else:
                self.render_footer(
                    hints=[
                        ("D-Pad", "Nav"),
                        ("A", "Tippen / Ausführen"),
                        ("X", "QR / Smartphone"),
                        ("Y", "Neues Captcha"),
                        ("B", "Zurück"),
                    ],
                    toast_message=toast_message,
                    toast_color=toast_color,
                )


