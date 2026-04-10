# Servo CV

This subtest uses webcam detections to decide whether the camera servo should look left, right, or center.

## Current Behavior

- Opens the webcam feed
- Runs YOLO on each frame
- Tracks the largest detection matching a target label
- Splits the frame into left, center, and right zones
- Sends one of these Arduino commands:
  - `LOOK_LEFT`
  - `LOOK_RIGHT`
  - `LOOK_CENTER`

This is a servo-only CV test. It does not move the drive motors.

## Requirements

- Arduino flashed with servo command support for:
  - `LOOK_LEFT`
  - `LOOK_RIGHT`
  - `LOOK_CENTER`
- Webcam connected and working on the Pi
- `opencv-python`
- `ultralytics`
- YOLO model available on the Pi
- `pyserial`

## Usage

Example:

```bash
cd ~/capstone_project/nova_testing/servo_cv
python3 track_and_pan.py --port /dev/ttyUSB0 --target-label person --show-window
```

Useful options:

- `--port /dev/ttyUSB0`
- `--camera-index 0`
- `--model yolo11n.pt`
- `--target-label person`
- `--confidence 0.45`
- `--deadzone-ratio 0.2`
- `--cooldown 0.75`
- `--show-window`

## Tuning Notes

- If the servo oscillates too much, increase `--cooldown`.
- If the servo overreacts near the frame center, increase `--deadzone-ratio`.
- If you want to track a different object class, change `--target-label`.
- If no target is detected, the script recenters the camera.

## Next Step

If this subtest works, the same left/center/right logic can be moved into the future coordinator architecture as a vision-driven camera behavior service.
