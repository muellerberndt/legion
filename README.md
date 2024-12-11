# R4dar

![Tests](https://github.com/muellerberndt/r4dar/actions/workflows/tests.yml/badge.svg)

R4dar is an AI-driven framework that automates web3 bug hunting workflows. The idea is to spawn an army of autonomous agents that perform tasks on behalf of the user, such as monitoring the scopes of active bounty programs and contests, assessing the relevance of code changes and upgrades, and prioritizing targets based on EV. Bug detection tools can also be integrated easily. The goal is to optimize the use of the researchers' time and hopefully increase the overall earnings.

The r4dar framework is designed to be [extensible](docs/customization.md) in order to allow users to keep their bug hunting alpha private.

Built-in features:

- Telegram chatbot interface
- Search files and repos associated with bounties
- Auto-sync data from Immunefi
- React to scope changes in bounty programs
- Auto-review of PRs and commits from Github repos associated with bounties

Some possible extensions:

- Auto-analyze upgraded proxy implementations in bounty scope (see [example](extensions/examples/))
- Prioritize targets based on daily events and EV
- Scan the codebases of all bounties for patterns distilled from bug reports
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
 
