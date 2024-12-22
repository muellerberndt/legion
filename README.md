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
List some bounties with assets that were added or updated recently

legion, [22 Dec BE 2567 at 13:52:59]:
🤔 To fulfill the user's request, I need to query the database for recent bounties and their associated assets. I will join the projects and assets tables to get this information.

🛠️ Executing: /db_query '{"from": "projects", "join": {"table": "assets", "on": {"id": "project_id"}}, "where": [{"field": "project_type", "op": "=", "value": "bounty"}], "order_by": [{"field": "assets.updated_at", "direction": "desc"}], "limit": 5}'

🤔 The user requested a list of recent bounties with assets that were added or updated recently. The previous query returned duplicate results, so I need to summarize and present the unique projects.

Here are some recent bounties with updated assets:

1. **eBTC**
   - Description: eBTC is a collateralized crypto asset soft pegged to the price of Bitcoin and built on the Ethereum network. It is based on the Liquity protocol and backed exclusively by Staked Ether (stETH). The protocol is designed with an immutable core with minimized counterparty reliance and governance.
   - Source: Immunefi
   - Keywords: Smart Contract, Lending, Defi, Solidity, Managed Triage: Time Saver, Subscription Plan: Essential, ETH, Yield Aggregator
   - Max Bounty: $100,000
   - Updated: 2024-12-21

(...)

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
 
