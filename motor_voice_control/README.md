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
- `S` = spin (also used for passive emergency stop trigger)
- `X` = emergency stop command-mode mapping

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

If needed, set `ARECORD_DEVICE` in `config.py` (example: `hw:1,0`).

## Verify whisper.cpp Manually
Record a quick sample:

```bash
arecord -D default -f S16_LE -r 16000 -c 1 -d 3 test.wav
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
- `PASSIVE_CLIP_DURATION_SECONDS`
- `COMMAND_CLIP_DURATION_SECONDS`
- `WHISPER_EXECUTABLE_PATH`
- `WHISPER_MODEL_PATH`
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
- `Sent to Arduino: S`
- `Wake phrase detected: hey nova`
- `Heard (command): ...`
- `Command recognized: forward`
- `Sent to Arduino: F`
- `No valid command recognized`

## Behavior Summary
- Passive mode always listens for `"stop"` and sends `S` immediately.
- Passive mode listens for wake phrase `"hey nova"`.
- After wake phrase, one command clip is recorded and parsed.
- Command mode supports:
  - `forward -> F`
  - `backward/back/reverse -> B`
  - `left -> L`
  - `right -> R`
  - `stop -> X`
  - `spin -> S`
- Then returns to passive mode.
