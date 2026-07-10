"""Constants for HASS Console."""

DOMAIN = "hass_console"

# Config flow keys
CONF_CONSOLE_YAML = "console_yaml"
CONF_ALARM_CSV = "alarm_csv"
CONF_LOG_CSV = "log_csv"
CONF_RETENTION_DAYS = "retention_days"
CONF_MAX_ROWS = "max_rows"

# Defaults — all CSVs live in /config/www/hass-console/
DEFAULT_CONSOLE_YAML = "/config/console.yaml"
DEFAULT_ALARM_CSV = "/config/www/hass-console/alarms.csv"
DEFAULT_LOG_CSV = "/config/www/hass-console/logs.csv"

# Retention defaults — disabled by default (opt-in), so no data is ever
# deleted unless the user sets a value. 0 means "no limit".
DEFAULT_RETENTION_DAYS = 0
DEFAULT_MAX_ROWS = 0

# CSV column schemas
ALARM_COLUMNS = [
    "id", "timestamp", "category", "entity", "class",
    "value", "duration", "note", "trigger", "ack", "ack_note",
]
LOG_COLUMNS = ["timestamp", "category", "entity", "value", "note"]

# Repairs issue ID for invalid console.yaml points
ISSUE_INVALID_CONFIG = "invalid_config"

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
CONF_TARGET_CSV = "target_csv"
