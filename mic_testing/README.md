# Mic Testing (Whisper)

Simple continuous microphone transcription test using OpenAI Whisper.

## Files
- `main.py`: records short mic chunks and transcribes continuously
- `config.py`: model/audio settings
- `requirements.txt`: python deps

## Setup
```bash
cd ~/capstone_project/nova_testing/mic_testing
pip install -r requirements.txt
```

## Optional: list mic devices
```bash
python3 main.py --list-devices
```

## Run
```bash
python3 main.py
```

With explicit input device:
```bash
python3 main.py --device 2
```

With different model:
```bash
python3 main.py --model small.en
```

## Notes
- Recorder now uses your device default sample rate automatically, then resamples to `16000` for Whisper.
- First run may take time while model weights download.
- If recognition is too sensitive or not sensitive enough, tune `SILENCE_RMS_THRESHOLD` in `config.py`.
