import io
import threading
import time

from PIL import Image, ImageDraw, ImageFont
from pyboy import PyBoy
from pyboy.utils import WindowEvent

try:
    _FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
except Exception:
    _FONT = ImageFont.load_default()

_OVERLAY_DURATION = 5.0  # seconds to show the overlay after a command

BUTTON_MAP: dict[str, tuple[WindowEvent, WindowEvent]] = {
    "up":     (WindowEvent.PRESS_ARROW_UP,      WindowEvent.RELEASE_ARROW_UP),
    "down":   (WindowEvent.PRESS_ARROW_DOWN,    WindowEvent.RELEASE_ARROW_DOWN),
    "left":   (WindowEvent.PRESS_ARROW_LEFT,    WindowEvent.RELEASE_ARROW_LEFT),
    "right":  (WindowEvent.PRESS_ARROW_RIGHT,   WindowEvent.RELEASE_ARROW_RIGHT),
    "a":      (WindowEvent.PRESS_BUTTON_A,      WindowEvent.RELEASE_BUTTON_A),
    "b":      (WindowEvent.PRESS_BUTTON_B,      WindowEvent.RELEASE_BUTTON_B),
    "start":  (WindowEvent.PRESS_BUTTON_START,  WindowEvent.RELEASE_BUTTON_START),
    "select": (WindowEvent.PRESS_BUTTON_SELECT, WindowEvent.RELEASE_BUTTON_SELECT),
}


class Emulator:
    def __init__(self, rom_path: str, frames_per_input: int = 6):
        print(f"[emulator] Loading ROM: {rom_path}")
        self.pyboy = PyBoy(rom_path, window="null", sound_emulated=True)
        self.pyboy.set_emulation_speed(1)  # 1x = normal Game Boy speed (~60fps)
        self.frames_per_input = frames_per_input
        print(f"[emulator] Initialized — headless, sound enabled, {frames_per_input} frames/input")

        self._queue: list[str] = []
        self._queue_lock = threading.Lock()
        self._running = False
        self._total_commands = 0
        self._frame_count = 0

        # Frame/audio buffers: filled by the emulator tick loop, drained by the streamer
        self._latest_frame: bytes = b'\x00' * (160 * 144 * 3)  # black until first tick
        self._frame_lock = threading.Lock()
        self._audio_buffer = bytearray()
        self._audio_lock = threading.Lock()

        # Input overlay
        self._overlay_text: str = ""
        self._overlay_time: float = 0.0
        self._overlay_lock = threading.Lock()

        self._loop_stopped = threading.Event()

    def queue_command(self, command: str) -> bool:
        """Add a validated command to the input queue. Returns True if accepted."""
        cmd = command.lower().strip()
        if cmd not in BUTTON_MAP:
            print(f"[emulator] Rejected unknown command: '{command}'")
            return False
        with self._queue_lock:
            self._queue.append(cmd)
            queue_len = len(self._queue)
        print(f"[emulator] Queued '{cmd}' (queue depth: {queue_len})")
        return True

    def set_last_input(self, platform: str, username: str, command: str) -> None:
        """Set the overlay text shown on the stream for the next few seconds."""
        with self._overlay_lock:
            self._overlay_text = f"[{platform}] {username}: {command}"
            self._overlay_time = time.monotonic()

    def get_raw_frame(self) -> bytes:
        """Return raw RGB24 bytes of the latest screen frame (for FFmpeg streaming)."""
        with self._frame_lock:
            frame = self._latest_frame

        with self._overlay_lock:
            text = self._overlay_text
            age = time.monotonic() - self._overlay_time

        if text and age < _OVERLAY_DURATION:
            img = Image.frombytes("RGB", (160, 144), frame)
            draw = ImageDraw.Draw(img)
            bar_h = 13
            bar_y = 144 - bar_h
            draw.rectangle([(0, bar_y), (160, 144)], fill=(20, 20, 20))
            draw.text((2, bar_y + 2), text, font=_FONT, fill=(255, 255, 255))
            return img.tobytes()

        return frame

    def get_screenshot(self) -> bytes:
        """Capture the current screen as PNG bytes."""
        img = self.pyboy.screen.image
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        size_kb = len(buf.getvalue()) / 1024
        print(f"[emulator] Screenshot captured ({size_kb:.1f} KB, frame {self._frame_count})")
        return buf.getvalue()

    def get_audio_chunk(self, num_bytes: int) -> bytes:
        """
        Return exactly num_bytes of audio (signed 8-bit stereo, 48000 Hz).
        Pads with silence if the buffer doesn't have enough yet.
        """
        with self._audio_lock:
            available = len(self._audio_buffer)
            if available >= num_bytes:
                chunk = bytes(self._audio_buffer[:num_bytes])
                del self._audio_buffer[:num_bytes]
            else:
                chunk = bytes(self._audio_buffer) + b'\x00' * (num_bytes - available)
                self._audio_buffer.clear()
                if available < num_bytes // 2:
                    print(f"[emulator] Audio underrun — had {available}B, needed {num_bytes}B, padded with silence")
        return chunk

    def run(self):
        """Main game loop — run this in a dedicated thread."""
        print("[emulator] Game loop starting...")
        self._running = True
        current_cmd: str | None = None
        frames_held = 0
        last_status_time = time.monotonic()

        while self._running and self.pyboy.tick():
            self._frame_count += 1

            # Capture frame and audio immediately after tick — both buffers are
            # overwritten each tick so we must copy them before the next tick runs
            frame_data = self.pyboy.screen.image.convert("RGB").tobytes()
            with self._frame_lock:
                self._latest_frame = frame_data

            audio_data = self.pyboy.sound.ndarray.tobytes()
            with self._audio_lock:
                self._audio_buffer.extend(audio_data)

            if current_cmd is not None:
                frames_held += 1
                if frames_held >= self.frames_per_input:
                    self.pyboy.send_input(BUTTON_MAP[current_cmd][1])  # release
                    print(f"[emulator] Released '{current_cmd}' after {frames_held} frames")
                    current_cmd = None
                    frames_held = 0
            else:
                with self._queue_lock:
                    if self._queue:
                        current_cmd = self._queue.pop(0)
                        remaining = len(self._queue)
                        self.pyboy.send_input(BUTTON_MAP[current_cmd][0])  # press
                        self._total_commands += 1
                        print(f"[emulator] Pressing '{current_cmd}' (cmd #{self._total_commands}, {remaining} remaining in queue)")

            # Print a status line every 60 seconds
            now = time.monotonic()
            if now - last_status_time >= 60:
                with self._queue_lock:
                    q = len(self._queue)
                with self._audio_lock:
                    audio_buf = len(self._audio_buffer)
                print(f"[emulator] Status — frame {self._frame_count}, total commands: {self._total_commands}, queue: {q}, audio buffer: {audio_buf}B")
                last_status_time = now

        print(f"[emulator] Game loop ended — {self._frame_count} frames, {self._total_commands} total commands")
        self._loop_stopped.set()

    def save_state(self, path: str) -> None:
        """Save emulator state to disk. Call only after the game loop has stopped."""
        try:
            with open(path, "wb") as f:
                self.pyboy.save_state(f)
            print(f"[emulator] State saved to {path}")
        except Exception as e:
            print(f"[emulator] Failed to save state: {e}")

    def load_state(self, path: str) -> None:
        """Load emulator state from disk. Call before starting the game loop."""
        try:
            with open(path, "rb") as f:
                self.pyboy.load_state(f)
            print(f"[emulator] State loaded from {path}")
        except Exception as e:
            print(f"[emulator] Failed to load state: {e}")

    def stop(self):
        print("[emulator] Stopping...")
        self._running = False
        self._loop_stopped.wait(timeout=3.0)
        self.pyboy.stop()
        print("[emulator] Stopped")
