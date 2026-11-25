"""Read-only hardware check. Run on the Pi: python3 check_hw.py

Checks that the Pico is sending telemetry, the LiDAR is sending valid
packets, and the camera gives frames -- without moving or configuring
anything. Safe to run at any time.

No hardware library is imported at module level, so this file can still
be imported (e.g. by a unit test) on a laptop that has none of them.
"""
import time


def load_config(path="config.yaml"):
    import yaml
    with open(path) as f:
        return yaml.safe_load(f)


def check_pico(cfg):
    import serial

    port = cfg["pico"]["port"]
    baud = cfg["pico"]["baud"]
    timeout_s = cfg["check"]["pico_timeout_s"]
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        return False, f"cannot open {port}: {e}"

    buf = b""
    count = 0
    last_line = None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        buf += ser.read(256)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.decode(errors="ignore").strip()
            if line.startswith("E,"):
                count += 1
                last_line = line
    ser.close()

    if count == 0:
        return False, "no E (telemetry) lines received"
    return True, f"{count} E lines in {timeout_s:.0f}s, last: {last_line}"


# LD06/LD19 packets use CRC-8 with polynomial 0x4D, MSB first, computed
# over all bytes except the CRC byte itself (which is the last byte).
def _crc8_table(poly=0x4D):
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
        table.append(crc)
    return table


_CRC_TABLE = _crc8_table()
_LIDAR_HEADER = b"\x54\x2c"
_LIDAR_PACKET_LEN = 47


def _crc8(data):
    crc = 0
    for b in data:
        crc = _CRC_TABLE[(crc ^ b) & 0xFF]
    return crc


def _packet_valid(packet):
    return len(packet) == _LIDAR_PACKET_LEN and _crc8(packet[:-1]) == packet[-1]


def _packet_first_distance_mm(packet):
    # Header(2) + speed(2) + start_angle(2), then distance(u16 LE) + intensity(u8)
    return packet[6] | (packet[7] << 8)


def check_lidar(cfg):
    import serial

    port = cfg["lidar"]["port"]
    baud = cfg["lidar"]["baud"]
    timeout_s = cfg["check"]["lidar_timeout_s"]
    try:
        ser = serial.Serial(port, baud, timeout=0.5)
    except Exception as e:
        return False, f"cannot open {port}: {e}"

    buf = b""
    valid = 0
    invalid = 0
    sample_mm = None
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        buf += ser.read(256)
        while True:
            idx = buf.find(_LIDAR_HEADER)
            if idx < 0 or len(buf) < idx + _LIDAR_PACKET_LEN:
                break
            packet = buf[idx:idx + _LIDAR_PACKET_LEN]
            buf = buf[idx + _LIDAR_PACKET_LEN:]
            if _packet_valid(packet):
                valid += 1
                if sample_mm is None:
                    sample_mm = _packet_first_distance_mm(packet)
            else:
                invalid += 1
    ser.close()

    if valid == 0:
        return False, f"no valid packets (invalid={invalid})"
    return True, f"{valid} valid packets, sample distance={sample_mm}mm"


def check_camera(cfg):
    width = cfg["camera"]["width"]
    height = cfg["camera"]["height"]
    timeout_s = cfg["check"]["camera_timeout_s"]
    if cfg["camera"]["type"] == "picamera2":
        return _check_picamera2(width, height, timeout_s)
    return _check_usb_camera(cfg["camera"]["index"], width, height, timeout_s)


def _check_picamera2(width, height, timeout_s):
    try:
        from picamera2 import Picamera2
    except Exception as e:
        return False, f"picamera2 not available: {e}"

    try:
        cam = Picamera2()
        cam.configure(cam.create_video_configuration(main={"size": (width, height)}))
        cam.start()
        frames = 0
        start = time.time()
        while time.time() - start < timeout_s:
            cam.capture_array()
            frames += 1
        cam.stop()
        cam.close()
    except Exception as e:
        return False, f"picamera2 error: {e}"

    if frames == 0:
        return False, "no frames captured"
    return True, f"{frames} frames in {timeout_s:.0f}s ({frames / timeout_s:.1f} fps)"


def _check_usb_camera(index, width, height, timeout_s):
    try:
        import cv2
    except Exception as e:
        return False, f"opencv not available: {e}"

    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        return False, f"cannot open camera index {index}"
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    frames = 0
    start = time.time()
    while time.time() - start < timeout_s:
        ok, _ = cap.read()
        if ok:
            frames += 1
    cap.release()

    if frames == 0:
        return False, "no frames captured"
    return True, f"{frames} frames in {timeout_s:.0f}s ({frames / timeout_s:.1f} fps)"


def main():
    cfg = load_config()
    checks = [
        ("Pico", check_pico),
        ("LiDAR", check_lidar),
        ("Camera", check_camera),
    ]
    all_ok = True
    for name, fn in checks:
        ok, msg = fn(cfg)
        all_ok = all_ok and ok
        print(f"[{'OK' if ok else 'FAIL'}] {name}: {msg}")

    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
