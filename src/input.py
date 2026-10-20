"""SDL2 Gamepad and Keyboard Input Handling for pr0-retroconsole.

Provides unified action dispatch for both native SDL2 game controllers
and desktop/gptokeyb keyboard inputs with:
1. Configurable button layouts: Nintendo (TrimUI / ArkOS) vs. Xbox (PC / muOS)
2. Fluid continuous hold-to-scroll & autorepeat for D-Pad and analog sticks
3. Real-time diagnostics / button test tracking
"""

from __future__ import annotations

import logging
import os
import platform
import time
from pathlib import Path
from typing import Any
import pygame

logger = logging.getLogger("pr0.input")

# Action Constants
ACTION_QUIT = "quit"
ACTION_UP = "up"
ACTION_DOWN = "down"
ACTION_LEFT = "left"
ACTION_RIGHT = "right"
ACTION_SCROLL_UP = "scroll_up"
ACTION_SCROLL_DOWN = "scroll_down"
ACTION_SELECT = "select"  # Bestätigen / Post öffnen
ACTION_BACK = "back"      # Zurück / Abbrechen
ACTION_INFO = "info"      # Einstellungen / Kommentare
ACTION_TOGGLE_MODE = "toggle_mode"  # Beliebt vs Neu
ACTION_UPVOTE = "upvote"  # R1 / + / Blussi
ACTION_DOWNVOTE = "downvote"  # L1 / - / Minus

# Standard SDL GameController Button IDs
BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_L1 = 4
BTN_R1 = 5
BTN_BACK = 6
BTN_START = 7
BTN_L3 = 8
BTN_R3 = 9


class InputManager:
    """Manages controllers, keyboards, deadzones, layouts, and autorepeat."""

    def __init__(self, axis_threshold: float = 0.45, layout: str = "auto"):
        self.axis_threshold = axis_threshold
        self.joysticks: list[pygame.joystick.Joystick] = []
        self._axis_states: dict[tuple[int, int], int] = {}  # (joy_id, axis) -> -1, 0, 1
        self._last_action_times: dict[str, float] = {}

        # Button Layout: 'nintendo' (TrimUI / ArkOS) vs 'xbox' (PC / muOS)
        self.layout_config = layout
        self.button_layout = self._resolve_layout(layout)

        # Autorepeat & Continuous Hold tracking
        self._held_actions: dict[str, float] = {}  # action -> press_timestamp
        self._last_repeat_times: dict[str, float] = {}  # action -> last_fired_timestamp
        self.stick_lx: float = 0.0
        self.stick_ly: float = 0.0
        self.stick_ry: float = 0.0

        # Diagnostics for Button-Test screen
        self.last_diag: dict[str, Any] = {
            "button_label": "Keine",
            "action": "Keine",
            "raw_type": "N/A",
            "raw_detail": "N/A",
            "timestamp": 0.0,
        }
        self.last_key_events: list[pygame.event.Event] = []

        # Detect gptokeyb
        self.is_gptokeyb_active = self._check_gptokeyb()
        if self.is_gptokeyb_active:
            logger.info("gptokeyb active: using keyboard dispatch, ignoring raw joystick to prevent double-firing.")
        else:
            self._init_joysticks()

        logger.info("InputManager init: layout=%s (resolved=%s), gptokeyb=%s",
                    self.layout_config, self.button_layout, self.is_gptokeyb_active)

    def _resolve_layout(self, layout: str) -> str:
        """Resolve layout string."""
        l_str = str(layout).lower().strip()
        if l_str in ("inverted", "vertauscht", "swap", "swapped", "xbox"):
            return "inverted"
        return "standard"

    def set_layout(self, layout: str) -> None:
        """Dynamically switch between 'nintendo' and 'xbox' button mapping."""
        self.layout_config = layout
        self.button_layout = self._resolve_layout(layout)
        self.clear_events()
        logger.info("Control layout switched to: %s", self.button_layout)

    def _check_gptokeyb(self) -> bool:
        """Detect if gptokeyb daemon is actively converting controller inputs to keyboard strokes."""
        if os.environ.get("GPTOKEYB_ACTIVE") == "1":
            return True
        if platform.system() == "Linux":
            try:
                for proc_entry in Path("/proc").glob("[0-9]*/cmdline"):
                    try:
                        cmd = proc_entry.read_bytes()
                        if b"gptokeyb" in cmd:
                            return True
                    except (PermissionError, FileNotFoundError, OSError):
                        continue
            except Exception:
                pass
        return False

    def _init_joysticks(self) -> None:
        """Initialize all connected SDL2 gamepads / joysticks."""
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        self.joysticks = []
        for i in range(count):
            try:
                joy = pygame.joystick.Joystick(i)
                joy.init()
                self.joysticks.append(joy)
                logger.info(
                    "Detected joystick #%d: %s (%d buttons, %d axes, %d hats)",
                    i, joy.get_name(), joy.get_numbuttons(), joy.get_numaxes(), joy.get_numhats(),
                )
            except Exception as e:
                logger.warning("Could not initialize joystick #%d: %s", i, e)

    def refresh_devices(self) -> None:
        """Check for newly connected or disconnected gamepads."""
        self.is_gptokeyb_active = self._check_gptokeyb()
        if not self.is_gptokeyb_active:
            self._init_joysticks()

    def _record_diag(self, button_label: str, action: str, raw_type: str, raw_detail: str) -> None:
        """Record input diagnostic info for live display in button test screen."""
        self.last_diag = {
            "button_label": button_label,
            "action": action,
            "raw_type": raw_type,
            "raw_detail": raw_detail,
            "timestamp": time.time(),
        }

    def _map_key(self, key: int) -> tuple[str | None, str]:
        """Map key to (action, button_label) based on active layout."""
        # Navigation
        if key == pygame.K_UP:
            return ACTION_UP, "D-Pad Hoch"
        elif key == pygame.K_DOWN:
            return ACTION_DOWN, "D-Pad Runter"
        elif key == pygame.K_LEFT:
            return ACTION_LEFT, "D-Pad Links"
        elif key == pygame.K_RIGHT:
            return ACTION_RIGHT, "D-Pad Rechts"

        # Scroll
        elif key in (pygame.K_w, pygame.K_PAGEUP):
            return ACTION_SCROLL_UP, "R-Stick Hoch / W"
        elif key in (pygame.K_s, pygame.K_PAGEDOWN):
            return ACTION_SCROLL_DOWN, "R-Stick Runter / S"

        # Shoulder Buttons
        elif key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS, pygame.K_r):
            return ACTION_UPVOTE, "R1 (Plus / Upvote)"
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS, pygame.K_e):
            return ACTION_DOWNVOTE, "L1 (Minus / Downvote)"
        elif key == pygame.K_t:
            return ACTION_TOGGLE_MODE, "L2/R2 (Beliebt / Neu)"

        # Face Buttons - Dependent on Button Layout
        # On PortMaster / gptokeyb with pr0.gptk:
        #   physical South sends K_RETURN
        #   physical East sends K_ESCAPE
        #   physical North sends K_TAB
        #   physical West sends K_i
        # Face Buttons - Dependent on Button Layout
        # Standard: A = Enter, B = ESC, X = i/x, Y = Tab/y
        # Inverted: B = Enter, A = ESC, Y = i/x, X = Tab/y
        if self.button_layout == "inverted":
            if key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_q):
                return ACTION_SELECT, "B (Bestätigen)"
            elif key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return ACTION_BACK, "A (Zurück)"
            elif key in (pygame.K_TAB, pygame.K_y):
                return ACTION_INFO, "Y (Info)"
            elif key in (pygame.K_i, pygame.K_x, pygame.K_c):
                return ACTION_TOGGLE_MODE, "X (Modus)"
        else:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                return ACTION_SELECT, "A (Öffnen / Bestätigen)"
            elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE, pygame.K_q):
                return ACTION_BACK, "B (Zurück)"
            elif key in (pygame.K_i, pygame.K_x, pygame.K_c):
                return ACTION_INFO, "X (Setup / Farben)"
            elif key in (pygame.K_TAB, pygame.K_y):
                return ACTION_TOGGLE_MODE, "Y (Beliebt / Neu)"

        return None, f"Key {key}"

    def map_event(self, event: pygame.event.Event) -> list[str]:
        """Map a single pygame event to zero or more discrete actions."""
        actions: list[str] = []

        # 1. Window close / Quit
        if event.type == pygame.QUIT:
            return [ACTION_QUIT]

        # 2. Joystick Connect / Disconnect
        if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self.refresh_devices()
            return actions

        # 3. Keyboard Input (Desktop test & gptokeyb)
        if event.type == pygame.KEYDOWN:
            act, btn_lbl = self._map_key(event.key)
            if act:
                actions.append(act)
                self._record_diag(btn_lbl, act, "KEYDOWN", pygame.key.name(event.key))
                self._held_actions[act] = time.time()
                self._last_repeat_times[act] = time.time()
            return actions

        elif event.type == pygame.KEYUP:
            act, _ = self._map_key(event.key)
            if act in self._held_actions:
                self._held_actions.pop(act, None)
                self._last_repeat_times.pop(act, None)
            return actions

        # 4. Native Gamepad Buttons
        if event.type == pygame.JOYBUTTONDOWN:
            btn = event.button
            act = None
            lbl = f"Button {btn}"

            if self.button_layout == "inverted":
                if btn == BTN_B:  # 1
                    act, lbl = ACTION_SELECT, "B (Bestätigen)"
                elif btn == BTN_A:  # 0
                    act, lbl = ACTION_BACK, "A (Zurück)"
                elif btn == BTN_Y:  # 3
                    act, lbl = ACTION_INFO, "Y (Info)"
                elif btn == BTN_X:  # 2
                    act, lbl = ACTION_TOGGLE_MODE, "X (Modus)"
            else:
                # Standard
                if btn == BTN_A:  # 0
                    act, lbl = ACTION_SELECT, "A (Öffnen / Bestätigen)"
                elif btn == BTN_B:  # 1
                    act, lbl = ACTION_BACK, "B (Zurück)"
                elif btn == BTN_X:  # 2
                    act, lbl = ACTION_INFO, "X (Setup / Farben)"
                elif btn == BTN_Y:  # 3
                    act, lbl = ACTION_TOGGLE_MODE, "Y (Beliebt / Neu)"

            if btn in (BTN_R1, 5):
                act, lbl = ACTION_UPVOTE, "R1"
            elif btn in (BTN_L1, 4):
                act, lbl = ACTION_DOWNVOTE, "L1"
            elif btn in (9, 10):
                act, lbl = ACTION_TOGGLE_MODE, f"L2/R2 (Button {btn})"
            elif btn == BTN_START:
                act, lbl = ACTION_SELECT, "START"
            elif btn == BTN_BACK:
                act, lbl = ACTION_BACK, "SELECT"

            # When gptokeyb is active, face buttons/d-pad/start/back are handled by gptokeyb key strokes.
            # Only shoulder buttons (L1/R1, L2/R2) are allowed as fallback here in case gptokeyb dropped them.
            if self.is_gptokeyb_active and act not in (ACTION_UPVOTE, ACTION_DOWNVOTE, ACTION_TOGGLE_MODE):
                return actions

            if act:
                actions.append(act)
                self._record_diag(lbl, act, "JOYBUTTONDOWN", f"Button {btn}")
                self._held_actions[act] = time.time()
                self._last_repeat_times[act] = time.time()

        elif event.type == pygame.JOYBUTTONUP:
            btn = event.button
            # Clear held button
            for act in (ACTION_SELECT, ACTION_BACK, ACTION_INFO, ACTION_TOGGLE_MODE, ACTION_UPVOTE, ACTION_DOWNVOTE):
                self._held_actions.pop(act, None)

        # 5. D-Pad Hats
        elif event.type == pygame.JOYHATMOTION:
            hat_x, hat_y = event.value
            # Clear previous hat directions
            for dir_act in (ACTION_LEFT, ACTION_RIGHT, ACTION_UP, ACTION_DOWN):
                self._held_actions.pop(dir_act, None)

            if hat_x == -1:
                actions.append(ACTION_LEFT)
                self._record_diag("D-Pad Links", ACTION_LEFT, "JOYHAT", "X=-1")
                self._held_actions[ACTION_LEFT] = time.time()
                self._last_repeat_times[ACTION_LEFT] = time.time()
            elif hat_x == 1:
                actions.append(ACTION_RIGHT)
                self._record_diag("D-Pad Rechts", ACTION_RIGHT, "JOYHAT", "X=1")
                self._held_actions[ACTION_RIGHT] = time.time()
                self._last_repeat_times[ACTION_RIGHT] = time.time()

            if hat_y == 1:
                actions.append(ACTION_UP)
                self._record_diag("D-Pad Hoch", ACTION_UP, "JOYHAT", "Y=1")
                self._held_actions[ACTION_UP] = time.time()
                self._last_repeat_times[ACTION_UP] = time.time()
            elif hat_y == -1:
                actions.append(ACTION_DOWN)
                self._record_diag("D-Pad Runter", ACTION_DOWN, "JOYHAT", "Y=-1")
                self._held_actions[ACTION_DOWN] = time.time()
                self._last_repeat_times[ACTION_DOWN] = time.time()

        # 6. Analog Sticks
        elif event.type == pygame.JOYAXISMOTION:
            axis = event.axis
            val = event.value

            if axis == 0:
                self.stick_lx = val
            elif axis == 1:
                self.stick_ly = val
            elif axis in (3, 4):
                self.stick_ry = val

            # Update stick hold states
            joy_id = event.instance_id if hasattr(event, "instance_id") else event.joy
            state = 0
            if val < -self.axis_threshold:
                state = -1
            elif val > self.axis_threshold:
                state = 1

            prev_state = self._axis_states.get((joy_id, axis), 0)
            self._axis_states[(joy_id, axis)] = state

            # Trigger discrete action on transition from neutral
            if state != prev_state and state != 0:
                if axis == 0:  # Left Stick X
                    act = ACTION_LEFT if state == -1 else ACTION_RIGHT
                    lbl = "L-Stick Links" if state == -1 else "L-Stick Rechts"
                    actions.append(act)
                    self._record_diag(lbl, act, "JOYAXIS", f"Axis 0 = {val:.2f}")
                    self._held_actions[act] = time.time()
                    self._last_repeat_times[act] = time.time()
                elif axis == 1:  # Left Stick Y
                    act = ACTION_UP if state == -1 else ACTION_DOWN
                    lbl = "L-Stick Hoch" if state == -1 else "L-Stick Runter"
                    actions.append(act)
                    self._record_diag(lbl, act, "JOYAXIS", f"Axis 1 = {val:.2f}")
                    self._held_actions[act] = time.time()
                    self._last_repeat_times[act] = time.time()
                elif axis in (3, 4):  # Right Stick Y
                    act = ACTION_SCROLL_UP if state == -1 else ACTION_SCROLL_DOWN
                    lbl = "R-Stick Hoch" if state == -1 else "R-Stick Runter"
                    actions.append(act)
                    self._record_diag(lbl, act, "JOYAXIS", f"Axis {axis} = {val:.2f}")
                    self._held_actions[act] = time.time()
                    self._last_repeat_times[act] = time.time()
            elif state == 0:
                # Returned to neutral: remove from held actions
                if axis == 0:
                    self._held_actions.pop(ACTION_LEFT, None)
                    self._held_actions.pop(ACTION_RIGHT, None)
                elif axis == 1:
                    self._held_actions.pop(ACTION_UP, None)
                    self._held_actions.pop(ACTION_DOWN, None)
                elif axis in (3, 4):
                    self._held_actions.pop(ACTION_SCROLL_UP, None)
                    self._held_actions.pop(ACTION_SCROLL_DOWN, None)

        return actions

    def poll_actions(self) -> list[str]:
        """Poll and return input actions, generating smooth autorepeat when holding buttons or sticks."""
        raw_actions: list[str] = []
        self.last_key_events.clear()
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                self.last_key_events.append(event)
            mapped = self.map_event(event)
            raw_actions.extend(mapped)

        now = time.time()
        filtered_actions: list[str] = []

        # Process discrete incoming actions with debounce
        for act in raw_actions:
            if act == ACTION_QUIT:
                filtered_actions.append(act)
                continue

            # Navigation debounce on first strike
            if act in (ACTION_UP, ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT):
                last = self._last_action_times.get(act, 0.0)
                if now - last < 0.10:
                    continue
                self._last_action_times[act] = now

            # Button action debounce
            elif act in (ACTION_SELECT, ACTION_BACK, ACTION_INFO, ACTION_TOGGLE_MODE, ACTION_UPVOTE, ACTION_DOWNVOTE):
                last = self._last_action_times.get(act, 0.0)
                if now - last < 0.22:
                    continue
                self._last_action_times[act] = now

            filtered_actions.append(act)

        # Autorepeat for held directions / sticks (Smooth continuous scrolling!)
        # Initial hold delay: 220ms, repeat interval: 70ms
        REPEATABLE_ACTIONS = (
            ACTION_UP,
            ACTION_DOWN,
            ACTION_LEFT,
            ACTION_RIGHT,
            ACTION_SCROLL_UP,
            ACTION_SCROLL_DOWN,
        )
        for act in REPEATABLE_ACTIONS:
            if act in self._held_actions:
                press_t = self._held_actions[act]
                last_rep = self._last_repeat_times.get(act, press_t)
                if (now - press_t >= 0.22) and (now - last_rep >= 0.07):
                    filtered_actions.append(act)
                    self._last_repeat_times[act] = now

        return filtered_actions

    def get_continuous_scroll_y(self) -> float:
        """Return continuous vertical scroll factor (-1.0 to +1.0) for analog sticks or held keys."""
        # 1. Analog Stick Y has priority for smooth proportional scrolling
        if abs(self.stick_ry) > self.axis_threshold:
            return self.stick_ry
        if abs(self.stick_ly) > self.axis_threshold:
            return self.stick_ly

        # 2. Held keys fallback
        if ACTION_DOWN in self._held_actions or ACTION_SCROLL_DOWN in self._held_actions:
            return 1.0
        if ACTION_UP in self._held_actions or ACTION_SCROLL_UP in self._held_actions:
            return -1.0

        return 0.0

    def clear_events(self) -> None:
        """Purge any remaining SDL events and reset input cooldowns."""
        pygame.event.clear()
        self._last_action_times.clear()
        self._held_actions.clear()
        self._last_repeat_times.clear()
        self._axis_states.clear()
