def evaluate_proposal(battery_level, wind_speed):
    """Higher score = better drone"""
    battery_score = battery_level / 100.0  # normalize
    wind_penalty = wind_speed / 30.0       # assume max wind 30km/h
    return battery_score - wind_penalty