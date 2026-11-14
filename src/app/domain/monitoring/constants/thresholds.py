"""Every tunable constant of the pipeline, in one place (BACKEND_TZ §5.3).

ML may send refined numbers for the context rules; change them here only.
"""

# --- minute aggregation (§5.1) ---
SQI_VALID = 50  # a second counts for optical metrics only at sqi >= this
MIN_VALID_SECONDS = 20  # fewer valid seconds -> metric is null for the minute
HARD_MIN_VALID_S = 40  # hard thresholds need this many valid hr seconds (type 1)
DEFAULT_PRESS_HPA = 1013.25
MMHG_PER_HPA = 0.750062

# --- context (§5.3) ---
CTX_OFF, CTX_SLEEP, CTX_REST, CTX_ACTIVE = 0, 1, 2, 3
CTX_NAMES = {CTX_OFF: "off", CTX_SLEEP: "sleep", CTX_REST: "rest", CTX_ACTIVE: "active"}
OFF_WORN_FRAC = 0.5
OFF_SQI = 20
ACTIVE_ACT_MG = 60.0
ACTIVE_COOLDOWN_MIN = 5
SLEEP_ACT_MG = 8.0
SLEEP_STILL_MIN = 15
SLEEP_HR_MARGIN = 5.0
SLEEP_HR_DEFAULT_REST = 60.0

# --- personal norm (§6) ---
BASELINE_METRICS = ("hr", "spo2", "rr", "skin_t", "hrv")
LEVEL_METRICS = ("hr", "spo2", "rr", "skin_t")  # hrv has a norm but raises no level
LEARN_BIT = {"hr": 1, "spo2": 2, "rr": 4, "skin_t": 8, "hrv": 16}
BUFFER_DAYS = 14
BUFFER_MAX = 3360
CELL_READY_N = 120
CELL_READY_DAYS = 3
SIGMA_FLOOR = {"hr": 3.0, "spo2": 1.0, "rr": 1.5, "skin_t": 0.3, "hrv": 8.0}
BAND_SIGMAS = 2.0
LEARN_MAX_ABS_Z = 2.5
# typical norm (med, sigma) per (metric, ctx); None ctx = any context.
# Used with doubled sigma while the metric is still learning.
TYPICAL_NORM: dict[tuple[str, str | None], tuple[float, float]] = {
    ("hr", "rest"): (60.0, 10.0),
    ("hr", "sleep"): (52.0, 8.0),
    ("spo2", None): (97.0, 1.5),
    ("rr", None): (14.0, 3.0),
    ("skin_t", None): (33.5, 1.5),
    ("hrv", None): (40.0, 20.0),
}
LEARNED_DAYS = 7
LEARNED_READY_PCT = 75

# --- levels (§7) ---
USUAL, WATCH, ALERT, CRITICAL = 0, 1, 2, 3
LEVEL_NAMES = {USUAL: "usual", WATCH: "watch", ALERT: "alert", CRITICAL: "critical"}
Z_WATCH, Z_WATCH_MIN = 2.0, 5
Z_ALERT, Z_ALERT_MIN = 3.0, 3
HYSTERESIS_MIN = 10

# hard limits (§7.2). Values are compared as received, no rounding.
SPO2_CRITICAL_MAX = 91.0  # <= -> critical
SPO2_ALERT_BELOW = 94.0  # < -> alert (i.e. 92–93.x)
HR_CRITICAL_HIGH = 131.0
HR_ALERT_HIGH = 111.0
HR_LOW = 40.0  # <= ; critical at rest, alert in sleep
RR_CRITICAL_LOW = 8.0
RR_CRITICAL_HIGH = 25.0
RR_ALERT_HIGH = 21.0

# the limit quoted in texts and on charts, by (metric, direction)
HARD_LIMIT_QUOTE = {
    ("spo2", "down"): SPO2_CRITICAL_MAX, ("hr", "up"): HR_CRITICAL_HIGH,
    ("hr", "down"): HR_LOW, ("rr", "up"): RR_CRITICAL_HIGH, ("rr", "down"): RR_CRITICAL_LOW,
}

# environment (§7.3)
PPCO2_WINDOW_MIN = 60
PPCO2_MIN_VALUES = 30
PPCO2_WATCH, PPCO2_ALERT, PPCO2_CRITICAL = 3.0, 5.3, 10.0
PRESS_DROP_WINDOW_MIN = 10
PRESS_DROP_ALERT = 0.02
PRESS_MEDIAN_WINDOW_MIN = 24 * 60
PRESS_MEDIAN_MIN_VALUES = 30
PRESS_BELOW_MEDIAN_CRITICAL = 0.10

# --- pattern (§8) ---
PATTERN_WINDOW_MIN = 10
PATTERN_P_WATCH = 0.8
PATTERN_WATCH_MIN = 3
PATTERN_CLASSES = (
    "normal", "hypoxia", "tachycardia_rest", "bradycardia",
    "fever_like", "hypercapnia", "depressurization", "sensor_artifact",
)

# --- incident metrics (§7.5) ---
SLOPE_WINDOW_MIN = 10
# |slope per minute| below this -> "stable"
TREND_EPS = {"hr": 0.3, "spo2": 0.1, "rr": 0.1, "skin_t": 0.02, "hrv": 0.5,
             "ppco2": 0.02, "press": 0.1}

UNITS = {"hr": "bpm", "spo2": "%", "rr": "br/min", "skin_t": "°C", "hrv": "ms",
         "ppco2": "mmHg", "press": "hPa", "amb_t": "°C"}
# display rounding; also what the LLM sees, so its numbers can be checked
DECIMALS = {"hr": 0, "spo2": 1, "rr": 0, "skin_t": 1, "hrv": 0,
            "ppco2": 1, "press": 1, "amb_t": 1}


def rnd(m: str, v: float | None) -> float | int | None:
    if v is None:
        return None
    d = DECIMALS.get(m, 1)
    return int(round(v)) if d == 0 else round(v, d)
