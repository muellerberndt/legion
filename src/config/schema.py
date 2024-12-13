# Environment variable mappings for config values
ENV_MAPPINGS = {
    "data_dir": "R4DAR_DATA_DIR",
    "extensions_dir": "R4DAR_EXTENSIONS_DIR",
    "active_extensions": {"env": "R4DAR_EXTENSIONS", "type": "list"},
    "database.host": "R4DAR_DB_HOST",
    "database.port": "R4DAR_DB_PORT",
    "database.name": "R4DAR_DB_NAME",
    "database.user": "R4DAR_DB_USER",
    "database.password": "R4DAR_DB_PASSWORD",
    "block_explorers.etherscan.key": "R4DAR_ETHERSCAN_KEY",
    "block_explorers.basescan.key": "R4DAR_BASESCAN_KEY",
    "block_explorers.arbiscan.key": "R4DAR_ARBISCAN_KEY",
    "block_explorers.polygonscan.key": "R4DAR_POLYGONSCAN_KEY",
    "block_explorers.bscscan.key": "R4DAR_BSCSCAN_KEY",
    "llm.openai.key": "R4DAR_OPENAI_KEY",
    "llm.openai.model": "R4DAR_OPENAI_MODEL",
    "telegram.bot_token": "R4DAR_BOT_TOKEN",
    "telegram.chat_id": "R4DAR_CHAT_ID",
    "github.api_token": "R4DAR_GITHUB_TOKEN",
    "github.poll_interval": "R4DAR_GITHUB_POLL_INTERVAL",
    "watchers.enabled": {"env": "R4DAR_WATCHERS_ENABLED", "type": "bool"},
    "watchers.webhook_port": {"env": "R4DAR_WEBHOOK_PORT", "type": "int"},
    "watchers.active_watchers": {"env": "R4DAR_WATCHERS", "type": "list"},
}

CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "database": {
            "type": "object",
            "properties": {
                "host": {"type": "string"},
                "port": {"type": "integer"},
                "name": {"type": "string"},
                "user": {"type": "string"},
                "password": {"type": "string"},
            },
            "required": ["host", "port", "name", "user", "password"],
        },
        "block_explorers": {
            "type": "object",
            "properties": {
                "etherscan": {
                    "type": "object",
                    "properties": {"key": {"type": ["string", "null"]}},
                    "additionalProperties": False,
                },
                "basescan": {
                    "type": "object",
                    "properties": {"key": {"type": ["string", "null"]}},
                    "additionalProperties": False,
                },
                "arbiscan": {
                    "type": "object",
                    "properties": {"key": {"type": ["string", "null"]}},
                    "additionalProperties": False,
                },
                "polygonscan": {
                    "type": "object",
                    "properties": {"key": {"type": ["string", "null"]}},
                    "additionalProperties": False,
                },
                "bscscan": {
                    "type": "object",
                    "properties": {"key": {"type": ["string", "null"]}},
                    "additionalProperties": False,
                },
            },
            "additionalProperties": False,
            "default": {},
        },
        "llm": {
            "type": "object",
            "properties": {
                "openai": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}, "model": {"type": "string", "default": "gpt-4"}},
                }
            },
            "default": {"openai": {}},
        },
        "github": {
            "type": "object",
            "properties": {"api_token": {"type": "string"}, "poll_interval": {"type": "integer", "default": 300}},
        },
        "watchers": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": False},
                "webhook_port": {"type": "integer", "default": 8080},
                "active_watchers": {"type": "array", "items": {"type": "string"}, "default": []},
            },
        },
        "telegram": {"type": "object", "properties": {"bot_token": {"type": "string"}, "chat_id": {"type": "string"}}},
        "data_dir": {"type": "string", "default": "./data"},
        "extensions_dir": {"type": "string", "default": "./extensions"},
        "active_extensions": {"type": "array", "items": {"type": "string"}, "default": []},
        "scheduled_actions": {
            "type": "object",
            "patternProperties": {
                "^[a-zA-Z0-9_]+$": {  # Allow alphanumeric names with underscores
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "interval_minutes": {"type": "integer", "minimum": 1},
                        "enabled": {"type": "boolean", "default": True},
                    },
                    "required": ["command", "interval_minutes"],
                }
            },
            "default": {},
        },
    },
    "required": ["database", "data_dir"],
}
