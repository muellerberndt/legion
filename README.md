# Legion

![Tests](https://github.com/muellerberndt/Legion/actions/workflows/tests.yml/badge.svg)

Legion is an AI-driven framework that automates Web3 bug hunting workflows using an army of autonomous agents. Agents can be spawned on demand and react to on-chain and off-chain events. They can perform arbitrary tasks, such as assessing code revisions and upgrades, prioritizing targets based on EV, evaluating on-chain and off-chain events, searching code for potential bugs, or whatever else the security researcher desires. 

The Legion framework ships with basic functionality. By [extending Legion](docs/customization.md) with custom actions and event handlers, you can enhance the capabilities of your agents and implement your own "alpha" strategies.

The base framework contains the following features:

- Telegram chatbot interface
- Launch agents on demand or schedule them to run at specific times
- Auto-track data from contests and bounty programs (currently only Immunefi)
- Search bounty data, files and repos (including regex & vector search)
- Auto-review of PRs and commits in GitHub repos in scope
- Auto-review of proxy upgrades in scope (see [example extension](extensions/examples/proxy_upgrade_review.py))
- Simple semgrep scanning (see [example extension](extensions/examples/simple_semgrep.py))

## Running Legion

You need to set up a Telegram bot, a Postgres database and several API keys first ([Installation Guide](docs/installation.md)).

To start the server, run:

```bash
./legion.sh server start --log-level INFO
```

You can then talk to the bot via Telegram.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [User Guide](docs/user_guide.md) - How to use Legion
- [Customization Guide](docs/customization.md) - How to extend Legion
- [Development Guide](docs/development.md) - Development setup and guidelines

## Contributing

Contributions are welcome!

## License

This project is licensed under the Apache 2.0 License with additional commercial terms. 

It is free to use for security research and bug hunting activities, including those generating commercial rewards (e.g., bug bounty programs or audit contests). Any extensions you build on top of Legion belong to you and are not subject to the license.

However, wrapping Legion into a commercial product or service is prohibited without written permission from the author. See [LICENSE](LICENSE.txt) for details.
 
