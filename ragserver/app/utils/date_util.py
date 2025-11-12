from datetime import UTC, datetime, timedelta


def get_current_time() -> datetime:
    return datetime.now(UTC)


def get_current_time_plus_days(days: int) -> datetime:
    return get_current_time() + timedelta(days=days)


def get_current_time_minus_days(days: int) -> datetime:
    return get_current_time() - timedelta(days=days)
