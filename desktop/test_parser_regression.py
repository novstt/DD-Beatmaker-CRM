import re
ID3 = None
from pathlib import Path

src = Path(__file__).with_name("main.py").read_text(encoding="utf-8")
ns = {}
# Extract only constants + parser function, avoiding Qt imports.
start = src.index("KEY_PATTERN = ")
end = src.index("\n\nclass AddBeatDialog", start)
block = src[start:end]
exec(block, globals())

cases = {
    "SLV - TITANIUM - F#min - 140BPM.mp3": (140, "F# minor"),
    "TITANIUM 150 BPM C# minor.mp3": (150, "C# minor"),
    "test_147bpm_Am.mp3": (147, "A minor"),
    "beat_99BPM_Bbmajor.mp3": (99, "Bb major"),
    "TITANIUM 40 bpm.mp3": (40, None),
    "TITANIUM 300 BPM.mp3": (300, None),
}

for filename, expected in cases.items():
    meta = parse_beat_filename(filename)
    assert meta["bpm"] == expected[0], (filename, meta)
    if expected[1]:
        assert meta["musical_key"] == expected[1], (filename, meta)

# Regression: the old broken regex must never be present.
assert "[4-3]" not in src

print("Parser regression tests: OK")

# Producer-credit normalization: aliases are removed from the suggested title.
producer_cases = {
    "SLV & DE PLUG - HIT (143Bpm Cmin).mp3": "HIT",
    "@prod.slv @deplugboy - MANSION (146Bpm Emin).mp3": "MANSION",
    "@prod_slv - TITANIUM 140BPM F#min.mp3": "TITANIUM",
    "de plugg - TEST 128 BPM A minor.mp3": "TEST",
    "@de_plug - TEST 128BPM Am.mp3": "TEST",
    "daddy kar - BEAT 155BPM Gmin.mp3": "BEAT",
    "@daddykar_official - BEAT 155BPM Gmin.mp3": "BEAT",
}
for filename, expected_name in producer_cases.items():
    meta = parse_beat_filename(filename)
    assert meta["name"] == expected_name, (filename, meta)

print("Producer alias/title cleanup tests: OK")
