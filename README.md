# Legion

![Tests](https://github.com/muellerberndt/Legion/actions/workflows/tests.yml/badge.svg)

Legion is an AI-driven framework that automates Web3 bug hunting workflows. It tracks ongoing bug bounties and contests and launches autonomous agents that can perform arbitrary tasks, such as assessing code revisions and upgrades, evaluating on-chain and off-chain events, searching code for potential bugs, or whatever else the security researcher desires. 

The Legion framework ships with basic functionality. The idea is to share a base framework that can be used by all security researchers while keeping the more advanced features private. By [extending Legion](docs/customization.md), you can enhance the capabilities of your agents and implement your own "alpha" strategies that you might not be willing to share. Some ideas:

- Intelligently prioritize targets using code complexity analysis & EV estimation (payouts, estimated competition, etc.)
- Integrate sophisticated vector search and reasoning capabilities to find bugs
- Add gap analysis in tests suites & automated Foundry test generation to find edge cases
- (... the list goes on)

The base framework contains the following features:

- Telegram chatbot interface
- Auto-sync data and code from Immunefi bounties
- Search bounty data, files and repos using regex & vector search
- Auto-review of PRs and commits in GitHub repos in scope
- Auto-review of proxy implementation upgrades in scope (see [example extension](extensions/examples/proxy_upgrade_review.py))
- Launch agents on demand or schedule them to run at specific intervals
- Simple semgrep scanning (see [example extension](extensions/examples/simple_semgrep.py))

## Running Legion

You need to set up a Telegram bot, a Postgres database and several API keys first ([Installation Guide](docs/installation.md)).

To start the server, run:

```bash
./legion.sh server start --log-level INFO
```

Sync bounty data from Immunefi with `/immunefi silent`. Then chat away with the bot:

```
Bernhard, [22 Dec BE 2567 at 21:06:27]:
Search all assets for the string 'using SignatureUtil for bytes'. If you find any asset containing this string please run semgrep on it and briefly summarize the asset code and semgrep results, as well as the associated project.

legion, [23 Dec BE 2567 at 06:57:18]:
🤔 First, I need to search for assets containing the string 'using SignatureUtil for bytes'. If found, I'll proceed to run semgrep on those assets.
🛠️ Executing: /file_search 'using SignatureUtil for bytes'
(... working a bit ...)

The asset associated with the string 'using SignatureUtil for bytes' is part of the 'deBridge' project. The project is described as a cross-chain interoperability and liquidity transfer protocol that allows decentralized transfer of data and assets between various blockchains. The semgrep scan on the asset with ID 906 found no issues. The code for the asset includes a library for handling signatures and a contract for asset transfers, among other functionalities.

Bernhard Mueller, [23 Dec BE 2567 at 07:01:41]:
What's the explorer URL for that asset?

legion, [23 Dec BE 2567 at 07:01:48]:
🤔 I need to retrieve the explorer URL for the asset with ID 906.
🛠️ Executing: /db_query '{"from": "assets", "select": ["identifier"], "where": [{"field": "id", "op": "=", "value": 906}]}'

The explorer URL for the asset is: https://etherscan.io/address/0x24455aa55ded7728783c9474be8ea2f5c935f8eb
```

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
 
