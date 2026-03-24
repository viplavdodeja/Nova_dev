# NOVA Testing: Warm Multimodal Pipeline

This package runs a warm, low-latency prototype pipeline on Raspberry Pi/Linux:

`STT + CV -> LLM -> TTS`

- STT: offline microphone speech-to-text with Vosk
- CV: webcam + YOLO scene summary
- LLM: local Ollama model `nova` with `keep_alive`
- TTS: Piper HTTP server (primary), optional `espeak` fallback

## Folder Modules
- `config.py`: runtime settings in one place
- `stt.py`: Vosk microphone recognition
- `vision.py`: frame capture, YOLO detections, scene summary text
- `llm.py`: Ollama calls, warmup, multimodal response generation
- `speech.py`: Piper HTTP synthesis + playback
- `main.py`: startup checks and runtime loop

## Requirements
- Python 3.10+
- Linux/Raspberry Pi
- Ollama running locally
- Piper voice downloaded
- Optional webcam and microphone

## Python Packages
```bash
pip install vosk sounddevice ultralytics opencv-python
pip install "piper-tts[http]"
```

## Linux Utilities
```bash
sudo apt update
sudo apt install -y alsa-utils espeak
```

`alsa-utils` provides `aplay` and `arecord`.

## Ollama Setup
Start Ollama (example):
```bash
ollama serve
```

Build custom model if needed:
```bash
ollama pull qwen2.5:1.5b
ollama create nova -f novafile
```

`llm.py` keeps the model warm via `keep_alive` and calls `warm_llm()` at startup.

## Piper HTTP Setup
Download voice:
```bash
python3 -m piper.download_voices en_US-lessac-medium
```

Start Piper HTTP server:
```bash
python3 -m piper.http_server -m en_US-lessac-medium
```

Default URL in config:
`http://localhost:5000`

## Vosk Model Setup
1. Download a Vosk model (for example `vosk-model-small-en-us-0.15`) from the Vosk model list.
2. Extract it in the `nova_testing` directory or another local path.
3. Set `VOSK_MODEL_PATH` in `config.py` to that folder.

## Microphone Device Checks
List capture devices:
```bash
arecord -l
```

If needed, set `MIC_DEVICE_INDEX` in `config.py`.

## Run
From inside `nova_testing`:
```bash
python3 main.py
```

Runtime behavior:
1. Warms Ollama
2. Checks Piper HTTP availability
3. Initializes STT if enabled
4. Per turn: listen (or typed fallback), capture scene, call LLM, speak response

Type `exit` in typed fallback input to quit.

## Config Values To Edit First
Open `config.py` and check:
- `OLLAMA_URL`
- `OLLAMA_MODEL`
- `OLLAMA_KEEP_ALIVE`
- `PIPER_HTTP_URL`
- `PIPER_VOICE`
- `VOSK_MODEL_PATH`
- `MIC_DEVICE_INDEX`
- `CAMERA_INDEX`
- `CV_CONFIDENCE_THRESHOLD`
- `SPEECH_ENABLED`
- `CV_ENABLED`
- `STT_ENABLED`
- `OPTIONAL_LEADING_SILENCE_MS`

## Known Limitations
- Piper HTTP response format can vary by version; this code tries common endpoints/payloads.
- If STT has noisy input, recognition quality can drop.
- CV inference latency depends on Pi model, camera resolution, and YOLO variant.
- This is a test harness; there is no persistent conversation memory.

## Fallback Behavior
- If STT fails or is disabled, typed terminal input is used.
- If CV fails or is disabled, scene text is omitted.
- If Piper HTTP fails, optional `espeak` fallback is used when enabled.
- If TTS fails entirely, app continues running without crashing.
