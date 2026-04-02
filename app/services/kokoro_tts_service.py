import hashlib
import importlib.util
import logging
import os
import sys
import threading
import time
import types
from functools import lru_cache
from pathlib import Path


class KokoroTtsError(RuntimeError):
    """Raised when local Kokoro speech generation is unavailable or fails."""


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = Path.home() / ".luminos-cache" / "tts"
TTS_CACHE_DIR = Path(os.getenv("LUMINOS_TTS_CACHE_DIR", str(DEFAULT_CACHE_ROOT))).expanduser()
DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
DEFAULT_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
DEFAULT_SAMPLE_RATE = int(os.getenv("KOKORO_SAMPLE_RATE", "24000"))
LOCK_TIMEOUT_SECONDS = float(os.getenv("LUMINOS_TTS_LOCK_TIMEOUT_SECONDS", "20"))
LOCK_STALE_SECONDS = float(os.getenv("LUMINOS_TTS_LOCK_STALE_SECONDS", "120"))
PREWARM_TEXT = os.getenv("LUMINOS_TTS_PREWARM_TEXT", "Luminos is ready.")
CACHE_RETENTION_DAYS = int(os.getenv("LUMINOS_TTS_CACHE_RETENTION_DAYS", "30"))
_MODEL_INIT_LOCK = threading.Lock()
_MODEL_SINGLETON = None


def _normalized_text(text: str) -> str:
    normalized = " ".join((text or "").strip().split())
    if not normalized:
        raise KokoroTtsError("Text is required for local TTS.")
    return normalized


def _tts_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _lock_path_for(wav_path: Path) -> Path:
    return wav_path.with_suffix(f"{wav_path.suffix}.lock")


def _acquire_generation_lock(lock_path: Path) -> int:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS

    while True:
        try:
            return os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            try:
                age_seconds = time.time() - lock_path.stat().st_mtime
                if age_seconds > LOCK_STALE_SECONDS:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue

            if time.monotonic() >= deadline:
                raise KokoroTtsError("Timed out waiting for local TTS cache generation lock.")
            time.sleep(0.1)


def _release_generation_lock(lock_fd: int, lock_path: Path) -> None:
    try:
        os.close(lock_fd)
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except FileNotFoundError:
            pass


@lru_cache(maxsize=1)
def _get_kmodel_class():
    spec = importlib.util.find_spec("kokoro")
    if spec is None or not spec.submodule_search_locations:
        raise KokoroTtsError(
            "Kokoro is not installed. Install the local Kokoro dependencies listed in KOKORO_TTS_SETUP.md."
        )

    package_dir = Path(list(spec.submodule_search_locations)[0])
    runtime_package_name = "_luminos_kokoro_runtime"

    if runtime_package_name not in sys.modules:
        runtime_package = types.ModuleType(runtime_package_name)
        runtime_package.__path__ = [str(package_dir)]
        sys.modules[runtime_package_name] = runtime_package

    for module_name in ("istftnet", "modules", "model"):
        full_name = f"{runtime_package_name}.{module_name}"
        if full_name in sys.modules:
            continue
        module_spec = importlib.util.spec_from_file_location(full_name, package_dir / f"{module_name}.py")
        if module_spec is None or module_spec.loader is None:
            raise KokoroTtsError(f"Failed to load Kokoro module '{module_name}'.")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[full_name] = module
        module_spec.loader.exec_module(module)

    return sys.modules[f"{runtime_package_name}.model"].KModel


def _get_model():
    global _MODEL_SINGLETON
    if _MODEL_SINGLETON is not None:
        return _MODEL_SINGLETON
    with _MODEL_INIT_LOCK:
        if _MODEL_SINGLETON is not None:
            return _MODEL_SINGLETON
        try:
            KModel = _get_kmodel_class()
        except ImportError as exc:
            raise KokoroTtsError(
                "Kokoro is not installed. Install the local Kokoro dependencies listed in KOKORO_TTS_SETUP.md."
            ) from exc
        except Exception as exc:
            raise KokoroTtsError(f"Failed to load Kokoro model modules: {exc}") from exc

        try:
            import torch
        except ImportError as exc:
            raise KokoroTtsError("torch is required for local Kokoro synthesis.") from exc

        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            _MODEL_SINGLETON = KModel().to(device).eval()
            return _MODEL_SINGLETON
        except Exception as exc:
            raise KokoroTtsError(f"Failed to initialize Kokoro model: {exc}") from exc


@lru_cache(maxsize=8)
def _load_voice_pack(voice_name: str):
    try:
        import torch
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise KokoroTtsError("huggingface-hub and torch are required for Kokoro voice loading.") from exc

    model = _get_model()
    try:
        voice_path = hf_hub_download(repo_id=model.REPO_ID, filename=f"voices/{voice_name}.pt")
        return torch.load(voice_path, weights_only=True).to(model.device)
    except Exception as exc:
        raise KokoroTtsError(f"Failed to load Kokoro voice '{voice_name}': {exc}") from exc


@lru_cache(maxsize=1)
def _get_english_g2p():
    try:
        import espeakng_loader
        from misaki.espeak import EspeakG2P
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
    except ImportError as exc:
        raise KokoroTtsError(
            "Misaki espeak phonemizer is not installed. Install the local Kokoro dependencies listed in KOKORO_TTS_SETUP.md."
        ) from exc

    try:
        EspeakWrapper.set_library(espeakng_loader.get_library_path())
        EspeakWrapper.set_data_path(espeakng_loader.get_data_path())
        return EspeakG2P(language="en-us")
    except Exception as exc:
        raise KokoroTtsError(f"Failed to initialize local espeak phonemizer: {exc}") from exc


def _phonemize_text(text: str) -> str:
    phonemes = _get_english_g2p()(text)
    phonemes = (phonemes or "").strip()
    if not phonemes:
        raise KokoroTtsError("Local phonemizer returned no phonemes for the supplied text.")
    if len(phonemes) > 510:
        phonemes = phonemes[:510]
    return phonemes


def _synthesize_audio(text: str):
    phonemes = _phonemize_text(text)
    model = _get_model()
    voice_pack = _load_voice_pack(DEFAULT_VOICE)
    try:
        output = model(phonemes, voice_pack[len(phonemes) - 1], DEFAULT_SPEED, return_output=True)
    except Exception as exc:
        raise KokoroTtsError(f"Kokoro failed to synthesize audio: {exc}") from exc
    return output.audio, DEFAULT_SAMPLE_RATE


def _write_wav(path: Path, audio, sample_rate: int) -> None:
    try:
        import soundfile as sf
    except ImportError as exc:
        raise KokoroTtsError("soundfile is required to write Kokoro WAV output.") from exc

    try:
        sf.write(path, audio, sample_rate, format="WAV")
    except Exception as exc:
        raise KokoroTtsError(f"Failed to write Kokoro WAV file: {exc}") from exc


def _write_wav_atomic(path: Path, audio, sample_rate: int) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    try:
        _write_wav(temp_path, audio, sample_rate)
        os.replace(temp_path, path)
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise


def ensure_tts_audio(text: str) -> dict[str, str]:
    normalized = _normalized_text(text)
    digest = _tts_hash(normalized)
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wav_path = TTS_CACHE_DIR / f"{digest}.wav"
    lock_path = _lock_path_for(wav_path)

    if wav_path.exists():
        logger.debug("Kokoro TTS cache hit for digest=%s", digest)
    else:
        logger.info("Kokoro TTS cache miss for digest=%s", digest)
        lock_fd = _acquire_generation_lock(lock_path)
        try:
            if not wav_path.exists():
                try:
                    audio, sample_rate = _synthesize_audio(normalized)
                    _write_wav_atomic(wav_path, audio, sample_rate)
                except KokoroTtsError:
                    logger.warning("Kokoro TTS generation failed for digest=%s", digest, exc_info=True)
                    raise
            else:
                logger.debug("Kokoro TTS cache filled while waiting for digest=%s", digest)
        finally:
            _release_generation_lock(lock_fd, lock_path)

    return {
        "text": normalized,
        "audio_url": f"/tts-cache/{wav_path.name}",
    }


def warmup_tts_runtime() -> dict[str, str]:
    start = time.monotonic()
    payload = ensure_tts_audio(PREWARM_TEXT)
    elapsed_ms = round((time.monotonic() - start) * 1000)
    logger.info(
        "Kokoro TTS warmup complete in %sms using voice '%s' (%s)",
        elapsed_ms,
        DEFAULT_VOICE,
        payload["audio_url"],
    )
    return payload


def prune_tts_cache(max_age_days: int = CACHE_RETENTION_DAYS) -> dict[str, int]:
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    deleted = 0
    kept = 0
    bytes_freed = 0
    cutoff = time.time() - max(max_age_days, 0) * 86400

    for wav_path in TTS_CACHE_DIR.glob("*.wav"):
        try:
            if wav_path.stat().st_mtime < cutoff:
                bytes_freed += wav_path.stat().st_size
                wav_path.unlink(missing_ok=True)
                deleted += 1
            else:
                kept += 1
        except FileNotFoundError:
            continue

    logger.info(
        "Kokoro TTS cache prune complete: deleted=%s kept=%s bytes_freed=%s",
        deleted,
        kept,
        bytes_freed,
    )
    return {"deleted": deleted, "kept": kept, "bytes_freed": bytes_freed}


def get_tts_health_snapshot(run_check: bool = True) -> dict[str, object]:
    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    wav_files = list(TTS_CACHE_DIR.glob("*.wav"))
    cache_file_count = len(wav_files)
    cache_size_bytes = sum(path.stat().st_size for path in wav_files if path.exists())

    payload = None
    error = None
    ready = True
    started = time.monotonic()

    if run_check:
        try:
            payload = ensure_tts_audio(PREWARM_TEXT)
        except KokoroTtsError as exc:
            ready = False
            error = str(exc)

    return {
        "ready": ready,
        "voice": DEFAULT_VOICE,
        "sample_rate": DEFAULT_SAMPLE_RATE,
        "cache_dir": str(TTS_CACHE_DIR),
        "cache_file_count": cache_file_count,
        "cache_size_bytes": cache_size_bytes,
        "prewarm_text": PREWARM_TEXT,
        "check_elapsed_ms": round((time.monotonic() - started) * 1000),
        "last_audio_url": payload["audio_url"] if payload else None,
        "error": error,
    }
