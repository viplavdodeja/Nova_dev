# Nova Dev Status

## Overview

This directory tracks the current development status of the Nova robot stack running across Raspberry Pi and Arduino.

The system is now at a stage where several core subsystems work independently, with integration work still remaining.

## Current Working Components

### 1. Speech-to-Text (STT)

- Raspberry Pi listens for the wake phrase: `Hey Nova`
- After wake detection, the Pi captures spoken command audio
- Speech is transcribed and parsed into robot actions
- Voice command flow is functioning for currently supported commands

### 2. Text-to-Speech (TTS)

- Text output from the LLM can be converted into speaker audio
- Audio playback path is functioning independently

### 3. Computer Vision (CV)

- Raspberry Pi connects to the webcam successfully
- The system can capture frames from the live feed
- Captured frames can be passed into the YOLO-based CV pipeline
- Vision input path is working independently

### 4. Motor Control

- Raspberry Pi sends serial commands to Arduino
- Arduino receives commands and drives the motors
- Basic directional commands are working
- Timed movement commands are working
- Supported motion control currently includes:
  - forward
  - backward
  - turn left
  - turn right
  - spin left
  - spin right
  - U-turn behavior via calibrated timings

### 5. Camera Servo

- Webcam is mounted to a servo controlled by Arduino
- Pi can issue look commands over serial
- Servo look commands currently include:
  - look left
  - look right
  - look forward / center

## Current Limitations

- Motion control is currently time-based, not encoder-based
- Precise physical distance is not yet calibrated
- Turn and spin behavior depends on timing calibration and surface conditions
- Components work independently, but full end-to-end autonomy is still pending

## Pending / Next Steps

- Calibrate forward and backward travel more precisely
- Refine turn and spin timing constants
- Integrate STT -> LLM -> TTS -> motor/CV loop into one coordinated runtime
- Add higher-level action logic that lets the LLM choose safe robot actions
- Incorporate CV context into the action/response pipeline
- Add robust testing for serial command handling and subsystem coordination

## Status Summary

Nova currently has:

- working wake-word-driven voice command input
- working LLM speech output path
- working webcam frame capture for CV
- working Arduino motor control from the Pi
- working servo-based camera positioning

The project is past subsystem bring-up and now entering integration, calibration, and behavior-layer development

