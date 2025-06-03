from datetime import datetime, date

def is_growth_season(current_date: date, crop_type: str = "spring") -> bool:
    """
    Determines if the given date is within the growth season for spring wheat.
    Growth season assumed: March 15 – June 15 (typical for spring wheat in temperate climates).
    """
    year = current_date.year
    start = date(year, 3, 15)
    end = date(year, 6, 15)
    return start <= current_date <= end

def get_default_payload(current_datetime: datetime, crop_type: str = "spring") -> str:
    """
    Returns 'fertilizer' during growth season, otherwise 'pesticide'.
    """
    return "fertilizer" if is_growth_season(current_datetime.date(), crop_type) else "pesticide"