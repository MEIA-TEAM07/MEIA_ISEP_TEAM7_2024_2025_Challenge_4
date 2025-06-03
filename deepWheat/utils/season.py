from datetime import datetime

def is_growth_season(date: datetime, crop_type: str = "spring") -> bool:
    """
    Returns True if the given date falls within the growth season 
    for the specified crop type.
    """
    if crop_type == "spring":
        start = datetime(date.year, 3, 15)
        end = datetime(date.year, 6, 15)
        return start <= date <= end
    elif crop_type == "winter":
        start = datetime(date.year, 9, 1)
        end = datetime(date.year, 11, 30)
        return start <= date <= end
    return False

def get_default_payload(date: datetime, crop_type: str = "spring") -> str:
    """
    Returns 'fertilizer' during growth season, otherwise 'pesticide'.
    """
    return "fertilizer" if is_growth_season(date, crop_type) else "pesticide"