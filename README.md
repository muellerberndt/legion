# R4dar

![Tests](https://github.com/muellerberndt/r4dar/actions/workflows/tests.yml/badge.svg)

R4dar is an AI agent-driven bot that does the dirty work for web3 bug hunters. Its goal is to optimize the use of the researchers' time by automatically correlating data from various sources. It keeps track of assets associated with ongoing bounty programs and contests, monitors on-chain and off-chain events related to those assets, and spawns agents that automate tasks on behalf of the user.

The r4dar framework is designed to be easily extensible in order to allow users to keep their bug hunting alpha private.

## Features

Built-in features:

- LLM-powered Telegram chatbot interface
- Search active bounties, contests and associated files
- Automated monitoring of Github repos associated with bounties
- Monitoring of bounty scopes on Immunefi

Some possible extensions:

- Auto-analysis when proxy implementation in scope is upgraded (see [example](examples/proxy_contract_handler.py))
- Automated diff and analysis when an asset is updated
- Prioritization targets based on daily events and EV
- Scan the codebases of all bounties and assets for bugs
- Endless possibilities...

## Running R4dar

You need to set up a Telegram bot, a Postgres database and several API keys first ([Installation Guide](docs/installation.md)).

To start the server, run:

```bash
./r4dar.sh server start --log-level INFO
```

You can then talk to the bot via Telegram. To get help, just type `/help`.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Development Guide](docs/development.md) - Development setup and guidelines
- [Customization Guide](docs/customization.md) - How to extend r4dar

## Contributing

Contributions are welcome!

## License

This project is licensed under the Apache 2.0 License with additional commercial terms. 

It is free to use for security research and bug hunting activities, including those generating commercial rewards (e.g., bug bounty programs or audit contests). Any extensions you build on top of r4dar belong to you and are not subject to the license.

However, wrapping r4dar into a commercial product or service is prohibited without written permission from the author. See [LICENSE](LICENSE.txt) for details.
