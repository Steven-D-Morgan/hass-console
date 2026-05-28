"""Constants for HASS Console."""

DOMAIN = "hass_console"

# Config flow keys
CONF_CONSOLE_YAML = "console_yaml"
CONF_ALARM_CSV = "alarm_csv"
CONF_LOG_CSV = "log_csv"

# Defaults
DEFAULT_CONSOLE_YAML = "/config/console.yaml"
DEFAULT_ALARM_CSV = "/config/www/hass-console-alarms.csv"
DEFAULT_LOG_CSV = "/config/www/hass-console-logs.csv"

# CSV column schemas
ALARM_COLUMNS = [
    "id", "timestamp", "category", "entity", "class",
    "value", "duration", "note", "trigger", "ack",
]
LOG_COLUMNS = ["timestamp", "category", "entity", "value", "note"]

# Timestamp format
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

# Point types
TYPE_LOG = "LOG"
TYPE_ALARM = "ALARM"

# YAML config keys
CONF_TYPE = "type"
CONF_CRON = "cron"
CONF_ENTITY = "entity"
CONF_NOTE = "note"
CONF_CLASS = "class"
CONF_TRIGGER = "trigger"
CONF_CATEGORY = "category"
