# Legion

![Tests](https://github.com/muellerberndt/Legion/actions/workflows/tests.yml/badge.svg)
<a href="https://cla-assistant.io/muellerberndt/legion"><img src="https://cla-assistant.io/readme/badge/muellerberndt/legion" alt="CLA assistant" /></a>

Legion is an AI-driven framework that automates Web3 bug hunting workflows. It tracks ongoing bug bounties and contests and launches autonomous agents that can perform arbitrary tasks, such as assessing code revisions and upgrades, evaluating on-chain and off-chain events, searching code for potential bugs, or whatever else the security researcher desires. 

Legion is meant to be used as a base framework for security researchers. By [extending Legion](docs/customization.md), you can enhance the capabilities of your agents and implement your own "alpha" strategies that you might not be willing to share. Some ideas:

- Intelligently prioritize targets using code complexity analysis & EV estimation (payouts, estimated competition, etc.)
- Integrate more sophisticated embeddings generation and reasoning models to find bugs
- Add gap analysis in tests suites & automated Foundry test generation / fuzzing to find edge cases
- (... the list goes on)

The base framework contains the following features:

- Telegram chatbot interface
- Auto-sync data and code from Immunefi bounties
- Auto-tracking of EVM proxy implementations across multiple chains
- Search bounty code using regex & vector search
- Auto-review of PRs and commits in GitHub repos associated with bounties
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
Bernhard Mueller, [25 Dec BE 2567 at 07:55:17]:
Search all assets for the string 'using SignatureUtil for bytes'. If you find any asset containing this string please run semgrep on it and briefly summarize the asset code and semgrep results, as well as the associated project.

legion, [25 Dec BE 2567 at 07:55:20]:
🤔 To find assets containing the string 'using SignatureUtil for bytes', I will perform a file search using the /file_search command. If any assets are found, I will proceed to run semgrep on them and summarize the results.
🛠️ Executing: /file_search 'using SignatureUtil for bytes'

(...)

The asset with ID 4987 is a deployed contract on Etherscan with the identifier https://etherscan.io/address/0x9C07A72177c5A05410cA338823e790876E79D73B. It is part of the DeGate project, which is an audit competition hosted on Immunefi. The target of the bounty is approximately 500 lines of new code designed to allow contract upgrades. The semgrep scan on this asset found no issues.

Bernhard Mueller, [25 Dec BE 2567 at 07:59:26]:
So is it a proxy? If so, what's the implementation? Can you run semgrep on that as well?

legion, [25 Dec BE 2567 at 07:59:29]:
🤔 To determine if the asset is a proxy and find its implementation, I need to query the database for the asset's proxy status and implementation details.
🛠️ Executing: /db_query '{"from": "assets", "select": ["is_proxy", "implementation_id"], "where": [{"field": "id", "op": "=", "value": 4987}]}'

(...)

The asset with ID 4987 is not a proxy contract, so there is no implementation to run semgrep on.
```

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
 
