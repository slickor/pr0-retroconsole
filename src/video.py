"""Cross-platform Video Playback for pr0-retroconsole.

Sprache: Deutsch (pr0-Amtssprache) • Architektur: 100% zertifizierter Vibecode.
Supports:
1. Inline Video Playback directly inside Pygame Post-View using ffmpeg frame streaming.
2. External Fullscreen / Windowed Playback using mpv, ffplay, or VLC with clean SDL2 transitions.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
import pygame

import struct

logger = logging.getLogger("pr0.video")

# Keybindings for mpv input configuration (Standard Nintendo layout: A=East=Play/Pause, B=South=Quit)
MPV_INPUT_CONF_CONTENT = """# pr0-retroconsole mpv controls
# Seeking controls (10% jumps with visual OSD progress bar)
RIGHT osd-msg-bar seek 10 relative-percent
LEFT osd-msg-bar seek -10 relative-percent
right osd-msg-bar seek 10 relative-percent
left osd-msg-bar seek -10 relative-percent
GAMEPAD_ACTION_RIGHT osd-msg-bar seek 10 relative-percent
GAMEPAD_ACTION_LEFT osd-msg-bar seek -10 relative-percent
BTN_DPAD_RIGHT osd-msg-bar seek 10 relative-percent
BTN_DPAD_LEFT osd-msg-bar seek -10 relative-percent

# Playback controls (A button on Nintendo / East / Enter)
SPACE cycle pause
ENTER cycle pause
a cycle pause
A cycle pause
GAMEPAD_ACTION_RIGHT cycle pause
BTN_EAST cycle pause
BTN_B cycle pause
JOY_BTN1 cycle pause
JOY_B cycle pause

# Quit controls (B button on Nintendo / South / Escape)
b quit
B quit
esc quit
ESC quit
q quit
Q quit
backspace quit
BACKSPACE quit
GAMEPAD_ACTION_DOWN quit
GAMEPAD_BACK quit
BTN_SOUTH quit
BTN_A quit
BTN_SELECT quit
BTN_START cycle pause
JOY_BTN0 quit
JOY_A quit
"""

_DURATION_CACHE: dict[str, float] = {}


def parse_mp4_duration(data: bytes) -> float | None:
    """Extract duration in seconds from MP4 mvhd atom in raw bytes."""
    idx = data.find(b"mvhd")
    if idx != -1 and len(data) >= idx + 36:
        version = data[idx + 4]
        if version == 0:
            timescale, duration = struct.unpack(">II", data[idx + 16 : idx + 24])
            if timescale > 0:
                return duration / timescale
        elif version == 1:
            timescale = struct.unpack(">I", data[idx + 24 : idx + 28])[0]
            duration = struct.unpack(">Q", data[idx + 28 : idx + 36])[0]
            if timescale > 0:
                return duration / timescale
    return None


def parse_webm_duration(data: bytes) -> float | None:
    """Extract duration in seconds from WebM Segment Info Duration element."""
    idx = data.find(b"\x44\x89")
    if idx != -1 and len(data) >= idx + 10:
        size = data[idx + 2]
        if size == 4:
            return struct.unpack(">f", data[idx + 3 : idx + 7])[0] / 1000.0
        elif size == 8:
            return struct.unpack(">d", data[idx + 3 : idx + 11])[0] / 1000.0
    return None


def get_video_duration(url: str, cookie_header: str | None = None) -> float:
    """Determine video duration in seconds with caching and low latency."""
    if not url:
        return 0.0

    if url in _DURATION_CACHE:
        return _DURATION_CACHE[url]

    # 1. Check local file on disk
    if os.path.isfile(url):
        try:
            with open(url, "rb") as f:
                head = f.read(131072)
            d = parse_mp4_duration(head) or parse_webm_duration(head)
            if d and d > 0:
                _DURATION_CACHE[url] = round(d, 2)
                return _DURATION_CACHE[url]
        except Exception:
            pass

    # 2. Remote HTTP URL (Range request for first 64KB)
    if url.startswith("http"):
        try:
            import requests

            headers = {"Range": "bytes=0-65535"}
            if cookie_header:
                headers["Cookie"] = cookie_header
            resp = requests.get(url, headers=headers, timeout=2.0)
            if resp.status_code in (200, 206) and resp.content:
                d = parse_mp4_duration(resp.content) or parse_webm_duration(resp.content)
                if d and d > 0:
                    _DURATION_CACHE[url] = round(d, 2)
                    return _DURATION_CACHE[url]
        except Exception:
            pass

    return 0.0



def get_handheld_env(binary_path: str | None = None) -> dict[str, str]:
    """Build process environment with LD_LIBRARY_PATH pointing to handheld system/app libraries."""
    env = os.environ.copy()
    # Remove LD_PRELOAD so external subprocesses (mpv, ffplay) are not forced to link against Pygame's patched SDL2
    env.pop("LD_PRELOAD", None)
    if platform.system() == "Linux":
        lib_candidates = [
            "/mnt/SDCARD/System/lib",
            "/mnt/sdcard/System/lib",
            "/mnt/SDCARD/Apps/PortMaster/PortMaster",
            "/mnt/sdcard/Apps/PortMaster/PortMaster",
            "/opt/system/Tools/PortMaster",
            "/roms/ports/PortMaster",
            "/usr/trimui/lib",
            "/usr/lib",
            "/lib",
        ]
        if binary_path:
            p_dir = str(Path(binary_path).parent)
            lib_candidates.insert(0, p_dir)
            p_lib = str(Path(binary_path).parent / "lib")
            lib_candidates.insert(1, p_lib)

        valid_libs = [p for p in lib_candidates if Path(p).is_dir()]
        existing = env.get("LD_LIBRARY_PATH")
        if existing:
            valid_libs.append(existing)
        env["LD_LIBRARY_PATH"] = ":".join(valid_libs)
    return env


def build_cookie_header(me_cookie: str | None, av_cookie: str | None = None) -> str:
    """Build RFC 6265 Cookie header string containing me and av cookies."""
    parts = []
    if me_cookie:
        c = me_cookie.strip()
        if c.startswith("me="):
            c = c[3:].strip()
        if c:
            parts.append(f"me={c}")
    if av_cookie:
        a = av_cookie.strip()
        if a.startswith("av="):
            a = a[3:].strip()
        if a:
            parts.append(f"av={a}")
    return "; ".join(parts)


class InlineVideoPlayer:
    """Decodes video frames in a background thread for direct embedded playback in Pygame,
    with an accompanying background audio stream for sound in post-view.
    """

    def __init__(
        self,
        preferred_ffmpeg: str | None = None,
        video_player: VideoPlayer | None = None,
        enable_audio: bool = True,
        me_cookie: str | None = None,
        av_cookie: str | None = None,
    ):
        self.preferred_ffmpeg = preferred_ffmpeg
        self.video_player = video_player
        self.enable_audio = enable_audio
        self.me_cookie = me_cookie
        self.av_cookie = av_cookie
        self.system = platform.system()
        self.ffmpeg_bin = self._find_ffmpeg()

        self._running = False
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None
        self._audio_proc: subprocess.Popen | None = None
        self._current_frame: pygame.Surface | None = None
        self._lock = threading.Lock()
        self._active_url: str | None = None
        self._duration: float = 0.0
        self._start_time: float = 0.0

    def set_cookie(self, me_cookie: str | None, av_cookie: str | None = None) -> None:
        """Update authentication and age-verification cookies for media streaming."""
        self.me_cookie = me_cookie
        self.av_cookie = av_cookie

        logger.info(
            "InlineVideoPlayer init: ffmpeg=%s, audio_enabled=%s",
            self.ffmpeg_bin,
            self.enable_audio,
        )

    def _find_ffmpeg(self) -> str | None:
        """Locate ffmpeg executable."""
        if self.preferred_ffmpeg and Path(self.preferred_ffmpeg).is_file():
            return str(Path(self.preferred_ffmpeg).resolve())
        if self.preferred_ffmpeg and shutil.which(self.preferred_ffmpeg):
            return shutil.which(self.preferred_ffmpeg)

        # Check local project bin
        project_root = Path(__file__).resolve().parent.parent
        bin_dir = project_root / "bin"
        local_bin = bin_dir / ("ffmpeg.exe" if self.system == "Windows" else "ffmpeg")
        if local_bin.is_file():
            return str(local_bin.resolve())

        # Check system PATH
        which_cmd = shutil.which("ffmpeg")
        if which_cmd:
            return which_cmd

        # Check known Windows locations
        if self.system == "Windows":
            candidates = [
                Path(r"C:\Program Files\Fred TV\deps\ffmpeg.exe"),
                Path(r"C:\tools\ffmpeg\bin\ffmpeg.exe"),
                Path(os.path.expanduser(r"~\scoop\shims\ffmpeg.exe")),
            ]
            for c in candidates:
                if c.is_file():
                    return str(c.resolve())

        if self.system == "Linux":
            candidates = [
                Path("/mnt/SDCARD/System/bin/ffmpeg"),
                Path("/mnt/sdcard/System/bin/ffmpeg"),
                Path("/mnt/SDCARD/Apps/ffmpeg/ffmpeg"),
                Path("/mnt/sdcard/Apps/ffmpeg/ffmpeg"),
                Path("/mnt/SDCARD/Apps/Player/ffmpeg"),
                Path("/mnt/sdcard/Apps/Player/ffmpeg"),
                Path("/mnt/SDCARD/Apps/player/ffmpeg"),
                Path("/mnt/sdcard/Apps/player/ffmpeg"),
                Path("/mnt/SDCARD/System/usr/bin/ffmpeg"),
                Path("/mnt/sdcard/System/usr/bin/ffmpeg"),
                Path("/mnt/SDCARD/System/usr/trimui/bin/ffmpeg"),
                Path("/mnt/sdcard/System/usr/trimui/bin/ffmpeg"),
                Path("/usr/bin/ffmpeg"),
                Path("/usr/local/bin/ffmpeg"),
                Path("/usr/trimui/bin/ffmpeg"),
                Path("/opt/system/Tools/PortMaster/tools/ffmpeg"),
                Path("/opt/tools/ffmpeg"),
                Path("/roms/ports/PortMaster/tools/ffmpeg"),
                Path("/roms/tools/PortMaster/tools/ffmpeg"),
            ]
            for c in candidates:
                if c.is_file() and os.access(c, os.X_OK):
                    return str(c.resolve())

        return None

    @property
    def is_available(self) -> bool:
        return self.ffmpeg_bin is not None

    def _start_audio(self, url: str) -> None:
        """Launch background audio playback companion process."""
        if not self.enable_audio:
            return

        player = self.video_player
        if not player or not player.has_player() or not player.player_path:
            logger.debug("No video player available for inline audio companion")
            return

        cookie_hdr = build_cookie_header(self.me_cookie, self.av_cookie)
        cmd: list[str] = []
        if player.player_type == "mpv":
            cmd = [
                player.player_path,
                "--no-video",
                "--loop-file=inf",
                "--terminal=no",
                "--really-quiet",
                "--volume=100",
            ]
            if player.is_handheld:
                cmd.extend(["--ao=alsa,oss,sdl"])
            if cookie_hdr and url.startswith("http"):
                cmd.extend([f"--http-header-fields=Cookie: {cookie_hdr}"])
            cmd.append(url)
        elif player.player_type == "ffplay":
            cmd = [
                player.player_path,
                "-nodisp",
                "-loop", "0",
                "-loglevel", "quiet",
            ]
            if cookie_hdr and url.startswith("http"):
                cmd.extend(["-headers", f"Cookie: {cookie_hdr}\r\n"])
            cmd.append(url)
        elif player.player_type == "vlc":
            cmd = [
                player.player_path,
                "--intf", "dummy",
                "--no-video",
                "--loop",
                url,
            ]
        else:
            return

        env = get_handheld_env(player.player_path)
        try:
            logger.info("Starting inline audio companion: %s", " ".join(cmd))
            self._audio_proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                env=env,
            )
        except Exception as e:
            logger.warning("Failed to start inline audio companion: %s", e)
            self._audio_proc = None

    def _stop_audio(self) -> None:
        """Terminate background audio playback companion."""
        if self._audio_proc:
            try:
                self._audio_proc.terminate()
                self._audio_proc.wait(timeout=0.15)
            except Exception:
                try:
                    self._audio_proc.kill()
                except Exception:
                    pass
            self._audio_proc = None

    def play_inline(self, url: str, width: int = 480, height: int = 270) -> bool:
        """Start streaming frames from video URL in a background thread with audio companion."""
        if not self.is_available or not url:
            return False

        if self._active_url == url and self._running:
            return True

        self.stop()

        # Ensure dimensions are even (required by ffmpeg rawvideo)
        w = width if width % 2 == 0 else width - 1
        h = height if height % 2 == 0 else height - 1
        w = max(100, w)
        h = max(60, h)

        self._active_url = url
        self._running = True
        self._start_time = time.time()
        self._duration = get_video_duration(url, build_cookie_header(self.me_cookie, self.av_cookie))

        # Start audio companion
        if self.enable_audio:
            self._start_audio(url)

        self._thread = threading.Thread(
            target=self._stream_worker,
            args=(url, w, h),
            daemon=True,
        )
        self._thread.start()
        return True

    def _stream_worker(self, url: str, width: int, height: int) -> None:
        is_local = os.path.isfile(url)
        cmd = [
            self.ffmpeg_bin,
            "-loglevel", "error",
        ]
        cookie_hdr = build_cookie_header(self.me_cookie, self.av_cookie)
        if cookie_hdr and url.startswith("http"):
            cmd.extend(["-headers", f"Cookie: {cookie_hdr}\r\n"])

        if is_local:
            cmd.extend(["-re", "-stream_loop", "-1"])

        cmd.extend([
            "-i", url,
            "-threads", "2",
            "-f", "rawvideo",
            "-pix_fmt", "rgb24",
            "-s", f"{width}x{height}",
            "-r", "25",
            "-",
        ])

        frame_bytes = width * height * 3
        frame_interval = 1.0 / 25.0

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=frame_bytes * 2,
                env=get_handheld_env(self.ffmpeg_bin),
            )
        except Exception as e:
            logger.error("Failed to start inline ffmpeg stream: %s", e)
            self._running = False
            return

        while self._running:
            t_start = time.time()
            try:
                raw = self._proc.stdout.read(frame_bytes)
                if len(raw) < frame_bytes:
                    err_msg = ""
                    if self._proc and self._proc.stderr:
                        try:
                            err_msg = self._proc.stderr.read().decode("utf-8", errors="replace")
                        except Exception:
                            pass
                    if err_msg.strip():
                        logger.warning("Inline ffmpeg stream error: %s", err_msg.strip()[:250])
                    break
                surf = pygame.image.frombuffer(raw, (width, height), "RGB")
                with self._lock:
                    self._current_frame = surf
            except Exception as e:
                logger.debug("Inline video read error: %s", e)
                break

            elapsed = time.time() - t_start
            sleep_time = max(0.001, frame_interval - elapsed)
            time.sleep(sleep_time)

        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

    def get_current_frame(self) -> pygame.Surface | None:
        """Thread-safe retrieval of latest video frame."""
        with self._lock:
            return self._current_frame

    def get_progress(self) -> float:
        """Returns playback progress as a float between 0.0 and 1.0."""
        if not self._running or self._duration <= 0:
            return 0.0
        elapsed = (time.time() - self._start_time) % self._duration
        return min(1.0, max(0.0, elapsed / self._duration))

    def stop(self) -> None:
        """Terminate the active stream and audio companion."""
        self._running = False
        self._active_url = None
        self._stop_audio()
        if self._proc:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.4)
        self._thread = None
        with self._lock:
            self._current_frame = None


class VideoPlayer:
    """Handles external video playback using mpv, ffplay, or vlc with graceful fallbacks."""

    def __init__(
        self,
        preferred_player: str | None = None,
        button_layout: str = "standard",
        me_cookie: str | None = None,
        av_cookie: str | None = None,
    ):
        self.preferred_player = preferred_player
        self.button_layout = button_layout
        self.me_cookie = me_cookie
        self.av_cookie = av_cookie
        self.system = platform.system()
        self.machine = platform.machine().lower()

        self.is_handheld = self._detect_handheld()
        self.player_type: str | None = None
        self.player_path: str | None = None
        self._resolve_player()

        self.input_conf_path = self._ensure_input_conf()

    def set_cookie(self, me_cookie: str | None, av_cookie: str | None = None) -> None:
        """Update authentication and age-verification cookies."""
        self.me_cookie = me_cookie
        self.av_cookie = av_cookie

        logger.info(
            "VideoPlayer init: system=%s, machine=%s, is_handheld=%s, type=%s, path=%s",
            self.system,
            self.machine,
            self.is_handheld,
            self.player_type,
            self.player_path,
        )

    def _detect_handheld(self) -> bool:
        """Detect if running on an ARM handheld (ArkOS, CrossMix OS, R36S, TrimUI)."""
        if self.system != "Linux":
            return False
        arm_indicators = ("aarch64", "armv7l", "armv8l", "arm")
        return any(self.machine.startswith(prefix) for prefix in arm_indicators)

    def _resolve_player(self) -> None:
        """Find suitable player executable, checking project bin, PATH, and standard system paths."""
        # 1. Check user preference from config
        if self.preferred_player:
            pref = Path(self.preferred_player)
            if pref.is_file():
                self.player_path = str(pref.resolve())
                self.player_type = self._identify_player_type(self.player_path)
                return
            which_pref = shutil.which(self.preferred_player)
            if which_pref:
                self.player_path = which_pref
                self.player_type = self._identify_player_type(which_pref)
                return

        # 2. Check local project bin/ folder
        project_root = Path(__file__).resolve().parent.parent
        bin_dir = project_root / "bin"
        local_candidates = [
            ("mpv", bin_dir / ("mpv.exe" if self.system == "Windows" else "mpv")),
            ("ffplay", bin_dir / ("ffplay.exe" if self.system == "Windows" else "ffplay")),
            ("vlc", bin_dir / ("vlc.exe" if self.system == "Windows" else "vlc")),
        ]
        for ptype, ppath in local_candidates:
            if ppath.is_file():
                self.player_path = str(ppath.resolve())
                self.player_type = ptype
                return

        # 3. Check system PATH
        for ptype in ("mpv", "ffplay", "vlc"):
            which_cmd = shutil.which(ptype)
            if which_cmd:
                self.player_path = which_cmd
                self.player_type = ptype
                return

        # 4. Windows standard install locations
        if self.system == "Windows":
            win_candidates = [
                # mpv paths
                ("mpv", Path(r"C:\Program Files\Fred TV\deps\mpv.exe")),
                ("mpv", Path(r"C:\Program Files\mpv\mpv.exe")),
                ("mpv", Path(r"C:\Program Files (x86)\mpv\mpv.exe")),
                ("mpv", Path(r"C:\tools\mpv\mpv.exe")),
                ("mpv", Path(r"C:\ProgramData\chocolatey\bin\mpv.exe")),
                ("mpv", Path(os.path.expanduser(r"~\scoop\shims\mpv.exe"))),
                # ffplay paths
                ("ffplay", Path(r"C:\tools\ffmpeg\bin\ffplay.exe")),
                ("ffplay", Path(os.path.expanduser(r"~\scoop\shims\ffplay.exe"))),
                # vlc paths
                ("vlc", Path(r"C:\Program Files\VideoLAN\VLC\vlc.exe")),
                ("vlc", Path(r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe")),
            ]
            for ptype, ppath in win_candidates:
                if ppath.is_file():
                    self.player_path = str(ppath.resolve())
                    self.player_type = ptype
                    return

        # 5. Linux / Handheld standard paths
        if self.system == "Linux":
            linux_candidates = [
                # TrimUI Smart Pro / CrossMix-OS standard mpv paths
                ("mpv", Path("/mnt/SDCARD/System/bin/mpv")),
                ("mpv", Path("/mnt/sdcard/System/bin/mpv")),
                ("mpv", Path("/mnt/SDCARD/Apps/mpv/mpv")),
                ("mpv", Path("/mnt/sdcard/Apps/mpv/mpv")),
                ("mpv", Path("/mnt/SDCARD/Apps/Player/mpv")),
                ("mpv", Path("/mnt/sdcard/Apps/Player/mpv")),
                ("mpv", Path("/mnt/SDCARD/Apps/player/mpv")),
                ("mpv", Path("/mnt/sdcard/Apps/player/mpv")),
                ("mpv", Path("/mnt/SDCARD/Emus/VIDEOS/mpv")),
                ("mpv", Path("/mnt/sdcard/Emus/VIDEOS/mpv")),
                ("mpv", Path("/mnt/SDCARD/System/usr/bin/mpv")),
                ("mpv", Path("/mnt/sdcard/System/usr/bin/mpv")),
                ("mpv", Path("/mnt/SDCARD/System/usr/trimui/bin/mpv")),
                ("mpv", Path("/mnt/sdcard/System/usr/trimui/bin/mpv")),
                ("mpv", Path("/usr/bin/mpv")),
                ("mpv", Path("/usr/local/bin/mpv")),
                ("mpv", Path("/usr/trimui/bin/mpv")),
                ("mpv", Path("/opt/system/Tools/PortMaster/tools/mpv")),
                ("mpv", Path("/opt/tools/mpv")),
                ("mpv", Path("/roms/ports/PortMaster/tools/mpv")),
                ("mpv", Path("/roms/tools/PortMaster/tools/mpv")),
                # ffplay candidates
                ("ffplay", Path("/mnt/SDCARD/System/bin/ffplay")),
                ("ffplay", Path("/mnt/sdcard/System/bin/ffplay")),
                ("ffplay", Path("/mnt/SDCARD/Apps/ffmpeg/ffplay")),
                ("ffplay", Path("/mnt/sdcard/Apps/ffmpeg/ffplay")),
                ("ffplay", Path("/usr/bin/ffplay")),
                ("ffplay", Path("/usr/local/bin/ffplay")),
                ("ffplay", Path("/opt/system/Tools/PortMaster/tools/ffplay")),
                ("ffplay", Path("/roms/ports/PortMaster/tools/ffplay")),
                ("vlc", Path("/usr/bin/cvlc")),
                ("vlc", Path("/usr/bin/vlc")),
            ]
            for ptype, ppath in linux_candidates:
                if ppath.is_file() and os.access(ppath, os.X_OK):
                    self.player_path = str(ppath.resolve())
                    self.player_type = ptype
                    return

    def _identify_player_type(self, path: str) -> str:
        """Extract player type from filename."""
        name = Path(path).stem.lower()
        if "mpv" in name:
            return "mpv"
        if "ffplay" in name:
            return "ffplay"
        if "vlc" in name:
            return "vlc"
        return "mpv"

    @property
    def player_bin(self) -> str | None:
        """Compatibility property returning player type or None."""
        return self.player_type

    def has_player(self) -> bool:
        """Return True if an executable video player is available."""
        return self.player_path is not None and self.player_type is not None

    def _generate_mpv_input_conf(self) -> str:
        """Generate mpv input bindings matching active button layout."""
        if self.button_layout == "inverted":
            # Inverted (Xbox style: B=Play/Pause, A=Quit/Back)
            play_action = "GAMEPAD_ACTION_RIGHT"
            quit_action = "GAMEPAD_ACTION_DOWN"
            play_btn = "GAMEPAD_B"
            quit_btn = "GAMEPAD_A"
            key_play = "b cycle pause\nB cycle pause"
            key_quit = "a quit\nA quit"
        else:
            # Standard (Nintendo / TrimUI / Knulli / ArkOS: A=Play/Pause, B=Quit/Back)
            play_action = "GAMEPAD_ACTION_DOWN"
            quit_action = "GAMEPAD_ACTION_RIGHT"
            play_btn = "GAMEPAD_A"
            quit_btn = "GAMEPAD_B"
            key_play = "a cycle pause\nA cycle pause"
            key_quit = "b quit\nB quit"

        return f"""# pr0-retroconsole mpv controls ({self.button_layout})
# Seeking controls (10% and 30% jumps with visual OSD progress bar)
RIGHT osd-msg-bar seek 10 relative-percent
LEFT osd-msg-bar seek -10 relative-percent
UP osd-msg-bar seek 30 relative-percent
DOWN osd-msg-bar seek -30 relative-percent
GAMEPAD_DPAD_RIGHT osd-msg-bar seek 10 relative-percent
GAMEPAD_DPAD_LEFT osd-msg-bar seek -10 relative-percent
GAMEPAD_DPAD_UP osd-msg-bar seek 30 relative-percent
GAMEPAD_DPAD_DOWN osd-msg-bar seek -30 relative-percent
GAMEPAD_RIGHT_SHOULDER osd-msg-bar seek 10 relative-percent
GAMEPAD_LEFT_SHOULDER osd-msg-bar seek -10 relative-percent

# Playback controls
SPACE cycle pause
ENTER cycle pause
{key_play}
{play_btn} cycle pause
{play_action} cycle pause

# Quit controls
ESC quit
esc quit
q quit
Q quit
BS quit
{key_quit}
{quit_btn} quit
{quit_action} quit
GAMEPAD_BACK quit
GAMEPAD_MENU quit
GAMEPAD_START cycle pause
"""

    def _ensure_input_conf(self) -> Path:
        """Ensure pr0_mpv_input.conf exists with custom keybindings matching active layout."""
        conf_content = self._generate_mpv_input_conf()
        candidates = [
            Path("./pr0_mpv_input.conf"),
            Path("/tmp/pr0_mpv_input.conf"),
            Path(tempfile.gettempdir()) / "pr0_mpv_input.conf",
        ]
        for p in candidates:
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(conf_content, encoding="utf-8")
                return p.resolve()
            except Exception as e:
                logger.warning("Could not write mpv input conf to %s: %s", p, e)

        fallback = Path("./pr0_mpv_input.conf")
        fallback.write_text(conf_content, encoding="utf-8")
        return fallback.resolve()

    def play(self, media_url: str, width: int = 640, height: int = 480) -> bool:
        """Launch video in external player and manage clean transition back to Pygame.

        :param media_url: Full URL or file path of video (.mp4, .webm)
        :param width: Target viewport width
        :param height: Target viewport height
        :return: True if playback started and completed successfully, False if no player found.
        """
        if not self.has_player() or not self.player_path:
            logger.warning("No video player found. Cannot play %s", media_url)
            return False

        cmd: list[str] = []
        cookie_hdr = build_cookie_header(self.me_cookie, self.av_cookie)
        duration = get_video_duration(media_url, cookie_hdr)
        seek_step = max(0.5, round(duration * 0.1, 2)) if duration > 0 else 2.0

        if self.player_type == "mpv":
            conf_arg = f"--input-conf={self.input_conf_path}"

            if self.is_handheld:
                # Ensure ALSA sound hardware device is completely free for mpv
                try:
                    if pygame.mixer.get_init():
                        pygame.mixer.quit()
                except Exception:
                    pass

                # Fullscreen playback for TrimUI Smart Pro, R36S, ArkOS, Knulli, muOS
                # Using --vo=sdl,gpu with --input-gamepad=no:
                # 1. vo_sdl natively binds to Mali FBDEV (TrimUI) or KMSDRM (ArkOS) via system SDL2
                # 2. --input-gamepad=no prevents SDL joystick conflict with vo_sdl ('Another component is using SDL')
                # 3. gptokeyb handles gamepad controls cleanly via keyboard emulation
                cmd = [
                    self.player_path,
                    "--fs",
                    "--hwdec=no",
                    "--vo=sdl,gpu",
                    "--ao=alsa,oss,sdl",
                    "--volume=100",
                    "--video-sync=audio",
                    "--framedrop=yes",
                    "--cache=yes",
                    "--demuxer-max-bytes=30M",
                    "--demuxer-readahead-secs=8",
                    "--loop-file=inf",
                    "--input-terminal=yes",
                    "--input-gamepad=no",
                    "--msg-level=all=warn",
                    "--osd-level=1",
                    "--osd-bar=yes",
                    "--osd-on-seek=bar",
                    "--osd-duration=1500",
                    "--osd-bar-align-y=1",
                    "--osd-bar-h=1.5",
                    "--osd-color=#EE4D2D",
                    conf_arg,
                ]
                if cookie_hdr and media_url.startswith("http"):
                    cmd.append(f"--http-header-fields=Cookie: {cookie_hdr}")
                cmd.append(media_url)
            else:
                # Windowed desktop/macOS/Windows playback sized to active display resolution
                cmd = [
                    self.player_path,
                    f"--geometry={width}x{height}",
                    "--loop-file=inf",
                    "--force-window=immediate",
                    "--input-terminal=yes",
                    "--input-gamepad=yes",
                    "--really-quiet",
                    "--osd-level=1",
                    "--osd-bar=yes",
                    "--osd-on-seek=bar",
                    "--osd-duration=1500",
                    "--osd-bar-align-y=1",
                    "--osd-bar-h=1.5",
                    "--osd-color=#EE4D2D",
                    conf_arg,
                ]
                if cookie_hdr and media_url.startswith("http"):
                    cmd.append(f"--http-header-fields=Cookie: {cookie_hdr}")
                cmd.append(media_url)
        elif self.player_type == "ffplay":
            if self.is_handheld:
                try:
                    if pygame.mixer.get_init():
                        pygame.mixer.quit()
                except Exception:
                    pass

                cmd = [
                    self.player_path,
                    "-x",
                    str(width),
                    "-y",
                    str(height),
                    "-fs",
                    "-noborder",
                    "-loop",
                    "0",
                    "-loglevel",
                    "error",
                    "-seek_interval",
                    str(seek_step),
                ]
                if duration > 0:
                    vf_filter = (
                        f"drawbox=x=0:y=ih-6:w=iw:h=6:color=black@0.6:t=fill,"
                        f"drawbox=x=0:y=ih-6:w=iw*min(1\\,max(0\\,t/{duration:.2f})):h=6:color=0xEE4D2D:t=fill"
                    )
                    cmd.extend(["-vf", vf_filter])
                if cookie_hdr and media_url.startswith("http"):
                    cmd.extend(["-headers", f"Cookie: {cookie_hdr}\r\n"])
                cmd.append(media_url)
            else:
                cmd = [
                    self.player_path,
                    "-x",
                    str(width),
                    "-y",
                    str(height),
                    "-noborder",
                    "-loop",
                    "0",
                    "-window_title",
                    "pr0 video",
                    "-seek_interval",
                    str(seek_step),
                ]
                if duration > 0:
                    vf_filter = (
                        f"drawbox=x=0:y=ih-6:w=iw:h=6:color=black@0.6:t=fill,"
                        f"drawbox=x=0:y=ih-6:w=iw*min(1\\,max(0\\,t/{duration:.2f})):h=6:color=0xEE4D2D:t=fill"
                    )
                    cmd.extend(["-vf", vf_filter])
                if cookie_hdr and media_url.startswith("http"):
                    cmd.extend(["-headers", f"Cookie: {cookie_hdr}\r\n"])
                cmd.append(media_url)
        elif self.player_type == "vlc":
            if self.is_handheld:
                cmd = [
                    self.player_path,
                    "--fullscreen",
                    "--no-video-title-show",
                    "--loop",
                    media_url,
                ]
            else:
                cmd = [
                    self.player_path,
                    f"--width={width}",
                    f"--height={height}",
                    "--no-video-title-show",
                    "--loop",
                    media_url,
                ]

        env = get_handheld_env(self.player_path)
        logger.info("Executing video player: %s", " ".join(cmd))

        # Determine back button index and keys based on active layout
        if self.button_layout == "inverted":
            # Inverted (Xbox style): B = Play, A = Back
            back_btn = 1
            back_keys = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_a, pygame.K_q)
        else:
            # Standard (Nintendo / TrimUI / Knulli / ArkOS): A = Play, B = Back
            back_btn = 0
            back_keys = (pygame.K_ESCAPE, pygame.K_b, pygame.K_q, pygame.K_BACKSPACE)

        # On Linux handhelds with exclusive display layers (Mali / KMSDRM), temporarily release Pygame display
        # so mpv has exclusive hardware access to the screen
        had_display = False
        if self.is_handheld and self.system == "Linux":
            try:
                logger.info("Temporarily releasing Pygame display for fullscreen video player...")
                pygame.display.quit()
                had_display = True
            except Exception as e:
                logger.debug("Failed to release display: %s", e)

        try:
            # Run player and monitor for exit
            p = subprocess.Popen(cmd, env=env)
            if had_display:
                # On handheld with exclusive display, mpv has full screen control and handles its own inputs
                try:
                    p.wait()
                except KeyboardInterrupt:
                    p.terminate()
            else:
                # Desktop windowed monitor loop
                while p.poll() is None:
                    for ev in pygame.event.get():
                        if ev.type == pygame.QUIT:
                            p.terminate()
                            break
                        elif ev.type == pygame.KEYDOWN:
                            if ev.key in back_keys:
                                logger.info("Video player exit requested via key %s", ev.key)
                                p.terminate()
                                break
                        elif ev.type == pygame.JOYBUTTONDOWN:
                            if ev.button in (back_btn, 6, 8, 10):
                                logger.info("Video player exit requested via gamepad back button %s", ev.button)
                                p.terminate()
                                break
                    time.sleep(0.04)

            try:
                p.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                p.kill()

            logger.info("Video player exited with code %s", p.returncode)
        except Exception as e:
            logger.error("Failed to execute video player: %s", e)
            return False
        finally:
            time.sleep(0.2)

            if had_display:
                logger.info("Restoring Pygame display after video playback...")
                try:
                    pygame.display.init()
                    pygame.display.set_mode((width, height), pygame.FULLSCREEN)
                    pygame.event.clear()
                except Exception as e:
                    logger.warning("Failed to restore Pygame display: %s", e)
            elif self.is_handheld and self.system == "Linux":
                try:
                    pygame.display.set_mode((width, height))
                    pygame.event.clear()
                except Exception as e:
                    logger.debug("Failed to re-sync display mode: %s", e)

        return True
