# Motor Calibration

This directory contains a small serial test utility for calibrating motion timings from an SSH terminal on the Pi.

## Supported Actions

- `forward`
- `backward`
- `left-turn`
- `right-turn`
- `spin-left`
- `spin-right`

## Usage

List detected serial ports:

```bash
python3 send_motion.py --list-ports
```

Send a timed motion:

```bash
python3 send_motion.py forward 1000 --port /dev/ttyACM0 --read-response
```

```bash
python3 send_motion.py backward 800 --port /dev/ttyACM0 --read-response
```

```bash
python3 send_motion.py left-turn 750 --port /dev/ttyACM0 --read-response
```

```bash
python3 send_motion.py right-turn 750 --port /dev/ttyACM0 --read-response
```

```bash
python3 send_motion.py spin-left 2500 --port /dev/ttyACM0 --read-response
```

```bash
python3 send_motion.py spin-right 2500 --port /dev/ttyACM0 --read-response
```

Send a raw serial message directly:

```bash
python3 send_motion.py --raw X --port /dev/ttyACM0 --read-response
```

## Serial Payload Mapping

- `forward` -> `F<duration_ms>`
- `backward` -> `B<duration_ms>`
- `left-turn` -> `L<duration_ms>`
- `right-turn` -> `R<duration_ms>`
- `spin-left` -> `SL<duration_ms>`
- `spin-right` -> `SR<duration_ms>`

Examples:

- `forward 1000` sends `F1000`
- `right-turn 820` sends `R820`
- `spin-left 3200` sends `SL3200`
- `spin-right 3200` sends `SR3200`
