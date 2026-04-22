# Nova Demo Launchers

Run these from this directory to start the main Nova demos while keeping the
original source files in place.

```bash
python3 voice_motor_control.py
python3 servo_person_tracker.py
python3 vision_llm_speech.py
```

## Launchers

- `voice_motor_control.py` runs `../motor_voice_control/main.py`
- `servo_person_tracker.py` runs `../servo_cv/track_and_pan.py`
- `vision_llm_speech.py` runs `../main.py`

Any command-line arguments are passed through to the original script. For
example:

```bash
python3 servo_person_tracker.py --port /dev/ttyUSB0 --show-window
```
