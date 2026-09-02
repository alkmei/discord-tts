import struct
import threading
import time
from unittest.mock import MagicMock
from unittest.mock import patch

from bot.services.stream import RedisAudioStream
from discord_tts.speech.tasks import _wav_header

WAV_HEADER_SIZE = 44
FMT_CHUNK_SIZE = 16
PCM_FORMAT = 1
SAMPLE_RATE_24K = 24000
BITS_16 = 16
DATA_SIZE_STREAMING = 0xFFFFFFFF
CHUNK_4_BYTES = 4


def test_wav_header_structure():
    header = _wav_header(
        sample_rate=SAMPLE_RATE_24K,
        num_channels=1,
        bits_per_sample=BITS_16,
    )
    assert len(header) == WAV_HEADER_SIZE

    (
        riff_tag,
        _riff_size,
        wave_tag,
        fmt_tag,
        fmt_size,
        audio_format,
        channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        data_tag,
        data_size,
    ) = struct.unpack("<4sI4s4sIHHIIHH4sI", header)

    assert riff_tag == b"RIFF"
    assert wave_tag == b"WAVE"
    assert fmt_tag == b"fmt "
    assert fmt_size == FMT_CHUNK_SIZE
    assert audio_format == PCM_FORMAT
    assert channels == 1
    assert sample_rate == SAMPLE_RATE_24K
    assert bits_per_sample == BITS_16
    assert byte_rate == SAMPLE_RATE_24K * 1 * BITS_16 // 8
    assert block_align == 1 * BITS_16 // 8
    assert data_tag == b"data"
    assert data_size == DATA_SIZE_STREAMING


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
