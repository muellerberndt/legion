# Legion

![Tests](https://github.com/muellerberndt/Legion/actions/workflows/tests.yml/badge.svg)

Legion is an AI-driven framework that automates Web3 bug hunting workflows. It tracks ongoing bug bounties and contests and launches autonomous agents that can perform arbitrary tasks, such as assessing code revisions and upgrades, evaluating on-chain and off-chain events, searching code for potential bugs, or whatever else the security researcher desires. 

The Legion framework ships with basic functionality. By [extending Legion](docs/customization.md), you can enhance the capabilities of your agents and implement your own "alpha" strategies that you might not be willing to share. Some ideas:

- Intelligently prioritize targets using code complexity analysis & EV estimation (payouts, estimated competition, etc.)
- Distill bug patterns from newly released reports to search for similar bugs in your scope
- Gap analysis in tests suites & automated Foundry test generation to find missing edge cases
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

You can then talk to the bot via Telegram.

```
What assets were added most recently to bounty scopes? List the assets together with the project names.

r4dar, [22 Dec BE 2567 at 07:10:25]:
🤔 Thinking: To find the most recently added assets to bounty scopes, I need to query the database for assets ordered by their creation date and join them with the projects table to get the project names.
🛠️ Running: db_query '{"from": "assets", "join": {"table": "projects", "on": {"project_id": "id"}}, "order_by": [{"field": "assets.created_at", "direction": "desc"}], "select": ["assets.identifier", "projects.name"], "limit": 10}'


Found 10 results

identifier,name
https://arbiscan.io/address/0x1619DE6B6B20eD217a58d00f37B9d47C7663feca,Celer
https://etherscan.io/address/0x5427FEFA711Eff984124bFBB1AB6fbf5E3DA1820,Celer
https://etherscan.io/address/0x5803457E3074E727FA7F9aED60454bf2F127853b,Celer
https://etherscan.io/address/0xea129aE043C4cB73DcB241AAA074F9E667641BA0,Celer
https://etherscan.io/address/0x61f85fF2a2f4289Be4bb9B72Fc7010B3142B5f41,Celer
https://etherscan.io/address/0xb01fd7Bc0B3c433e313bf92daC09FF3942212b42,Celer
https://etherscan.io/address/0xCb4A7569a61300C50Cf80A2be16329AD9F5F8F9e,Celer
https://etherscan.io/address/0x8a4B4C2aCAdeAa7206Df96F00052e41d74a015CE,Celer
https://arbiscan.io/address/0xfb47177dc75f3910b8bc6525b4835cca67a12c48,Voltz
https://etherscan.io/address/0xA6BA323693f9e9B591F79fbDb947c7330ca2d7ab,Voltz
```

## Documentation

- [Installation Guide](docs/installation.md) - Detailed setup instructions
- [User Guide](docs/userguide.md) - How to use Legion
- [Customization Guide](docs/customization.md) - How to extend Legion
- [Development Guide](docs/development.md) - Development setup and guidelines

## Contributing

Contributions are welcome!

## License

This project is licensed under the Apache 2.0 License with additional commercial terms. 

It is free to use for security research and bug hunting activities, including those generating commercial rewards (e.g., bug bounty programs or audit contests). Any extensions you build on top of Legion belong to you and are not subject to the license.

However, wrapping Legion into a commercial product or service is prohibited without written permission from the author. See [LICENSE](LICENSE.txt) for details.
 
