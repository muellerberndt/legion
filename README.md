# R4dar 🎯

R4dar is an AI agent-driven bot that does the dirty work for web3 bug hunters. Its goal is to optimize the use of the researchers' time by automatically correlating , and acting on, ata from various sources. It keeps track of assets associated with ongoing bounty programs and contests, monitors on-chain and off-chain events related to those assets, and spawns agents that perform tasks on behalf of the user.

The r4dar framework is designed to be easily extensible in order to allow users to keep their bug hunting alpha private.

## Features

Built-in features:

- LLM-powered Telegram chatbot interface
- Indexing assets from bounty platforms and contests (atm Immunefi only)
- Various search options for bounties & associated assets
- Automated diff when in-scope assets are updated on Immunefi or Github
- Automated monitoring of Github repos in scope
- On-chain monitoring via Quicknode integration

Extensions you can build:

- Notify the user when a smart contract in scope is upgraded (see [example](examples/proxy_contract_handler.py))
- Extract new semgrep patterns whenever a new audit report is published
- Pre-assess the codebase of new bounties and contests
- Daily data analysis to prioritize bounties, contests and assets
- ?

## Running R4dar

You need to set up a Telegram bot, a Postgres database and several API keys first ([Installation Guide](docs/installation.md)).

To start the server, run:

```bash
./r4dar.sh server start --log-level INFO
```

You can then talk to the bot via Telegram. To get help, just type `/help`.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Customization Guide](docs/customization.md) - How to extend r4dar

## Contributing

Contributions are welcome!

## License

This project is licensed under the Apache 2.0 License with additional commercial terms. 

It is free to use for security research and bug hunting activities, including those generating commercial rewards (e.g., bug bounty programs or audit contests). Any extensions you build on top of r4dar belong to you and are not subject to the license.

However, wrapping r4dar into a commercial product or service is prohibited without written permission from the author. See [LICENSE](LICENSE.txt) for details.
