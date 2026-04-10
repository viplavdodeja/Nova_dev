# Servo CV

This subtest uses webcam detections to decide whether the camera servo should look left, right, or center.

This version now uses incremental servo angle control instead of only three fixed positions.

## Current Behavior

- Opens the webcam feed
- Runs YOLO on each frame
- Tracks the largest detection matching a target label
- Computes horizontal target error relative to frame center
- Nudges the servo in small steps toward the target
- Sends Arduino angle commands in this format:
  - `SV<angle>`

This is a servo-only CV test. It does not move the drive motors.

## Requirements

- Arduino flashed with servo command support for:
  - `SV<angle>`
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
- `--servo-center-angle 90`
- `--servo-min-angle 20`
- `--servo-max-angle 160`
- `--small-step 3`
- `--large-step 7`
- `--cooldown 0.2`
- `--confirm-frames 2`
- `--lost-target-hold-seconds 1.0`
- `--show-window`

## Tuning Notes

- If the servo oscillates too much, increase `--deadzone-ratio` and reduce `--small-step`.
- If the servo tracks too slowly, increase `--small-step` or `--large-step`.
- If the servo overreacts near the frame center, increase `--deadzone-ratio`.
- If the servo still flips between directions, increase `--confirm-frames`.
- If the servo recenters too aggressively when detection flickers, increase `--lost-target-hold-seconds`.
- If you want to track a different object class, change `--target-label`.
- If no target is detected, the script recenters the camera.

Recommended starting point:

```bash
python3 track_and_pan.py --port /dev/ttyUSB0 --target-label person --deadzone-ratio 0.3 --small-step 2 --large-step 5 --cooldown 0.25 --confirm-frames 2 --lost-target-hold-seconds 1.0 --show-window
```

## Next Step

If this subtest works, the same left/center/right logic can be moved into the future coordinator architecture as a vision-driven camera behavior service.
