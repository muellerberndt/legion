# R4dar 🎯

R4dar is an AI agent-driven bot that does the dirty work for web3 bug hunters. Its goal is to optimize the use of the researchers' time by automatically correlating , and acting on, ata from various sources. It keeps track of assets associated with ongoing bounty programs and contests, monitors on-chain and off-chain events related to those assets, and spawns agents that perform tasks on behalf of the user.

The r4dar framework is designed to be easily extensible in order to allow users to keep their bug hunting alpha private.

## Features

Built-in features include:

- LLM-powered Telegram chatbot interface
- Indexing assets from bounty platforms and contests (atm Immunefi only)
- Various search options for bounties & associated assets
- Automated diff when in-scope assets are updated on Immunefi or Github
- Automated monitoring of Github repos in scope
- On-chain monitoring via Quicknode integration

## Quick Start

```bash
# Install R4dar
pip install r4dar

# Set up configuration
cp config.example.yml config.yml
# Edit config.yml with your settings

# Start the service
r4dar start
```

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Customization Guide](docs/customization.md) - How to extend R4dar with custom handlers and analyzers
- [API Reference](docs/api.md) - API documentation for developers

## Example Usage

```python
# Example custom handler for monitoring specific contracts
from r4dar.handlers import Handler
from r4dar.triggers import BlockchainEvent

class CustomContractHandler(Handler):
    def get_triggers(self):
        return [BlockchainEvent]
        
    async def handle(self):
        # Your custom logic here
        pass
```

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on how to submit pull requests, report issues, and contribute to the project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


