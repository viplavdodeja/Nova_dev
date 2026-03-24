# NOVA Testing (Chat + CV Scene to LLM)

This test package provides two terminal modes:
- Chat mode: send typed input to local Ollama (`qwen2.5:1.5b`) and optionally speak the response
- CV scene test mode: capture webcam frames, run YOLO detections, build clean scene text, send scene text to Ollama, and optionally speak the response

Raw YOLO output is not sent directly to the LLM.  
The model receives compact scene text such as: `I detect a person and a bottle.`

## Files
- `main.py`: menu + mode orchestration
- `llm.py`: Ollama API calls (`generate_response`, `generate_scene_response`)
- `vision.py`: webcam capture, YOLO detection filtering, scene-text building
- `speech.py`: Piper-first TTS (`python3 -m piper` + `aplay`) with optional `espeak` fallback

## Run
From inside `nova_testing`:

```bash
python3 main.py
```

Then choose:
- `1` for terminal chat mode
- `2` for CV scene test mode

## Configuration
Edit constants at the top of `main.py`:
- `SPEECH_ENABLED`: enable/disable spoken output
- `CAMERA_INDEX`: webcam index (often `0`)
- `CONFIDENCE_THRESHOLD`: low-confidence filter for detections
- `FRAME_COUNT`: number of frames used in one CV test run
- `YOLO_MODEL_PATH`: model file path (default `yolo11n.pt`)

## Raspberry Pi / Linux assumptions
- Python 3
- Ollama installed and running locally
- Model available: `qwen2.5:1.5b`
- OpenCV and Ultralytics available for vision mode
- USB webcam accessible from the selected camera index
- Piper installed (`piper-tts`) and `aplay` available
- Optional fallback: `espeak`

## Install examples
Primary TTS (Piper):
```bash
sudo apt update
sudo apt install -y alsa-utils
pip install piper-tts
python3 -m piper.download_voices en_US-lessac-medium
```

Optional fallback:
```bash
sudo apt install -y espeak
```

Python vision dependencies (if needed):
```bash
pip install opencv-python ultralytics
```

## Verify Ollama
```bash
ollama list
curl http://localhost:11434/api/tags
ollama pull qwen2.5:1.5b
```

## Quick audio test
Manual Piper test:
```bash
python3 -m piper -m en_US-lessac-medium -f test.wav -- "Hello, I am NOVA."
aplay test.wav
```

## Speech behavior
- `speech.py` uses Piper first via `python3 -m piper`.
- It writes a temporary `.wav`, plays it with `aplay`, then removes the file.
- If Piper fails and `ENABLE_ESPEAK_FALLBACK` is `True`, it tries `espeak`.
- `speak_text(text)` returns `True` only on successful playback, otherwise `False`.

## Change voice model
Edit `PIPER_VOICE_MODEL` in `speech.py` (default: `en_US-lessac-medium`), then download that voice:
```bash
python3 -m piper.download_voices <voice-name>
```
