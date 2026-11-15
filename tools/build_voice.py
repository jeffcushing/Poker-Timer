#!/usr/bin/env python3
"""Render announcer clips with a macOS voice and embed them in poker-timer.html.

Usage: python3 tools/build_voice.py ["Voice Name (Premium)"]
Requires macOS `say` and `afconvert`. Re-run after changing phrases or voice.
"""
import array, base64, json, os, re, subprocess, sys, tempfile, wave
from concurrent.futures import ThreadPoolExecutor

VOICE = sys.argv[1] if len(sys.argv) > 1 else "Matilda (Premium)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ROOT, "poker-timer.html")
RATE = 22050

PHRASES = {
    "blinds_intro": "The new blinds are",
    "and":          "and",
    "one_min":      "One minute remains in this round.",
    "break_time":   "Break time. You have",
    "minutes":      "minutes.",
    "break_over":   "Break is over.",
    "colorup_intro":"Time to color up the",
    "chips":        "chips.",
    "paused":       "The timer is paused.",
}
CHIP_NAMES = ["White", "Red", "Blue", "Green", "Black",
              "Grey", "Orange", "Pink", "Purple", "Yellow", "Light Blue", "Brown"]
for name in CHIP_NAMES:
    PHRASES["chip_" + name.lower()] = name

NUMBERS = sorted(set(list(range(1, 61)) + list(range(5, 1001, 5)) +
                     list(range(1000, 10001, 100)) + list(range(10000, 100001, 1000))))
# n<val> = mid-sentence number, n<val>f = sentence-final number (falling tone)
for n in NUMBERS:
    PHRASES[f"n{n}"] = str(n)
    PHRASES[f"n{n}f"] = f"{n}."


def trim(samples, thr=250, pad=int(RATE * 0.02)):
    start = next((i for i, x in enumerate(samples) if abs(x) > thr), 0)
    end = len(samples) - next((i for i, x in enumerate(reversed(samples)) if abs(x) > thr), 0)
    return samples[max(0, start - pad):min(len(samples), end + pad)]


def render(item):
    key, text = item
    with tempfile.TemporaryDirectory() as d:
        raw, clean, out = (os.path.join(d, f) for f in ("raw.wav", "clean.wav", "out.aac"))
        subprocess.run(["say", "-v", VOICE, f"--data-format=LEI16@{RATE}", "-o", raw, text], check=True)
        w = wave.open(raw)
        samples = array.array("h", w.readframes(w.getnframes()))
        w.close()
        w = wave.open(clean, "w")
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(trim(samples).tobytes()); w.close()
        subprocess.run(["afconvert", "-f", "adts", "-d", "aac", "-b", "24000", clean, out], check=True)
        with open(out, "rb") as f:
            return key, base64.b64encode(f.read()).decode()


def main():
    if VOICE not in subprocess.run(["say", "-v", "?"], capture_output=True, text=True).stdout:
        sys.exit(f"Voice not installed: {VOICE}")
    with ThreadPoolExecutor(max_workers=os.cpu_count() or 4) as pool:
        clips = dict(pool.map(render, PHRASES.items()))
    payload = json.dumps({"voice": VOICE, "clips": clips}, separators=(",", ":"))
    with open(HTML, encoding="utf-8") as f:
        html = f.read()
    new, n = re.subn(r"/\*VOICE_CLIPS_START\*/.*?/\*VOICE_CLIPS_END\*/",
                     lambda _: f"/*VOICE_CLIPS_START*/{payload}/*VOICE_CLIPS_END*/", html, flags=re.S)
    if n != 1:
        sys.exit("Markers /*VOICE_CLIPS_START*/ ... /*VOICE_CLIPS_END*/ not found in poker-timer.html")
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"Embedded {len(clips)} clips ({len(payload) / 1e6:.1f} MB) using {VOICE}")


if __name__ == "__main__":
    main()
