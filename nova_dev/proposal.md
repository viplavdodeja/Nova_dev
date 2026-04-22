# Nova Integration Proposal

## Goal

Build an overarching runtime for Nova where:

- computer vision runs continuously by default
- wake-word listening runs continuously in the background
- the robot can respond to user voice commands at any time
- command mode temporarily pauses or throttles CV while the command is handled
- motion, speech, and perception are coordinated by a single control layer

## Recommended Architecture

Use a central event-driven coordinator on the Raspberry Pi with explicit robot state.

Core modules:

- `Coordinator / State Machine`
- `Audio Service`
- `Vision Service`
- `Motion Service`
- `LLM / Decision Service`
- `TTS Service`

The coordinator is the only module allowed to decide what the robot does next.

## Why This Architecture

This keeps subsystems from fighting each other.

Without a coordinator:

- CV may trigger behavior while a user is speaking
- the LLM may issue actions while motion is already running
- TTS may overlap with command listening
- motor commands may be issued from multiple places at once

With a coordinator:

- all subsystems publish events
- one component owns robot state
- one component decides when CV pauses, when motion starts, and when speaking is allowed

## Proposed Runtime Model

### 1. Coordinator

The coordinator owns high-level control flow and robot state.

Responsibilities:

- maintain current operating state
- receive events from subsystems
- decide what action to execute next
- block or queue lower-priority actions while a higher-priority task is active
- enforce safe transitions between perception, speaking, and motion

### 2. Audio Service

Responsibilities:

- always-on wake phrase detection
- command capture after wake phrase
- emergency stop detection
- publish events such as:
  - `wake_detected`
  - `command_heard`
  - `emergency_stop_detected`

### 3. Vision Service

Responsibilities:

- keep webcam stream active
- run frame capture continuously
- run inference when enabled
- publish events such as:
  - `object_detected`
  - `person_detected`
  - `scene_update`

Recommendation:

- keep camera capture alive even when command mode is active
- pause or throttle only the expensive CV inference stage
- this avoids webcam reconnect overhead

### 4. Motion Service

Responsibilities:

- send serial commands to Arduino
- expose safe action primitives only
- publish:
  - `motion_started`
  - `motion_completed`
  - `motion_failed`

Important:

- the LLM should not generate raw serial strings directly
- the motion service should accept only known commands like:
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

### 5. LLM / Decision Service

Responsibilities:

- interpret user intent
- convert CV context into high-level decisions
- generate spoken responses
- recommend safe high-level actions

Important boundary:

- the LLM should choose from allowed actions
- the coordinator should decide whether those actions are allowed in the current state

### 6. TTS Service

Responsibilities:

- convert text output into speaker audio
- publish:
  - `tts_started`
  - `tts_finished`

The coordinator should control when TTS is allowed so speech does not interfere with command listening.

## Proposed Robot States

Use an explicit finite-state model.

Suggested states:

- `observe`
- `listening_for_wake`
- `command_mode`
- `executing_motion`
- `speaking`
- `paused_for_safety`
- `error`

Practical interpretation:

- `observe`: default mode, CV active, wake listening active
- `command_mode`: user command capture in progress, CV inference paused
- `executing_motion`: robot is moving or repositioning servo
- `speaking`: robot is responding through TTS
- `paused_for_safety`: emergency stop or safety hold
- `error`: subsystem failure or invalid state

## Example Control Flow

### Default behavior

1. Start wake listening
2. Start webcam capture
3. Start CV inference
4. Remain in `observe`

### User voice command flow

1. Audio service detects `Nova`
2. Coordinator transitions to `command_mode`
3. Coordinator pauses or throttles CV inference
4. Audio service captures the user command
5. Parser / LLM interprets the command
6. Coordinator selects an action
7. If the action is motion, transition to `executing_motion`
8. Motion service sends Arduino command and waits for completion
9. Resume CV inference
10. Return to `observe`

### Conversational flow

1. User says `Nova`
2. Coordinator enters `command_mode`
3. User asks a question instead of a robot action
4. LLM generates a text response
5. Coordinator transitions to `speaking`
6. TTS service plays the response
7. Coordinator returns to `observe`

### Emergency stop flow

1. Audio service detects stop phrase
2. Coordinator sends immediate stop command
3. Transition to `paused_for_safety`
4. Ignore non-critical actions until system is stable

## Priority Rules

Recommended priority order:

1. emergency stop
2. hardware or safety faults
3. active user voice commands
4. motion completion events
5. autonomous CV-triggered behavior

This prevents autonomous behavior from overriding the user.

## Recommended Implementation Approach

### Phase 1: Single-process coordinator

Best immediate option.

Use one Python process with either:

- `asyncio`, or
- a central loop with worker threads

This process should host:

- audio listener task
- CV task
- motion controller wrapper
- TTS wrapper
- LLM wrapper
- central coordinator/state machine

Benefits:

- easiest to debug
- lowest integration overhead
- good fit for current prototype stage

### Phase 2: Service split if needed

If the codebase grows, split into separate processes:

- `audio_service.py`
- `vision_service.py`
- `motion_service.py`
- `tts_service.py`
- `coordinator.py`

Use queues or local sockets for communication.

This should be a later step, not the first step.

## Recommended Code Organization

Suggested layout inside `nova_dev`:

- `proposal.md`
- `coordinator.py`
- `robot_state.py`
- `events.py`
- `audio_service.py`
- `vision_service.py`
- `motion_service.py`
- `tts_service.py`
- `llm_service.py`
- `config.py`

Possible support folders:

- `logs/`
- `tests/`
- `adapters/`

## Integration Guidance

### Keep these layers separate

- Perception:
  - STT
  - CV
- Interpretation:
  - command parser
  - LLM
- Action selection:
  - coordinator/state machine
- Execution:
  - motor serial commands
  - servo commands
  - TTS playback

This separation keeps the system easier to debug and safer to extend.

### Motion design rule

Do not let the LLM invent arbitrary low-level commands.

Instead, expose a small set of calibrated actions and let the coordinator translate those to serial payloads.

### Vision design rule

Do not let CV directly move the robot without coordinator approval.

CV should publish observations, not motor commands.

## Near-Term Development Plan

### Step 1

Create `robot_state.py` and define the state enum.

### Step 2

Create `events.py` and define a small event model for:

- wake detected
- command heard
- emergency stop
- motion completed
- tts finished
- object detected

### Step 3

Create `motion_service.py` as a clean wrapper around the existing motor and servo command logic.

### Step 4

Create `coordinator.py` with:

- state tracking
- event handling
- CV pause/resume control
- motion execution control
- TTS control

### Step 5

Wire in existing STT and CV modules as services feeding events into the coordinator.

### Step 6

Add LLM decision routing for:

- user conversational responses
- user-issued robot actions
- environment-aware suggestions or autonomous behavior

## Summary

The best fit for Nova right now is:

- one central coordinator
- explicit robot states
- continuous wake listening
- CV active by default
- CV paused or throttled during command execution
- motion and TTS controlled through safe action primitives

This gives a stable path from independently working components to a single integrated robot runtime.
