# Motor Voice Control (Pi Side, Whisper STT)

## Overview
This project runs on Raspberry Pi and sends motor and servo commands to an Arduino over serial, based on live microphone speech.

Pipeline:
1. Record short microphone clips with `arecord`
2. Transcribe each clip with `whisper.cpp`
3. Use passive clips for wake and emergency-stop detection
4. Use command clips after wake for constrained command recognition
5. Parse command text into motion or servo payloads
6. Send serial payloads to Arduino

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

## Arduino Safety Stop
The Arduino sketch `Arduino/motor_voice_LED.cpp` enforces an ultrasonic emergency stop.
If the ultrasonic sensor on `PIN_ULTRASONIC` detects an object within 5 inches,
the Arduino immediately stops the motors, cancels the active timed command, sets
the LED to error/red, and prints `ULTRASONIC EMERGENCY STOP`.

## LED State Messages
The Pi also sends LED state tokens to Arduino:
- `LED_READY` in idle/passive mode (blue)
- `LED_LISTEN` while waiting for command input (orange)
- `LED_MOVE` while the Arduino is actively moving (green)

## Project Files
- `main.py`: app loop (passive mode + command mode)
- `speech_listener_whisper_cpp.py`: `arecord` + `whisper.cpp` clip transcription
- `speech_listener.py`: compatibility wrapper exposing the listener API used by the scripts
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

`whisper.cpp` will load the configured model on startup.

## Verify Microphone Devices
The temp-audio path uses `arecord`. To inspect capture devices:

```bash
arecord -l
```

Set `ARECORD_DEVICE` in `config.py` if your microphone is not the default input.

## Configure Before Running
Edit these in `config.py`:
- `SERIAL_PORT` (default `/dev/ttyUSB0`)
- `BAUD_RATE` (default `9600`)
- `WAKE_PHRASE` (default `nova`)
- `WAKE_REQUIRED_HITS` (set `2` to reduce false wake triggers)
- `PASSIVE_LISTEN_TIMEOUT_SECONDS`
- `COMMAND_LISTEN_TIMEOUT_SECONDS`
- `GREETING_COMMANDS`
- `GREETING_LOOK_PAUSE_SECONDS`
- `ARECORD_DEVICE`
- `WHISPER_EXECUTABLE_PATH`
- `WHISPER_MODEL_PATH`
- `WHISPER_THREADS`
- `WHISPER_CPP_PASSIVE_MODE_SECONDS`
- `WHISPER_CPP_COMMAND_MODE_SECONDS`
- `FORWARD_DISTANCE_CALIBRATION_IN`
- `BACKWARD_DISTANCE_CALIBRATION_IN`

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
- `Wake word detected: nova`
- `Heard (command): ...`
- `Command recognized: forward`
- `Sent to Arduino: F`
- `No valid command recognized`

## Behavior Summary
- Passive mode always listens for `"stop"` and sends `X` immediately.
- Passive mode listens for wake word `"nova"`.
- Wake word matching uses the standalone word `nova`, so `hey nova` still works.
- Passive listening records short clips and transcribes them with `whisper.cpp`.
- After wake phrase, command mode records a command clip and transcribes it.
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
- Greetings such as `hello`, `good morning`, `good afternoon`, and `good evening` trigger a sequence:
- `LOOK_LEFT`, wait 1 second
- `LOOK_RIGHT`, wait 1 second
- `SR1030` for a 360 spin
- Spoken distances are supported for forward/backward, such as `move forward 20 cm`, `go backward 12 inches`, or `forward for 10 cm`.
- Distance commands now use lookup-table interpolation from the calibration arrays in `config.py`, not a single global speed constant.
- Spoken durations are supported, such as `move forward for 1 second`, `turn left for 2 seconds`, or `spin for half second`.
- Then returns to passive mode.
