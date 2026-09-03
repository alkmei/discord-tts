import threading
import time
from unittest.mock import MagicMock
from unittest.mock import patch

import discord
import numpy as np

from bot.services.stream import PrimedAudioSource
from bot.services.stream import RedisAudioStream

CHUNK_4_BYTES = 4
INT16_MIN = -32768
INT16_MAX = 32767


def test_sample_clipping_prevents_overflow():
    """Verify float audio is clamped to avoid int16 wrap-around."""
    raw_floats = np.array([-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5], dtype=np.float32)

    # Without clipping, 1.5 * 32767 wraps to negative
    unclipped = (raw_floats * 32767).astype("<i2")
    assert unclipped[-1] < 0

    # With clipping, values stay within [-32768, 32767]
    clipped = np.clip(raw_floats * 32767.0, -32768.0, 32767.0).astype("<i2")
    assert clipped[0] == INT16_MIN
    assert clipped[-1] == INT16_MAX
    assert clipped[3] == 0


def test_redis_audio_stream_wait_until_ready_threshold():
    """Verify wait_until_ready unblocks when prebuffer_bytes threshold is met."""
    chunks = [
        (b"key", b"chunk1_1234"),
        (b"key", b"chunk2_5678"),
        (b"key", b"chunk3_9012"),
    ]
    mock_redis = MagicMock()
    mock_redis.blpop.side_effect = chunks

    with patch("redis.from_url", return_value=mock_redis):
        stream = RedisAudioStream(
            "redis://localhost:6379/0",
            "test_key",
            prebuffer_bytes=11,
        )
        ready = stream.wait_until_ready(timeout=2.0)
        assert ready is True
        stream.close()


def test_redis_audio_stream_wait_until_ready_eof():
    """Verify wait_until_ready unblocks when EOF arrives before threshold."""
    chunks = [
        (b"key", b"hi"),
        (b"key", b"EOF"),
    ]
    mock_redis = MagicMock()
    mock_redis.blpop.side_effect = chunks

    with patch("redis.from_url", return_value=mock_redis):
        stream = RedisAudioStream(
            "redis://localhost:6379/0",
            "test_key",
            prebuffer_bytes=1000,
        )
        ready = stream.wait_until_ready(timeout=2.0)
        assert ready is True
        assert stream.is_eof is True
        data = stream.read()
        assert data == b"hi"
        stream.close()


def test_primed_audio_source():
    """Verify PrimedAudioSource pre-reads the first frame on initialization."""
    mock_source = MagicMock(spec=discord.AudioSource)
    mock_source.read.side_effect = [b"frame1", b"frame2", b""]
    mock_source.is_opus.return_value = False

    primed = PrimedAudioSource(mock_source)
    assert mock_source.read.call_count == 1
    assert primed.read() == b"frame1"
    assert primed.read() == b"frame2"
    assert primed.read() == b""

    primed.cleanup()
    mock_source.cleanup.assert_called_once()


def test_redis_audio_stream_reads_chunks_until_eof():
    chunks = [
        (b"key", b"chunk1_"),
        (b"key", b"chunk2_"),
        (b"key", b"chunk3"),
        (b"key", b"EOF"),
    ]

    mock_redis = MagicMock()
    mock_redis.blpop.side_effect = chunks

    with patch("redis.from_url", return_value=mock_redis):
        stream = RedisAudioStream("redis://localhost:6379/0", "test_key")
        result = bytearray()
        while True:
            data = stream.read(CHUNK_4_BYTES)
            if not data:
                break
            result.extend(data)
        stream.close()

    assert bytes(result) == b"chunk1_chunk2_chunk3"


def test_redis_audio_stream_concurrent_push():
    queue = []
    cond = threading.Condition()
    done = False

    def fake_blpop(key, timeout=1):
        with cond:
            while not queue and not done:
                cond.wait(timeout=0.1)
                return None
            if queue:
                return (b"key", queue.pop(0))
            return None

    mock_redis = MagicMock()
    mock_redis.blpop.side_effect = fake_blpop

    with patch("redis.from_url", return_value=mock_redis):
        stream = RedisAudioStream("redis://localhost:6379/0", "test_key")

        # Push data with a small delay
        def producer():
            time.sleep(0.05)
            with cond:
                queue.append(b"hello ")
                cond.notify_all()
            time.sleep(0.05)
            with cond:
                queue.append(b"world")
                cond.notify_all()
            time.sleep(0.05)
            with cond:
                queue.append(b"EOF")
                cond.notify_all()

        t = threading.Thread(target=producer)
        t.start()

        data = stream.read(5)
        assert data == b"hello"
        rest = stream.read()
        assert rest == b" world"
        eof = stream.read()
        assert eof == b""

        t.join()
        stream.close()


def test_redis_audio_stream_readinto():
    chunks = [(b"key", b"12345678"), (b"key", b"EOF")]

    mock_redis = MagicMock()
    mock_redis.blpop.side_effect = chunks

    with patch("redis.from_url", return_value=mock_redis):
        stream = RedisAudioStream("redis://localhost:6379/0", "test_key")
        buf = bytearray(CHUNK_4_BYTES)
        n = stream.readinto(buf)
        assert n == CHUNK_4_BYTES
        assert buf == b"1234"

        n2 = stream.readinto(buf)
        assert n2 == CHUNK_4_BYTES
        assert buf == b"5678"

        n3 = stream.readinto(buf)
        assert n3 == 0
        stream.close()
