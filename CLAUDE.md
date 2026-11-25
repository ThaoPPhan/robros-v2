# Robros v2: rebuild step by step, starting with MANUAL mode

## How we work (read this first)
- I am rebuilding the robot software from scratch to UNDERSTAND it. Last time too much was built
  without testing on the real robot. This time: ONE milestone at a time.
- After each milestone: STOP. Tell me exactly how to test it on the real robot, then WAIT for my
  result before starting the next milestone. Never start the next milestone on your own.
- Keep code small and readable: short files, plain Python, comments that explain WHY.
  After writing a file, explain in a few sentences what it does and how it fits the rest.
- Explain things to me in Vietnamese; keep code, comments and file names in English.
- Scope for now: MANUAL mode only (competition stage 1). Do NOT write autonomous driving, lane
  following, route plans or obstacle avoidance until I explicitly ask.
- The old project `~/robros-pi3` is reference only: you may read it and copy small pieces
  (e.g. the LiDAR packet parser, the Pico firmware) but explain what you copy. Never modify it.

## Development setup
- Claude Code runs on my LAPTOP in `~/robros-v2`. The robot is a Raspberry Pi 3B at `pi@pi.local`
  (passwordless SSH). The Pi has too little RAM to run Claude Code.
- `deploy.sh`: rsync this folder to `pi@pi.local:~/robros-v2/` (exclude .git, logs/, __pycache__).
  `fetch_logs.sh`: rsync `pi@pi.local:~/robros-v2/logs/` back to `./logs/`.
- Hardware libraries (picamera2, lgpio) don't exist on the laptop: import them inside functions or
  behind try/except so unit tests run locally.
- Only apt packages on the Pi: python3-opencv, python3-numpy, python3-yaml, python3-flask,
  python3-serial, python3-picamera2. No pip installs on the Pi unless I agree.
- SAFETY: never run anything on the Pi that can move the motors without asking me first and waiting
  for my OK. Read-only checks over SSH (list devices, run a camera test, read the LiDAR) are fine.
  Long-running programs (web server, robot program): give me the exact command; I start them myself.

## Competition facts that matter for MANUAL mode
- Stage 1 = manual: we drive the robot along the track while watching the robot's own camera.
- The robot carries an open box with 1 kg of sand. Sand lost = penalty, so all speed changes must be
  smooth (ramped) and turns gentle. Finishing with the payload matters more than speed.
- Live forward camera viewed by the team is mandatory.
- Physical master switch exists (hardware). Software stop is extra, not a replacement.
- Track: 90 cm wide lane with blue tape edges, about 24 m, six sharp 90° corners.

## Hardware (all wired and powered)
- Raspberry Pi 3B, Raspberry Pi OS 64-bit, on a wall charger (micro-USB 5 V / 2.5 A).
  CPU is weak: camera at 320x240, simple code.
- Pico (RP2040 clone) on USB: `/dev/ttyACM0`. Firmware: `pico_motor_controller.ino`
  (copy from `~/robros-pi3/pico_motor_controller/`). It drives 2 motors through 2 DRV8871 and reads
  2 quadrature encoders.
- Pico protocol (text lines ending in `\n`):
  - Pi -> Pico: `M,<left>,<right>` wheel speeds -1..1; `S,<steer>,<speed>` (steer + = right);
    `H,<seq>` heartbeat (send >= 5/s); `R` reset encoders; `X` stop.
  - Pico -> Pi, 20 Hz: `E,<ms>,<countL>,<countR>,<rateL>,<rateR>,<outL>,<outR>,<failsafe>`
  - Pico stops the motors if no M/S command for 300 ms (or heartbeats stop for 600 ms after
    being seen). It ramps acceleration itself (1.5/s up, 3.0/s down).
- Camera: Pi Camera v1.3 on the ribbon port (picamera2), or a USB camera (`cv2.VideoCapture(0)`).
  Make it selectable in config.
- LiDAR (LDRobot/LeDong LD06/LD19 class) on `/dev/serial0`, 230400 baud, 47-byte packets:
  `0x54 0x2C`, speed (u16), start angle (u16, 0.01°), 12 x (distance mm u16, intensity u8),
  end angle (u16), timestamp (u16), CRC8 poly 0x4D. 0° = sensor front, clockwise. Distance 0 = none.
- Motors: JGA25-370 12 V with encoders; battery 12.6 V Li-ion through a master switch.

## Milestones (do them in order, one per session; wait for my test result after each)

**M0: Skeleton + hardware check.**
`config.yaml` (ports, camera type, speeds), `deploy.sh`, `fetch_logs.sh`, and `check_hw.py` that
reports, without moving anything: Pico port present and sending E lines, LiDAR port present and
packets valid, camera gives frames (fps). Done when: I run `python3 check_hw.py` on the Pi and all
three show OK.

**M1: Talk to the Pico.** `pico_link.py`: a class that opens the port, sends commands + heartbeat
from a background thread at 20 Hz, and keeps the latest telemetry. Plus `test_pico.py`: wheels
forward 1 s, back 1 s, stop, printing encoder counts. Done when: wheels (lifted) move as expected and
counts rise forward / fall backward.

**M2: Camera stream.** `camera.py` (picamera2 or USB, 320x240) + `web.py` (Flask) serving a page with
the live MJPEG video on port 8000. Done when: I see smooth video at `http://pi.local:8000` and the
terminal prints the fps.

**M3: Drive from the browser.** Same page: hold W/A/S/D to drive, release = stop, speed slider, big
STOP button, space = stop. Browser sends commands about 10 times a second; if the robot hears nothing
for 0.3 s it stops. Done when: driving works and closing the tab stops the robot.

**M4: The control loop.** `robot.py` with ONE loop at 20 Hz: read inputs (browser command, telemetry)
-> decide (mode STOP or MANUAL) -> safety checks -> send to the Pico -> log one CSV row in
`logs/`. Starts in STOP. Gentle turn limit for the sand. Page shows mode, encoder counts/speeds, Pico
status. Done when: same driving as M3 but through the loop, and a log file appears.

**M5: LiDAR in the loop.** LiDAR reader thread, nearest distance in front shown on the page, a small
top-down map, and an optional emergency stop in MANUAL when something is closer than X cm ahead
(checkbox to disable). Done when: a box in front shows up and triggers the stop.

**M6: Polish for the competition run.** Gamepad support (browser Gamepad API), snapshot button,
smoother speed response, a one-page "how to run on competition day" in README.md. Done when: I drive a
mock track with the sand box without spilling.

## Rules for the code
- One program owns each port at a time (`/dev/ttyACM0`, `/dev/serial0`).
- Default to safe: start stopped; on any error, lost Pico, lost browser or Ctrl-C -> send stop.
- Every tunable number lives in `config.yaml`, not in the code.
- Add a small unit test when logic can be tested without hardware (parsers, command mixing, timeouts).