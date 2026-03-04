import os
import subprocess
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TWITCH_STREAM_KEY, STREAM_FPS, TIMEZONE, QUIET_HOURS_START, QUIET_HOURS_END, STREAM_WIDTH, STREAM_HEIGHT

TWITCH_RTMP = "rtmp://live.twitch.tv/app"

# Audio: signed 8-bit stereo at 48kHz (PyBoy's native format)
SAMPLE_RATE = 48000
AUDIO_CHANNELS = 2
AUDIO_BYTES_PER_SAMPLE = 1  # int8
AUDIO_BYTES_PER_FRAME = (SAMPLE_RATE // STREAM_FPS) * AUDIO_CHANNELS * AUDIO_BYTES_PER_SAMPLE


class TwitchStreamer:
    def __init__(self, emulator):
        self.emulator = emulator
        self._process: subprocess.Popen | None = None
        self._running = False        # global on/off
        self._streaming = False      # True only while FFmpeg is active
        self._frames_sent = 0
        self._errors = 0

    def _is_quiet_hours(self) -> bool:
        hour = datetime.now(ZoneInfo(TIMEZONE)).hour
        if QUIET_HOURS_START > QUIET_HOURS_END:
            return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END
        return QUIET_HOURS_START <= hour < QUIET_HOURS_END

    def _seconds_until_quiet_hours_end(self) -> float:
        now = datetime.now(ZoneInfo(TIMEZONE))
        wake = now.replace(hour=QUIET_HOURS_END, minute=0, second=0, microsecond=0)
        if wake <= now:
            wake = wake.replace(day=wake.day + 1)
        return (wake - now).total_seconds()

    def _ffmpeg_cmd(self, video_fd: int, audio_fd: int) -> list[str]:
        return [
            "ffmpeg",
            # Video input
            "-thread_queue_size", "512",
            "-f", "rawvideo",
            "-pixel_format", "rgb24",
            "-video_size", f"{STREAM_WIDTH}x{STREAM_HEIGHT}",
            "-framerate", str(STREAM_FPS),
            "-i", f"pipe:{video_fd}",
            # Audio input — signed 8-bit stereo PCM
            "-thread_queue_size", "512",
            "-f", "s8",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(AUDIO_CHANNELS),
            "-i", f"pipe:{audio_fd}",
            # Video encoding
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-maxrate", "3000k",
            "-bufsize", "6000k",
            "-pix_fmt", "yuv420p",
            "-g", str(STREAM_FPS * 2),
            # Audio encoding
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", str(SAMPLE_RATE),
            # Output
            "-f", "flv",
            f"{TWITCH_RTMP}/{TWITCH_STREAM_KEY}",
        ]

    def _video_writer(self, pipe):
        frame_duration = 1.0 / STREAM_FPS
        while self._streaming:
            start = time.monotonic()
            try:
                pipe.write(self.emulator.get_raw_frame())
                pipe.flush()
                self._frames_sent += 1
            except (BrokenPipeError, OSError) as e:
                self._errors += 1
                print(f"[streamer] Video pipe error: {e}")
                self._streaming = False
                break
            remaining = frame_duration - (time.monotonic() - start)
            if remaining > 0:
                time.sleep(remaining)
        print(f"[streamer] Video writer stopped ({self._frames_sent} frames)")

    def _audio_writer(self, pipe):
        frame_duration = 1.0 / STREAM_FPS
        while self._streaming:
            start = time.monotonic()
            try:
                pipe.write(self.emulator.get_audio_chunk(AUDIO_BYTES_PER_FRAME))
                pipe.flush()
            except (BrokenPipeError, OSError) as e:
                self._errors += 1
                print(f"[streamer] Audio pipe error: {e}")
                self._streaming = False
                break
            remaining = frame_duration - (time.monotonic() - start)
            if remaining > 0:
                time.sleep(remaining)
        print("[streamer] Audio writer stopped")

    def _start_stream(self):
        print(f"[streamer] Starting stream — {STREAM_WIDTH}x{STREAM_HEIGHT} @ {STREAM_FPS}fps")
        video_r, video_w = os.pipe()
        audio_r, audio_w = os.pipe()

        self._process = subprocess.Popen(
            self._ffmpeg_cmd(video_r, audio_r),
            pass_fds=(video_r, audio_r),
        )
        os.close(video_r)
        os.close(audio_r)
        print(f"[streamer] FFmpeg started (pid {self._process.pid})")

        video_pipe = os.fdopen(video_w, 'wb')
        audio_pipe = os.fdopen(audio_w, 'wb')

        self._streaming = True
        video_thread = threading.Thread(target=self._video_writer, args=(video_pipe,), daemon=True)
        audio_thread = threading.Thread(target=self._audio_writer, args=(audio_pipe,), daemon=True)
        video_thread.start()
        audio_thread.start()

        return video_pipe, audio_pipe, video_thread, audio_thread

    def _stop_stream(self, video_pipe, audio_pipe, video_thread, audio_thread):
        print("[streamer] Stopping stream...")
        self._streaming = False
        if self._process:
            self._process.terminate()
            self._process = None
        video_thread.join()
        audio_thread.join()
        try:
            video_pipe.close()
            audio_pipe.close()
        except OSError:
            pass
        print(f"[streamer] Stream stopped ({self._frames_sent} total frames)")

    def run(self):
        print(f"[streamer] Stream manager started (quiet hours: {QUIET_HOURS_START}:00–{QUIET_HOURS_END}:00 {TIMEZONE})")
        self._running = True

        while self._running:
            if self._is_quiet_hours():
                secs = self._seconds_until_quiet_hours_end()
                print(f"[streamer] Quiet hours — stream off until {QUIET_HOURS_END}:00 {TIMEZONE} ({secs/3600:.1f}h)")
                time.sleep(secs)
                print("[streamer] Quiet hours over, starting stream")
                continue

            # Start the stream
            video_pipe, audio_pipe, video_thread, audio_thread = self._start_stream()

            # Check every minute whether quiet hours have started or stream died
            while self._running and self._streaming:
                time.sleep(60)
                if self._is_quiet_hours():
                    print(f"[streamer] Quiet hours starting — stopping stream")
                    break

            self._stop_stream(video_pipe, audio_pipe, video_thread, audio_thread)

        print("[streamer] Stream manager exited")

    def stop(self):
        print("[streamer] Shutting down...")
        self._running = False
        self._streaming = False
        if self._process:
            self._process.terminate()
            print(f"[streamer] FFmpeg terminated ({self._frames_sent} total frames)")
