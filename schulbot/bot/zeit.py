"""Die aktuelle Zeit in deiner Zeitzone.

Alle Teile des Bots fragen die Zeit hier ab. So lässt sie sich in den Tests
auf einen festen Zeitpunkt stellen.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import config

ZONE = ZoneInfo(config.ZEITZONE)


def jetzt() -> datetime:
    return datetime.now(ZONE)
