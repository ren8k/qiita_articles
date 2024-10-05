from datetime import datetime, timezone
from typing import Final

PER_PAGE: Final[int] = 100
USER_ID: Final[str] = "<user name>"
API_TOKEN: Final[str] = "<api token>"
START_DATE: Final[datetime] = datetime(2024, 4, 1, tzinfo=timezone.utc)
END_DATE: Final[datetime] = datetime(2025, 3, 31, tzinfo=timezone.utc)
