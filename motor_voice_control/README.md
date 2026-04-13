# Motor Voice Control (Pi Side, continuous Vosk)

## Overview
This project runs on Raspberry Pi and sends motor and servo commands to an Arduino over serial, based on live microphone speech.

Pipeline:
1. Continuously stream microphone audio in memory
2. Use Vosk for always-on passive wake and emergency-stop detection
3. Switch to rolling command capture after wake
4. Parse command text into motion or servo payloads
5. Send serial payloads to Arduino

No TTS, no UI, no LLM.

## Serial Command Mapping
- `F` = forward
- `B` = backward
- `L` = left
- `R` = right
- `S` = spin
- `X` = emergency stop
- `<LETTER><milliseconds>` = timed move, for example `F1000`
- `SL<milliseconds>` = spin left
- `SR<milliseconds>` = spin right
- `LOOK_LEFT` = move camera servo left
- `LOOK_RIGHT` = move camera servo right
- `LOOK_CENTER` = center camera servo

## LED State Messages
The Pi also sends LED state tokens to Arduino:
- `LED_READY` in idle/passive mode (blue)
- `LED_LISTEN` while waiting for command input (orange)
- `LED_MOVE` while the Arduino is actively moving (green)

## Project Files
- `main.py`: app loop (passive mode + command mode)
- `speech_listener.py`: continuous Vosk microphone stream for wake and command capture
- `command_parser.py`: wake phrase/emergency/command parsing
- `motor_serial.py`: serial connection and command sending
- `config.py`: all config values
- `requirements.txt`: Python deps

## Python Environment Setup
From your project folder:

```bash
cd ~/capstone_project/nova_testing/motor_voice_control
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Download a Vosk model into this directory or update `VOSK_MODEL_PATH` in `config.py` to point at the model location.

## Verify Microphone Devices
List capture devices:

```bash
python3 -c "import sounddevice as sd; print(sd.query_devices())"
```

Set `MIC_DEVICE_INDEX` in `config.py` if your microphone is not the default input.

## Configure Before Running
Edit these in `config.py`:
- `SERIAL_PORT` (default `/dev/ttyUSB0`)
- `BAUD_RATE` (default `9600`)
- `WAKE_PHRASE` (default `hey nova`)
- `WAKE_REQUIRED_HITS` (set `2` to reduce false wake triggers)
- `PASSIVE_LISTEN_TIMEOUT_SECONDS`
- `COMMAND_LISTEN_TIMEOUT_SECONDS`
- `VOSK_MODEL_PATH`
- `MIC_DEVICE_INDEX`
- `STT_SAMPLE_RATE`
- `STT_BLOCK_SIZE`
- `ROBOT_SPEED_CM_PER_SEC`

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
- Passive listening is continuous and does not rely on temporary WAV files.
- After wake phrase, a rolling command capture session begins on the live stream.
- Idle LED is controlled by `LED_READY`.
- Command-mode LED is controlled by `LED_LISTEN`.
- Moving LED is controlled by the Arduino when a motion command starts and ends.
- Command mode supports:
- `forward -> F`
- `backward/back/reverse -> B`
- `left -> L`
- `right -> R`
- `turn left -> L250`
- `turn right -> R250`
- `u turn -> R450`
- `u turn left -> L450`
- `u turn right -> R450`
- `spin left -> SL900`
- `spin right -> SR900`
- `spin -> SR900`
- `look left -> LOOK_LEFT`
- `look right -> LOOK_RIGHT`
- `look forward -> LOOK_CENTER`
- `stop -> X`
- Spoken distances are supported for forward/backward, such as `move forward 20 cm`, `go backward 12 inches`, or `forward for 10 cm`.
- Spoken durations are supported, such as `move forward for 1 second`, `turn left for 2 seconds`, or `spin for half second`.
- Then returns to passive mode.
