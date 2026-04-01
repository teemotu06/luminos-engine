# Kokoro Local TTS Setup

LUMINOS now supports fully local roster prompt speech for oral-check flow.

## Python dependencies

Install the app requirements:

```bash
cd /Users/tanioramotu/luminos-engine
source .venv/bin/activate
pip install -r requirements.txt
```

Then install the local Kokoro runtime packages separately. This project currently runs on Python 3.9, so use the minimal no-extra install path below instead of `pip install kokoro` with default English extras.

```bash
pip install --no-deps kokoro==0.7.16 misaki==0.7.16
pip install torch transformers huggingface-hub loguru scipy numpy==1.26.4 soundfile
pip install espeakng-loader phonemizer-fork num2words regex cffi pycparser
```

The local TTS integration expects these Python packages at runtime:

- `kokoro`
- `misaki`
- `numpy`
- `soundfile`
- `torch`
- `transformers`
- `huggingface-hub`
- `loguru`
- `scipy`
- `espeakng-loader`
- `phonemizer-fork`
- `num2words`
- `regex`

## System dependency

Kokoro relies on local phonemizer/system voice tooling. On macOS or Linux, install `espeak-ng` if local synthesis fails during phonemization.

Examples:

```bash
brew install espeak-ng
```

or on Debian/Ubuntu:

```bash
sudo apt-get install espeak-ng
```

## Optional environment variables

These are optional. Defaults are already set in the app service.

- `KOKORO_VOICE` default: `af_heart`
- `KOKORO_SPEED` default: `1.0`
- `KOKORO_SAMPLE_RATE` default: `24000`
- `LUMINOS_TTS_CACHE_DIR` default: `~/.luminos-cache/tts`
- `LUMINOS_TTS_PREWARM_ENABLED` default: `true`
- `LUMINOS_TTS_STRICT_STARTUP` default: `false`
- `LUMINOS_TTS_PREWARM_TEXT` default: `Luminos is ready.`
- `LUMINOS_TTS_CACHE_RETENTION_DAYS` default: `30`
- `LUMINOS_TTS_CACHE_PRUNE_ON_STARTUP` default: `true`

## Runtime behavior

- Request: `POST /lesson/tts/prompt`
- Request JSON:

```json
{ "text": "Tom, please read." }
```

- Response JSON:

```json
{
  "text": "Tom, please read.",
  "audio_url": "/tts-cache/abcd1234efgh5678.wav"
}
```

Generated WAV files are cached in:

```text
~/.luminos-cache/tts/
```

The frontend automatically requests and plays the next student prompt during Block 07 oral-check flow.

## Notes

- This integration uses Kokoro locally for synthesis.
- On first use, Kokoro will download model weights and the selected voice from Hugging Face into the local cache. After that, speech generation is local and cached in `~/.luminos-cache/tts/`.
- On app startup, LUMINOS prewarms Kokoro by default so model/voice initialization happens before the first classroom prompt.
- On app startup, LUMINOS also prunes old cached WAV files by default.
- If you want deployment to fail fast when Kokoro is unavailable, set `LUMINOS_TTS_STRICT_STARTUP=true`.
- Runtime prompt audio is served from the dedicated FastAPI mount `/tts-cache`, not from the source tree.
- The implementation uses a lightweight `espeak` phonemizer path for English prompts to avoid the Python 3.9-incompatible `spacy` dependency chain in the full Misaki English stack.

## Operator endpoints

These are served from the existing admin router:

- `GET /admin/tts-health`
- `POST /admin/tts-prune-cache?max_age_days=30`

If `LUMINOS_ADMIN_SECRET` is set, pass `?secret=<value>`.
