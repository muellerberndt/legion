# Legion

![Tests](https://github.com/muellerberndt/Legion/actions/workflows/tests.yml/badge.svg)

Legion is an AI-driven framework that automates Web3 bug hunting workflows. It tracks ongoing bug bounties and contests and launches autonomous agents that can perform arbitrary tasks, such as assessing code revisions and upgrades, evaluating on-chain and off-chain events, searching code for potential bugs, or whatever else the security researcher desires. 

Legion is meant to be used as a base framework for security researchers. By [extending Legion](docs/customization.md), you can enhance the capabilities of your agents and implement your own "alpha" strategies that you might not be willing to share. Some ideas:

- Intelligently prioritize targets using code complexity analysis & EV estimation (payouts, estimated competition, etc.)
- Integrate more sophisticated embeddings generation and reasoning models to find bugs
- Add gap analysis in tests suites & automated Foundry test generation / fuzzing to find edge cases
- (... the list goes on)

The base framework contains the following features:

- Auto-sync data and code from bug bounty platforms (e.g., Immunefi)
- Auto-tracking of EVM proxy implementations across multiple chains
- Search bounty code using regex & vector search
- Auto-review of PRs and commits in GitHub repos associated with bounties
- Launch agents on demand or schedule them to run at specific intervals
- Simple semgrep scanning (see [example extension](extensions/examples/simple_semgrep.py))

## Running Legion

First, set up your local environment and API keys by following the [Installation Guide](docs/installation.md).

To start the server, run:

```bash
python -m src.cli.main server start --log-level INFO
```

The server will start and automatically sync bounty data based on your configuration. You can monitor the logs for progress and results. All notifications and events are stored in a local SQLite database.

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [User Guide](docs/user_guide.md) - How to use Legion
- [Customization Guide](docs/customization.md) - How to extend Legion
- [Development Guide](docs/development.md) - Development setup and guidelines

## Contributing

Contributions are welcome! To contribute to the base framework, you need to sign the [Contributor License Agreement](https://cla-assistant.io/muellerberndt/legion) and follow the [Development Guide](docs/development.md).

## License

This project is licensed under the Apache 2.0 License with additional commercial terms. 

It is free to use for security research and bug hunting activities, including those generating commercial rewards (e.g., bug bounty programs or audit contests). Any extensions you build on top of Legion belong to you and are not subject to the license.

However, wrapping Legion into a commercial product or service is prohibited without written permission from the author. See [LICENSE](LICENSE.txt) for details.
 
