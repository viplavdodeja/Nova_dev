# Nova Demo Launchers

Run these from this directory to start the main Nova demos while keeping the
original source files in place.

```bash
python3 voice_motor_control.py
python3 motor_voice_control_fast_demo.py
python3 motor_voice_control_preset.py
python3 motor_voice_control_llm.py
python3 servo_person_tracker.py
python3 vision_llm_speech.py
```

## Launchers

- `voice_motor_control.py` runs `../motor_voice_control/main.py`
- `motor_voice_control_fast_demo.py` runs a lower-latency demo with continuous Vosk, background tracking, greeting animation, and preset TTS
- `motor_voice_control_preset.py` runs motor voice control with preset greeting speech
- `motor_voice_control_llm.py` runs motor voice control with CV-aware LLM greeting speech
- `servo_person_tracker.py` runs `../servo_cv/track_and_pan.py`
- `vision_llm_speech.py` runs `../main.py`

## Greeting Speech Demos

`motor_voice_control_fast_demo.py` is the recommended demo path when latency
matters. It keeps Vosk listening continuously, pauses YOLO tracking during
command capture, and keeps TTS loaded in a background worker.

`motor_voice_control_preset.py` uses fixed phrases:

- `good morning` -> `Good morning`
- `hello` -> `Hello I'm NOVA`

It also runs the person-tracking servo loop in the background and pauses it
while the greeting animation is playing.

`motor_voice_control_llm.py` captures one current webcam frame, summarizes it with YOLO,
asks the LLM for a short greeting response using that scene summary, and speaks it.
It runs the person-tracking servo loop in the background, then temporarily stops
tracking during greeting capture/animation so the camera is available for the
LLM scene snapshot.

Any command-line arguments are passed through to the original script. For
example:

```bash
python3 servo_person_tracker.py --port /dev/ttyUSB0 --show-window
```
