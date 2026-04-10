# Nova Implementation Outline

## Objective

Integrate Nova's currently independent subsystems into one coordinated runtime on the Raspberry Pi.

The target behavior is:

- CV runs by default
- wake-word listening runs continuously in the background
- user voice commands can interrupt the default behavior
- command mode pauses or throttles CV
- motion, servo movement, and TTS are coordinated through one controller

## Phase 1: Foundations

### 1. Define robot state

Create a shared state model for:

- `observe`
- `command_mode`
- `executing_motion`
- `speaking`
- `paused_for_safety`
- `error`

### 2. Define event model

Create a common event layer for:

- `wake_detected`
- `command_received`
- `emergency_stop`
- `motion_started`
- `motion_completed`
- `servo_completed`
- `tts_started`
- `tts_finished`
- `vision_detection`
- `vision_target_lost`

### 3. Normalize subsystem interfaces

Each subsystem should expose a clean interface:

- audio service returns wake and command events
- vision service returns detections and optional target position
- motion service exposes calibrated motion primitives
- servo service exposes look and angle primitives
- TTS service plays text and signals completion
- LLM service returns structured actions and spoken output

## Phase 2: Coordinator Runtime

### 4. Build coordinator

Create a central coordinator that:

- owns the active robot state
- receives subsystem events
- decides which subsystem is allowed to act
- enforces priority and safety rules

### 5. Add default observation loop

Default runtime behavior:

- wake listener active
- camera capture active
- CV active
- no motion unless requested by the user or by an approved autonomous rule

### 6. Add command mode transitions

When `wake_detected` occurs:

- transition to `command_mode`
- pause or throttle CV inference
- capture speech command
- parse command
- either execute action directly or send to LLM for interpretation

### 7. Add execution routing

The coordinator should route actions to:

- motion service for drive commands
- servo service for look or tracking commands
- TTS service for spoken replies

## Phase 3: LLM Integration

### 8. Restrict LLM output to safe actions

The LLM should not emit raw serial strings.

It should only choose from a structured action set such as:

- `speak`
- `forward`
- `backward`
- `turn_left`
- `turn_right`
- `u_turn_left`
- `u_turn_right`
- `spin_left`
- `spin_right`
- `look_left`
- `look_right`
- `look_center`
- `track_target`
- `stop`

### 9. Add context packaging

The coordinator should build LLM inputs from:

- current robot state
- recent speech transcript
- summarized CV detections
- current target tracking state

### 10. Add response policy

The coordinator should decide whether the LLM output becomes:

- speech only
- motion only
- speech followed by motion
- no action

## Phase 4: Vision-Guided Behavior

### 11. Add servo tracking mode

Move the current `servo_cv` test into a reusable service.

Tracking mode should:

- detect the target
- estimate horizontal error
- adjust servo angle incrementally
- expose target state to the coordinator

### 12. Add autonomous observation behavior

Examples:

- track a person while idle
- center the camera when the target is lost
- announce detected objects when asked

Autonomous behavior must remain lower priority than user commands.

## Phase 5: Safety and Stability

### 13. Add emergency stop handling

Emergency stop must:

- interrupt active motion
- override autonomous CV behavior
- place the system into `paused_for_safety`

### 14. Add subsystem watchdogs

Handle failures such as:

- serial disconnects
- camera disconnects
- failed inference
- failed TTS playback

### 15. Add logging

Log:

- state transitions
- received commands
- serial payloads
- CV detections
- LLM actions
- failures and retries

## Phase 6: Validation

### 16. Subsystem validation

Confirm each subsystem still works independently:

- STT
- TTS
- CV
- motion
- servo

### 17. Integration validation

Validate combined flows:

- wake -> command -> motion -> resume CV
- wake -> question -> TTS reply -> resume CV
- observe -> detect target -> servo tracking
- motion active -> emergency stop

### 18. Behavior tuning

Tune:

- motion calibration values
- servo tracking gains
- CV cadence
- wake-word sensitivity
- TTS interruption behavior

## First Build Target

The first integrated milestone should be:

- one `coordinator.py`
- one state enum
- one event model
- CV active in observe mode
- wake-word listener active in background
- command mode pauses CV
- basic motion and servo actions routed through clean services

This is the minimum viable integrated architecture.
