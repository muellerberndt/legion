# Legion

![Tests](https://github.com/muellerberndt/Legion/actions/workflows/tests.yml/badge.svg)

Legion is an AI-driven framework that automates web3 bug hunting workflows using an army of autonomous agents. Agents can be spawned on demand and react to on-chain and off-chain events. They can perform arbitrary tasks, such as assessing the relevance of code revisions and upgrades, prioritizing targets based on EV, evaluating recent events, searching bounty and contest code for potential bugs, running analysis tools, or whatever else the security researcher desires. 

The Legion framework is designed to be [extensible](docs/customization.md) so users can keep their bug hunting alpha private. The base framework contains the following features:

- Telegram chatbot interface
- Auto-sync data from contests and bounty programs (atm only Immunefi)
- Search bounty data, files and repos (including vector search)
- Auto-review of PRs and commits in bounty repos
- Notifications on scope changes, asset revision diffs
- Example extensions for auto-reviewing proxy upgrades & semgrep scans

## Running Legion

You need to set up a Telegram bot, a Postgres database and several API keys first ([Installation Guide](docs/installation.md)).

To start the server, run:

```bash
./legion.sh server start --log-level INFO
```

You can then talk to the bot via Telegram.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [Development Guide](docs/development.md) - Development setup and guidelines
- [Customization Guide](docs/customization.md) - How to extend Legion

## Contributing

Contributions are welcome!

## License

This project is licensed under the Apache 2.0 License with additional commercial terms. 

It is free to use for security research and bug hunting activities, including those generating commercial rewards (e.g., bug bounty programs or audit contests). Any extensions you build on top of Legion belong to you and are not subject to the license.

However, wrapping Legion into a commercial product or service is prohibited without written permission from the author. See [LICENSE](LICENSE.txt) for details.
 
