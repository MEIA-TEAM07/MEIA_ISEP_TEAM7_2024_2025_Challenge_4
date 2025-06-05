# config.py

# Battery thresholds
BATTERY_LOW_THRESHOLD = 45     # below this, drone should return to base
BATTERY_CRITICAL_THRESHOLD = 25  # optional: e.g., cannot respond to CFP if below

# Recharging behavior
BATTERY_RECHARGE_STEP = 20     # battery recharge step per second
RECHARGE_INTERVAL = 1          # in seconds
RECHARGE_LOG = True            # log during recharge or not

# Growth season dates
GROWTH_SEASON_START = (3, 15)  # March 15
GROWTH_SEASON_END = (6, 15)    # June 15

# Default payloads
DEFAULT_CROP_TYPE = "spring"   # used for seasonal logic

# Wind simulation
WIND_MIN = 5
WIND_MAX = 15

# Field scan & apply durations
FLIGHT_TIME = 2
APPLICATION_TIME = 2