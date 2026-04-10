# Motor Voice Control (Pi Side, whisper.cpp)

## Overview
This project runs on Raspberry Pi and sends one-letter motor commands to an Arduino over serial, based on microphone speech.

Pipeline:
1. Record short WAV clips using `arecord`
2. Transcribe clips using `whisper.cpp` CLI
3. Detect emergency stop and wake phrase
4. Parse movement commands
5. Send command letters over serial to Arduino

No Arduino code, no TTS, no UI, no LLM.

## Serial Command Mapping
- `F` = forward
- `B` = backward
- `L` = left
- `R` = right
- `S` = spin
- `X` = emergency stop
- `<LETTER><milliseconds>` = timed move, for example `F1000`

## LED State Messages
The Pi also sends LED state tokens to Arduino:
- `LED_READY` in idle/passive mode (blue)
- `LED_LISTEN` while waiting for command input (orange)
- `LED_MOVE` while the Arduino is actively moving (green)

## Project Files
- `main.py`: app loop (passive mode + command mode)
- `speech_listener.py`: recording + whisper.cpp transcription
- `command_parser.py`: wake phrase/emergency/command parsing
- `motor_serial.py`: serial connection and command sending
- `config.py`: all config values
- `requirements.txt`: Python deps
- `audio_files/`: recorded WAV clips (created automatically)

## Linux Packages
Install ALSA tools for microphone recording:

```bash
sudo apt update
sudo apt install -y alsa-utils
```

## Python Environment Setup
From your project folder:

```bash
cd ~/capstone_project/nova_testing/motor_voice_control
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## Verify Microphone Devices
List capture devices:

```bash
arecord -l
```

Set `ARECORD_DEVICE` in `config.py` to a stable capture target, typically:
- `plughw:1,0` (recommended for USB mics on Pi)
- `hw:1,0` (raw hardware device)

## Verify whisper.cpp Manually
Record a quick sample:

```bash
arecord -D default -f S16_LE -r 16000 -c 1 -d 3 test.wav
```

Recommended stable format/device test:

```bash
arecord -D plughw:1,0 -f S16_LE -r 16000 -c 1 -d 3 test.wav
```

Run whisper.cpp manually:

```bash
/home/pi/whisper.cpp/build/bin/whisper-cli \
  -m /home/pi/whisper.cpp/models/ggml-base.en.bin \
  -f test.wav -l en --no-timestamps
```

If this works, update those paths in `config.py`.

## Configure Before Running
Edit these in `config.py`:
- `SERIAL_PORT` (default `/dev/ttyUSB0`)
- `BAUD_RATE` (default `9600`)
- `WAKE_PHRASE` (default `hey nova`)
- `WAKE_REQUIRED_HITS` (set `2` to reduce false wake triggers)
- `PASSIVE_CLIP_DURATION_SECONDS`
- `COMMAND_CLIP_DURATION_SECONDS`
- `WHISPER_EXECUTABLE_PATH`
- `WHISPER_MODEL_PATH`
- `WHISPER_THREADS`
- `ENABLE_PASSIVE_VAD` / `WHISPER_VAD_MODEL_PATH`
- `ENABLE_COMMAND_GRAMMAR` / `COMMAND_GRAMMAR_PATH`
- `TEMP_AUDIO_DIR`

## Run the App

```bash
python3 main.py
```

## Expected Terminal Output
Typical output includes:
- `Connected to Arduino on /dev/ttyUSB0 @ 9600`
- `Voice motor control started`
- `Heard (passive): ...`
- `Emergency stop detected`
- `Sent to Arduino: X`
- `Wake phrase detected: hey nova`
- `Heard (command): ...`
- `Command recognized: forward`
- `Sent to Arduino: F`
- `No valid command recognized`

## Behavior Summary
- Passive mode always listens for `"stop"` and sends `X` immediately.
- Passive mode listens for wake phrase `"hey nova"`.
- Wake phrase matching handles punctuation variants such as `hey, nova`.
- Passive mode uses phrase buffering across chunks (`previous + current`) to catch split phrases.
- After wake phrase, one command clip is recorded and parsed.
- Idle LED is controlled by `LED_READY`.
- Command-mode LED is controlled by `LED_LISTEN`.
- Moving LED is controlled by the Arduino when a motion command starts and ends.
- Command mode can use grammar-constrained decoding for better command accuracy.
- Command mode supports:
- `forward -> F`
- `backward/back/reverse -> B`
- `left -> L`
- `right -> R`
- `stop -> X`
- `spin -> S`
- Spoken durations are supported, such as `move forward for 1 second`, `turn left for 2 seconds`, or `spin for half second`.
- Then returns to passive mode.
