from datetime import datetime, timedelta, timezone

def get_current_time() -> datetime:
    return datetime.now(timezone.utc)

def get_current_time_plus_days(days: int) -> datetime:
    return get_current_time() + timedelta(days=days)

def get_current_time_minus_days(days: int) -> datetime:
    return get_current_time() - timedelta(days=days)