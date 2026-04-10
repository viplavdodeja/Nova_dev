# Nova Recommended Stack

## Core Runtime

- Language: Python 3
- Platform: Raspberry Pi
- Runtime style: single-process coordinator with worker threads or `asyncio`
- Microcontroller: Arduino over serial

## System Roles

### Coordinator Layer

- `coordinator.py`
- `robot_state.py`
- `events.py`

Responsibilities:

- own robot state
- coordinate subsystem activity
- enforce priorities
- route actions safely

## Perception Stack

### Speech-to-Text

- wake-word and command pipeline: existing `motor_voice_control` speech flow
- likely tools already in use:
  - `whisper.cpp`
  - `arecord`

Recommended role in final stack:

- background wake detection
- command capture on demand

### Computer Vision

- OpenCV for camera capture
- Ultralytics YOLO for object detection

Current related files:

- `nova_testing/vision.py`
- `nova_testing/webcam_setup/`
- `nova_testing/servo_cv/`

Recommended role in final stack:

- default environment perception
- optional target tracking input for servo control

## Action Stack

### Motion Control

- Raspberry Pi -> serial -> Arduino
- Arduino handles motor shield control and timed execution

Current related files:

- `nova_testing/motor_voice_control/motor_serial.py`
- Arduino motor sketch in your flashed `main.cpp`

Recommended role in final stack:

- expose only calibrated motion primitives
- do not expose raw serial strings to the LLM

### Servo Control

- Arduino `Servo` library
- serial commands from Pi

Recommended command interface:

- `LOOK_LEFT`
- `LOOK_RIGHT`
- `LOOK_CENTER`
- `SV<angle>` for incremental angle control

### Text-to-Speech

- Piper HTTP or Piper CLI
- optional `espeak` fallback

Current related config:

- `PIPER_HTTP_URL`
- `PIPER_VOICE`
- `PIPER_COMMAND`
- `ENABLE_TTS_FALLBACK_ESPEAK`

Recommended role in final stack:

- speak LLM-generated output
- coordinator-controlled playback only

## Reasoning Stack

### LLM Layer

- Ollama-hosted local model

Current related config:

- `OLLAMA_URL`
- `OLLAMA_MODEL`

Recommended role in final stack:

- interpret user intent
- generate speech responses
- select from a constrained action vocabulary

Do not use the LLM for:

- raw servo angles
- raw motor serial payloads
- direct hardware timing decisions

## Messaging / Coordination Model

Recommended now:

- in-process event queue
- shared state object

Recommended later if needed:

- multiprocessing queues
- local sockets
- ZeroMQ

Do not start with ROS2 unless the project scope grows substantially.

## Suggested File Layout

- `nova_dev/coordinator.py`
- `nova_dev/robot_state.py`
- `nova_dev/events.py`
- `nova_dev/audio_service.py`
- `nova_dev/vision_service.py`
- `nova_dev/motion_service.py`
- `nova_dev/servo_service.py`
- `nova_dev/tts_service.py`
- `nova_dev/llm_service.py`
- `nova_dev/config.py`

## Action API Recommendation

The coordinator should work with structured actions like:

- `speak(text)`
- `forward()`
- `backward()`
- `turn_left()`
- `turn_right()`
- `u_turn_left()`
- `u_turn_right()`
- `spin_left()`
- `spin_right()`
- `look_left()`
- `look_right()`
- `look_center()`
- `set_servo_angle(angle)`
- `track_target(label)`
- `stop()`

## State Model Recommendation

Use these primary states:

- `observe`
- `command_mode`
- `executing_motion`
- `speaking`
- `paused_for_safety`
- `error`

## Priority Model Recommendation

Priority order:

1. emergency stop
2. hardware fault / safety hold
3. active user voice command
4. motion completion / execution bookkeeping
5. autonomous CV-driven behavior

## Development Strategy

### Best immediate stack choice

- one Python coordinator
- OpenCV + YOLO for vision
- existing whisper.cpp-based STT path
- existing serial motion path
- existing TTS path
- Ollama for local LLM reasoning

### Why this stack

- it matches what already works
- it minimizes rewrite
- it keeps latency and integration complexity manageable on the Pi
- it gives a clear path from subsystem tests to one integrated robot runtime
