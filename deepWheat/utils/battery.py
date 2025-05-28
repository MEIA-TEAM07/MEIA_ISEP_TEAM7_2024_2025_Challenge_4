def compute_battery_usage(base_cost: float, wind_speed: float) -> float:
    """
    Compute battery usage based on base cost and wind speed.
    :param base_cost: base % cost of operation
    :param wind_speed: wind speed in km/h
    :return: battery % consumed
    """
    wind_penalty = wind_speed * 0.2  # tune this factor if needed
    return base_cost + wind_penalty

def drain_battery(current_level: float, usage: float) -> float:
    """
    Drain battery while keeping value within bounds.
    """
    return max(0, current_level - usage)