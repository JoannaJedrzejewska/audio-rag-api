import io
import time
import struct
import math
import pytest


def _make_wav_bytes(duration_s: float = 0.5, sr: int = 16000) -> bytes:
    num_samples = int(sr * duration_s)
    data = b"".join(
        struct.pack('<h', int(32767 * math.sin(2 * math.pi * 440 * i / sr)))
        for i in range(num_samples)
    )
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + len(data), b'WAVE', b'fmt ', 16,
        1, 1, sr, sr * 2, 2, 16, b'data', len(data))
    return header + data


def test_transcribe_returns_202(client):
    wav = _make_wav_bytes()
    r = client.post(
        "/audio/transcribe",
        files={"file": ("test.wav", io.BytesIO(wav), "audio/wav")},
    )
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "queued"


def test_transcribe_rejects_bad_format(client):
    r = client.post(
        "/audio/transcribe",
        files={"file": ("bad.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert r.status_code == 400


def test_transcribe_rejects_empty_file(client):
    r = client.post(
        "/audio/transcribe",
        files={"file": ("empty.wav", io.BytesIO(b""), "audio/wav")},
    )
    assert r.status_code == 400


def test_job_status_not_found(client):
    r = client.get("/audio/jobs/nonexistent-id-xyz")
    assert r.status_code == 404


def test_full_transcription_flow(client):
    wav = _make_wav_bytes()
    r = client.post(
        "/audio/transcribe",
        files={"file": ("flow_test.wav", io.BytesIO(wav), "audio/wav")},
    )
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    for _ in range(20):
        status_r = client.get(f"/audio/jobs/{job_id}")
        assert status_r.status_code == 200
        status = status_r.json()["status"]
        if status in ("completed", "failed"):
            break
        time.sleep(0.5)

    final = client.get(f"/audio/jobs/{job_id}").json()
    assert final["status"] in ("completed", "failed")
    if final["status"] == "completed":
        assert final["transcription"] is not None