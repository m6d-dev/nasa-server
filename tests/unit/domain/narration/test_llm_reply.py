from src.app.domain.narration.validation.llm_reply import parse_reply

SUMMARY = {"pattern": "hypoxia", "severity": 2, "since_min": 7,
           "metrics": [{"m": "spo2", "value": 93.0, "usual": [95.0, 99.0], "trend": "falling", "limit": 91.0},
                       {"m": "hr", "value": 80, "usual": [56, 68], "trend": "rising"}]}

GOOD = """WHAT: Blood oxygen has been below your usual range for 7 minutes (93.0 %, usual 95.0–99.0).
WHY: Oxygen is falling while heart rate rises (80 bpm, usual 56–68); SpO2 and CO2 look like low oxygen.
ACTION: Check the sensor fit. If it falls to 91 % or below, notify the crew medical officer."""


def test_accepts_three_lines_with_known_numbers():
    t = parse_reply(GOOD, SUMMARY)
    assert t is not None and len(t.action) == 2


def test_rejects_invented_number():
    assert parse_reply(GOOD.replace("80 bpm", "85 bpm"), SUMMARY) is None


def test_rejects_wrong_shape():
    assert parse_reply("WHAT: x\nWHY: y", SUMMARY) is None
    assert parse_reply(GOOD.replace("WHY:", "BECAUSE:"), SUMMARY) is None
