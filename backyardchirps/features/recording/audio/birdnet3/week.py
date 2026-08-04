import calendar
import math
from datetime import datetime


def week_48_for(recorded_at: datetime) -> int:
    """
    BirdNET's 48-week calendar index (1 to 48) for a date, the input GeoModel 3
    expects for the week dimension.
    """
    day_of_year = recorded_at.timetuple().tm_yday
    days_in_year = 366 if calendar.isleap(recorded_at.year) else 365
    return math.ceil((day_of_year / days_in_year) * 48)
