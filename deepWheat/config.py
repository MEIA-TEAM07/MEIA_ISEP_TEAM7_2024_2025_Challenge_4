# config.py

BATTERY_LOW_THRESHOLD = 45
BATTERY_CRITICAL_THRESHOLD = 25
BATTERY_RECHARGE_STEP = 20
RECHARGE_INTERVAL = 1
RECHARGE_LOG = True

GROWTH_SEASON_START = (3, 15)  # March 15
GROWTH_SEASON_END = (6, 15)    # June 15
DEFAULT_CROP_TYPE = "spring"

WIND_MIN = 5
WIND_MAX = 15
FLIGHT_TIME = 2
APPLICATION_TIME = 2

# Grid size for all fields (can be made per-field if needed)
FIELD_ROWS = 2
FIELD_COLS = 5

# Field and disease mapping
FIELDS = [
    {"field_id": "field_1", "rows": FIELD_ROWS, "cols": FIELD_COLS},
    {"field_id": "field_2", "rows": FIELD_ROWS, "cols": FIELD_COLS}
]

DISEASED_PLANTS = {
    "field_1": [
        (0, 1, "white_stripe"),
        (1, 3, "brown_rust")
    ],
    "field_2": [
        (1, 2, "yellow_rust"),
        (0, 4, "septoria"),
    ],
}

# Map agent JIDs to fields
FIELD_AGENT_ASSIGNMENT = {
    "field_1": "field1@localhost",
    "field_2": "field2@localhost",
}
FIELD_AGENTS = [
    {"agent_jid": "field1@localhost", "field_id": "field_1"},
    {"agent_jid": "field2@localhost", "field_id": "field_2"}
]
# Weather settings
WEATHER_API_KEY = "bcbf7b4cabfaa6fa5678dc5c5ada8a96"
WEATHER_LAT = 41.1496
WEATHER_LON = -8.6109
WEATHER_UPDATE_INTERVAL = 600