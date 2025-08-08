# Installation Guide

This guide provides detailed instructions for setting up Legion on your system.

## Prerequisites

- Python 3.9 or higher

## Legion Installation

First, clone the repository:

```bash
git clone git@github.com:muellerberndt/legion.git
cd legion
```

### Local Installation

1. Create a Python virtual environment:

```bash
pyenv virtualenv 3.12 legion
pyenv activate legion
```

2. Install the requirements:

```bash
pip install -r requirements.txt
```

3. Create the configuration file:

```bash
cp config.yml.example config.yml
```

4. Configure the following in `config.yml`:

   - `llm.api_key`: Your API key for the language model (e.g., Moonshot).
   - `llm.model`: The model you want to use (e.g., `kimi-k2-turbo-preview`).
   - `llm.base_url`: The base URL for the LLM API (e.g., `https://api.moonshot.cn/v1`).
   - `github.api_token`: Your GitHub API token (required for monitoring GitHub repositories).
   - `immunefi.bounties_file`: The path to your local bounties file (e.g., `bounties.json`).

5. Create your `bounties.json` file. This file should contain a list of bounty programs in the same format as the Immunefi API. See the example in the root directory.

6. Start the service:

```bash
python -m src.cli.main server start --log-level INFO
```

## Syncing project data

The server will automatically start syncing data based on the `scheduled_actions` in your `config.yml`. By default, it will sync the bounties from your `bounties.json` file every minute. You can monitor the `server.log` file for progress.

## Monitoring blockchain events

By default, Legion will run a webhook listener on port 8080. If you are running Legion locally, you can use a tool like [ngrok](https://ngrok.com/) to expose your local server to the internet.

To set up monitoring of proxy implementation upgrades for the [upgrade handler example](extensions/examples/proxy_implementation_upgrade_handler.py), you need to set up alerts with a provider like [Quicknode](https://www.quicknode.com/) or [Alchemy](https://www.alchemy.com/). Filter events by the 'Upgraded' topic. Here is how to do it with Quicknode:

```
tx_logs_topic0 == '0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b'
```
