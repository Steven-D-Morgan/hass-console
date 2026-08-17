"""Constants for HASS Console."""

DOMAIN = "hass_console"

CONF_CONSOLE_YAML = "console_yaml"
CONF_ALARM_CSV = "alarm_csv"
CONF_LOG_CSV = "log_csv"
CONF_RETENTION_DAYS = "retention_days"
CONF_MAX_ROWS = "max_rows"

DEFAULT_CONSOLE_YAML = "/config/console.yaml"
DEFAULT_ALARM_CSV = "/config/www/hass-console/alarms.csv"
DEFAULT_LOG_CSV = "/config/www/hass-console/logs.csv"

DEFAULT_RETENTION_DAYS = 0
DEFAULT_MAX_ROWS = 0

ALARM_COLUMNS = [
    "id", "timestamp", "category", "entity", "class",
    "value", "duration", "note", "trigger", "ack", "ack_note",
]
LOG_COLUMNS = ["timestamp", "category", "entity", "value", "note"]

ISSUE_INVALID_CONFIG = "invalid_config"

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

TYPE_LOG = "LOG"
TYPE_ALARM = "ALARM"

CONF_TYPE = "type"
CONF_CRON = "cron"
CONF_ENTITY = "entity"
CONF_NOTE = "note"
CONF_CLASS = "class"
CONF_TRIGGER = "trigger"
CONF_CATEGORY = "category"
CONF_TARGET_CSV = "target_csv"
