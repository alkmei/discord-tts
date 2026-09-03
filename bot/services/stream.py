"""Thread-safe Redis-to-pipe audio stream bridge.

Provides a file-like object that FFmpegPCMAudio can read from via pipe mode,
while a background thread pulls audio chunks from a Redis List (BLPOP).
"""

import io
import logging
import threading
import time

import discord
import redis

logger = logging.getLogger(__name__)

# Sentinel value published by the worker to signal end-of-stream
_EOF = b"EOF"
# BLPOP timeout — how long to wait for each chunk before checking again
_BLPOP_TIMEOUT = 10
# Default pre-buffer size: ~3 chunks of 1920 samples @ 24kHz mono (240ms of audio)
_DEFAULT_PREBUFFER_BYTES = 11520


class RedisAudioStream(io.RawIOBase):
    """A readable stream backed by a Redis List.

    Designed to be passed to ``discord.FFmpegPCMAudio(source, pipe=True)``
    so that FFmpeg reads audio data from stdin (``pipe:0``).

    The stream spawns a daemon thread that pulls chunks from the Redis key
    using BLPOP. Chunks are appended to an internal ``bytearray`` buffer
    and served to the reader (FFmpeg) on ``read()`` / ``readinto()`` calls.

    Thread safety is ensured by a ``threading.Condition`` that coordinates
    the producer (Redis reader thread) and the consumer (FFmpeg reader thread).
    """

    def __init__(
        self,
        redis_url: str,
        stream_key: str,
        prebuffer_bytes: int = _DEFAULT_PREBUFFER_BYTES,
    ) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._stream_key = stream_key
        self._prebuffer_bytes = prebuffer_bytes
        self._prebuffered = False

        self._buffer = bytearray()
        self._eof = False
        self._error: Exception | None = None
        self._cond = threading.Condition()

        self._thread = threading.Thread(
            target=self._consume,
            name=f"redis-stream-{stream_key}",
            daemon=True,
        )
        self._thread.start()

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Wait until prebuffer threshold is reached, stream ends, or an error occurs.

        Returns True if ready (or ended/error), False if timed out.
        """
        deadline = time.monotonic() + timeout
        with self._cond:
            while (
                len(self._buffer) < self._prebuffer_bytes
                and not self._eof
                and self._error is None
                and not self.closed
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
            self._prebuffered = True
            return True

    # ── Producer (background thread) ──────────────────────────────────

    def _consume(self) -> None:
        """Pull chunks from Redis and buffer them."""
        try:
            r = redis.from_url(self._redis_url, decode_responses=False)
            while True:
                result = r.blpop(self._stream_key, timeout=_BLPOP_TIMEOUT)
                if result is None:
                    # Timeout — check if stream was closed externally
                    if self.closed:
                        return
                    continue

                _key, data = result

                if data == _EOF:
                    with self._cond:
                        self._eof = True
                        self._cond.notify_all()
                    return

                with self._cond:
                    self._buffer.extend(data)
                    self._cond.notify_all()

        except Exception as exc:
            logger.exception("RedisAudioStream consumer error for %s", self._stream_key)
            with self._cond:
                self._error = exc
                self._eof = True
                self._cond.notify_all()

    @property
    def is_eof(self) -> bool:
        """Whether the end-of-stream sentinel has been received."""
        with self._cond:
            return self._eof

    # ── Consumer (FFmpeg reader thread) ───────────────────────────────

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        """Read up to *size* bytes. Blocks until data is available or EOF."""
        with self._cond:
            # Ensure prebuffer or EOF is reached before releasing first chunk
            while (
                not self._prebuffered
                and not self._eof
                and self._error is None
                and not self.closed
            ):
                if len(self._buffer) >= self._prebuffer_bytes:
                    break
                self._cond.wait()
            self._prebuffered = True

            if size < 0:
                while not self._eof and not self.closed:
                    self._cond.wait()
                if self._error:
                    raise self._error
                data = bytes(self._buffer)
                self._buffer.clear()
                return data

            # Wait until we have data, or EOF, or an error
            while not self._buffer and not self._eof and not self.closed:
                self._cond.wait()

            if self._error:
                raise self._error

            if not self._buffer:
                # EOF and buffer empty → signal end to FFmpeg
                return b""

            data = bytes(self._buffer[:size])
            del self._buffer[:size]
            return data

    def readinto(self, b: bytearray | memoryview) -> int:
        """Required by RawIOBase — used by BufferedReader."""
        data = self.read(len(b))
        n = len(data)
        b[:n] = data
        return n

    def close(self) -> None:
        """Close the stream and signal the background thread to stop."""
        if not self.closed:
            with self._cond:
                self._eof = True
                self._cond.notify_all()
            super().close()


class PrimedAudioSource(discord.AudioSource):
    """Wraps an AudioSource and pre-reads the first frame.

    This ensures FFmpeg process startup, piping, and initial resampling
    occur *before* discord.py's AudioPlayer thread captures
    self._start = time.perf_counter().
    On the first read() call from AudioPlayer, this immediately yields
    the pre-read frame with zero latency, preventing AudioPlayer from
    falling behind its reference clock and bursting audio frames.
    """

    def __init__(self, source: discord.AudioSource) -> None:
        self._source = source
        self._first_frame: bytes | None = source.read()

    def read(self) -> bytes:
        if self._first_frame is not None:
            frame = self._first_frame
            self._first_frame = None
            return frame
        return self._source.read()

    def is_opus(self) -> bool:
        return self._source.is_opus()

    def cleanup(self) -> None:
        self._source.cleanup()
