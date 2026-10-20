"""Virtual On-Screen Keyboard for handheld gamepads.

Allows entering text (usernames, passwords, captcha codes) with D-Pad
navigation, A/B/X/Y button shortcuts, and optional physical keyboard input.
"""

from __future__ import annotations

import pygame
from typing import Any

# Standard QWERTY layout definitions
KEYS_LOWER: list[list[str]] = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "_", "="],
    ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "[", "]"],
    ["a", "s", "d", "f", "g", "h", "j", "k", "l", ";", "'", "@"],
    ["z", "x", "c", "v", "b", "n", "m", ",", ".", "/", "!"],
    ["[SHIFT]", "[SPACE]", "[DEL]", "[FERTIG]"],
]

KEYS_UPPER: list[list[str]] = [
    ["!", "@", "#", "$", "%", "^", "&", "*", "(", ")", "-", "_", "+"],
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "{", "}"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L", ":", "\"", "@"],
    ["Z", "X", "C", "V", "B", "N", "M", "<", ">", "?", "~"],
    ["[shift]", "[SPACE]", "[DEL]", "[FERTIG]"],
]


class VirtualKeyboard:
    """Manages virtual on-screen keyboard state and input handling."""

    def __init__(
        self,
        title: str = "Eingabe",
        initial_text: str = "",
        is_password: bool = False,
        max_length: int = 64,
    ):
        self.title = title
        self.text = initial_text
        self.is_password = is_password
        self.max_length = max_length

        self.row: int = 1
        self.col: int = 0
        self.is_shift: bool = False

    def set_target(self, title: str, initial_text: str = "", is_password: bool = False) -> None:
        """Configure keyboard for a new text field."""
        self.title = title
        self.text = initial_text
        self.is_password = is_password
        self.row = 1
        self.col = 0
        self.is_shift = False

    def _get_layout(self) -> list[list[str]]:
        return KEYS_UPPER if self.is_shift else KEYS_LOWER

    def handle_action(self, action: str) -> str | None:
        """Process handheld gamepad input action.

        Returns:
            "DONE" if confirmed/submitted,
            "CANCEL" if aborted,
            None if typing continues.
        """
        layout = self._get_layout()

        if action == "up":
            self.row = (self.row - 1) % len(layout)
            self.col = min(self.col, len(layout[self.row]) - 1)
        elif action == "down":
            self.row = (self.row + 1) % len(layout)
            self.col = min(self.col, len(layout[self.row]) - 1)
        elif action == "left":
            row_len = len(layout[self.row])
            self.col = (self.col - 1) % row_len
        elif action == "right":
            row_len = len(layout[self.row])
            self.col = (self.col + 1) % row_len

        elif action in ("confirm", "select"):  # [A] Button
            selected_key = layout[self.row][self.col]
            if selected_key in ("[SHIFT]", "[shift]"):
                self.is_shift = not self.is_shift
            elif selected_key == "[SPACE]":
                if len(self.text) < self.max_length:
                    self.text += " "
            elif selected_key == "[DEL]":
                if self.text:
                    self.text = self.text[:-1]
            elif selected_key == "[FERTIG]":
                return "DONE"
            else:
                if len(self.text) < self.max_length:
                    self.text += selected_key

        elif action in ("extra", "info"):  # [X] Button -> Shortcut for SHIFT
            self.is_shift = not self.is_shift

        elif action == "toggle_mode":  # [Y] Button -> Shortcut for Backspace
            if self.text:
                self.text = self.text[:-1]

        elif action == "back":  # [B] Button
            return "CANCEL"

        return None

    def handle_physical_key(self, event: pygame.event.Event) -> str | None:
        """Handle physical USB or PC keyboard events."""
        if event.key == pygame.K_RETURN:
            return "DONE"
        elif event.key == pygame.K_ESCAPE:
            return "CANCEL"
        elif event.key == pygame.K_BACKSPACE:
            if self.text:
                self.text = self.text[:-1]
        elif event.unicode and event.unicode.isprintable():
            if len(self.text) < self.max_length:
                self.text += event.unicode
        return None

    def render(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        height: int,
        font_regular: pygame.font.Font,
        font_bold: pygame.font.Font,
        font_small: pygame.font.Font,
        color_card: tuple[int, int, int],
        color_border: tuple[int, int, int],
        color_text: tuple[int, int, int],
        color_text_dim: tuple[int, int, int],
        color_accent: tuple[int, int, int],
        scale: float = 1.0,
    ) -> None:
        """Render virtual keyboard within the given rectangle."""
        # 1. Main background panel
        panel_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(surface, color_card, panel_rect, border_radius=8)
        pygame.draw.rect(surface, color_border, panel_rect, width=1, border_radius=8)

        pad = int(8 * scale)
        cur_y = y + pad

        # 2. Header / Title + Input Display
        title_surf = font_bold.render(self.title, True, color_accent)
        surface.blit(title_surf, (x + pad + 2, cur_y))
        cur_y += title_surf.get_height() + int(4 * scale)

        # Input text box
        box_h = int(28 * scale)
        box_rect = pygame.Rect(x + pad, cur_y, width - (pad * 2), box_h)
        pygame.draw.rect(surface, (18, 18, 20), box_rect, border_radius=4)
        pygame.draw.rect(surface, color_border, box_rect, width=1, border_radius=4)

        disp_text = ("●" * len(self.text)) if self.is_password else self.text
        # Cursor blink
        cursor_char = "_" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        full_disp = disp_text + cursor_char
        txt_surf = font_regular.render(full_disp, True, color_text)

        # Clip if too long for box
        max_txt_w = box_rect.width - int(12 * scale)
        if txt_surf.get_width() > max_txt_w:
            clip_rect = pygame.Rect(txt_surf.get_width() - max_txt_w, 0, max_txt_w, txt_surf.get_height())
            surface.blit(txt_surf, (box_rect.x + int(6 * scale), box_rect.centery - txt_surf.get_height() // 2), clip_rect)
        else:
            surface.blit(txt_surf, (box_rect.x + int(6 * scale), box_rect.centery - txt_surf.get_height() // 2))

        cur_y += box_h + int(8 * scale)

        # 3. Key Grid
        layout = self._get_layout()
        rows_total = len(layout)
        remaining_h = (y + height) - cur_y - pad - int(18 * scale)
        key_h = max(int(20 * scale), remaining_h // rows_total)
        key_gap = int(3 * scale)

        for r_idx, row_keys in enumerate(layout):
            r_y = cur_y + r_idx * key_h
            cols_total = len(row_keys)
            avail_w = width - (pad * 2)

            if r_idx == 4:
                # Bottom action row with custom proportional widths
                # [SHIFT], [SPACE], [DEL], [FERTIG]
                weights = [1.5, 3.5, 1.5, 2.0]
                total_w = sum(weights)
                cur_x = x + pad
                for c_idx, k_label in enumerate(row_keys):
                    w_ratio = weights[c_idx] / total_w
                    k_w = int(avail_w * w_ratio) - key_gap
                    self._draw_key(
                        surface, cur_x, r_y, k_w, key_h - key_gap, k_label,
                        is_selected=(r_idx == self.row and c_idx == self.col),
                        font=font_small,
                        color_card=color_card,
                        color_border=color_border,
                        color_text=color_text,
                        color_accent=color_accent,
                    )
                    cur_x += k_w + key_gap
            else:
                key_w = (avail_w - (cols_total - 1) * key_gap) // cols_total
                for c_idx, k_label in enumerate(row_keys):
                    k_x = x + pad + c_idx * (key_w + key_gap)
                    self._draw_key(
                        surface, k_x, r_y, key_w, key_h - key_gap, k_label,
                        is_selected=(r_idx == self.row and c_idx == self.col),
                        font=font_regular,
                        color_card=color_card,
                        color_border=color_border,
                        color_text=color_text,
                        color_accent=color_accent,
                    )

        # 4. Footer shortcuts
        foot_y = y + height - int(16 * scale)
        hint_txt = "[A] Tippen   [X] Shift   [Y] Löschen   [B] Abbrechen   [START] Fertig"
        hint_surf = font_small.render(hint_txt, True, color_text_dim)
        surface.blit(hint_surf, (x + pad, foot_y))

    def _draw_key(
        self,
        surface: pygame.Surface,
        kx: int,
        ky: int,
        kw: int,
        kh: int,
        label: str,
        is_selected: bool,
        font: pygame.font.Font,
        color_card: tuple[int, int, int],
        color_border: tuple[int, int, int],
        color_text: tuple[int, int, int],
        color_accent: tuple[int, int, int],
    ) -> None:
        rect = pygame.Rect(kx, ky, kw, kh)
        if is_selected:
            pygame.draw.rect(surface, color_accent, rect, border_radius=4)
            text_color = (255, 255, 255)
        else:
            pygame.draw.rect(surface, (28, 28, 32), rect, border_radius=4)
            pygame.draw.rect(surface, color_border, rect, width=1, border_radius=4)
            text_color = color_text

        rendered = font.render(label, True, text_color)
        surface.blit(
            rendered,
            (rect.centerx - rendered.get_width() // 2,
             rect.centery - rendered.get_height() // 2),
        )
