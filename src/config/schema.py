# Environment variable mappings for config values
ENV_MAPPINGS = {
    "data_dir": "LEGION_DATA_DIR",
    "extensions_dir": "LEGION_EXTENSIONS_DIR",
    "active_extensions": {"env": "LEGION_EXTENSIONS", "type": "list"},
    "database.host": "LEGION_DB_HOST",
    "database.port": "LEGION_DB_PORT",
    "database.name": "LEGION_DB_NAME",
    "database.user": "LEGION_DB_USER",
    "database.password": "LEGION_DB_PASSWORD",
    "block_explorers.etherscan.key": "LEGION_ETHERSCAN_KEY",
    "block_explorers.basescan.key": "LEGION_BASESCAN_KEY",
    "block_explorers.arbiscan.key": "LEGION_ARBISCAN_KEY",
    "block_explorers.polygonscan.key": "Legion_POLYGONSCAN_KEY",
    "block_explorers.bscscan.key": "LEGION_BSCSCAN_KEY",
    "llm.openai.key": "LEGION_OPENAI_KEY",
    "llm.openai.model": "LEGION_OPENAI_MODEL",
    "telegram.bot_token": "LEGION_BOT_TOKEN",
    "telegram.chat_id": "LEGION_CHAT_ID",
    "github.api_token": "LEGION_GITHUB_TOKEN",
    "github.poll_interval": "LEGION_GITHUB_POLL_INTERVAL",
    "webhook_server.enabled": {"env": "LEGION_WEBHOOK_SERVER_ENABLED", "type": "bool"},
    "webhook_server.port": {"env": "LEGION_WEBHOOK_PORT", "type": "int"},
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
                    "properties": {
                        "key": {"type": "string"},
                        "model": {"type": "string", "default": "gpt-4"},
                        "max_context_length": {"type": "integer", "default": 128000},
                        "context_reserve": {"type": "integer", "default": 8000},
                    },
                }
            },
            "default": {"openai": {}},
        },
        "github": {
            "type": "object",
            "properties": {"api_token": {"type": "string"}, "poll_interval": {"type": "integer", "default": 300}},
        },
        "webhook_server": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean", "default": True},
                "port": {"type": "integer", "default": 8080},
            },
            "default": {"enabled": True, "port": 8080},
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
        "file_search": {
            "type": "object",
            "properties": {
                "allowed_extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [".sol", ".cairo", ".rs", ".vy", ".fe", ".move", ".yul"],
                }
            },
            "default": {"allowed_extensions": [".sol", ".cairo", ".rs", ".vy", ".fe", ".move", ".yul"]},
        },
    },
    "required": ["database", "data_dir"],
}
