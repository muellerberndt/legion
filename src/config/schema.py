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
                "etherscan": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                "basescan": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                "arbiscan": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                "polygonscan": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
                "bscscan": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
            },
        },
        "llm": {
            "type": "object",
            "properties": {
                "openai": {
                    "type": "object",
                    "properties": {"key": {"type": "string"}, "model": {"type": "string"}},
                    "required": ["key"],
                }
            },
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
        "telegram": {
            "type": "object",
            "properties": {"bot_token": {"type": "string"}, "chat_id": {"type": "string"}},
            "required": ["bot_token", "chat_id"],
        },
        "data_dir": {"type": "string"},
        "extensions_dir": {"type": "string"},
        "active_extensions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["database", "data_dir"],
}
