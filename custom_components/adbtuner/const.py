"""Constants for the ADBTuner integration."""

from datetime import timedelta

DOMAIN = "adbtuner"

CONF_GUIDE_URL = "guide_url"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=15)
GUIDE_SCAN_INTERVAL = timedelta(minutes=30)
CHANNELS_REFRESH_INTERVAL = timedelta(minutes=10)

TUNER_STATES = ["idle", "tuning", "tuned", "maintenance"]
