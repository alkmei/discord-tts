"""Thread-safe Redis-to-pipe audio stream bridge.

Provides a file-like object that FFmpegPCMAudio can read from via pipe mode,
while a background thread pulls audio chunks from a Redis List (BLPOP).
"""

import io
import logging
import threading

import redis

logger = logging.getLogger(__name__)

# Sentinel value published by the worker to signal end-of-stream
_EOF = b"EOF"
# BLPOP timeout — how long to wait for each chunk before checking again
_BLPOP_TIMEOUT = 10


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

    def __init__(self, redis_url: str, stream_key: str) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._stream_key = stream_key

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

    # ── Consumer (FFmpeg reader thread) ───────────────────────────────

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        """Read up to *size* bytes. Blocks until data is available or EOF."""
        with self._cond:
            if size < 0:
                while not self._eof:
                    self._cond.wait()
                if self._error:
                    raise self._error
                data = bytes(self._buffer)
                self._buffer.clear()
                return data

            # Wait until we have data, or EOF, or an error
            while not self._buffer and not self._eof:
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
