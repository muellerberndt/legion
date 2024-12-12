# Installation Guide

This guide provides detailed instructions for setting up R4dar on your system.

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 13 or higher
- pgvector extension for PostgreSQL

## System-specific preparation

### macOS

```bash
# Install PostgreSQL and pgvector
brew install postgresql
brew install pgvector

# Start PostgreSQL service
brew services start postgresql
```

### Ubuntu/Debian

```bash
# Install PostgreSQL
sudo apt update
sudo apt install postgresql postgresql-contrib

# Install pgvector
sudo apt install postgresql-common
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install

# Start PostgreSQL service
sudo systemctl start postgresql
```

## Database Setup

1. Connect to PostgreSQL and create the database:

```bash
# Connect to PostgreSQL
psql postgres

# Create database and user
CREATE USER r4dar WITH PASSWORD 'your-password';
CREATE DATABASE r4dar_db OWNER r4dar;
\c r4dar_db

# Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Create vector index type
CREATE ACCESS METHOD vector_l2_ops USING ivfflat;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE r4dar_db TO r4dar;
GRANT ALL ON ALL TABLES IN SCHEMA public TO r4dar;
\q
```

2. Verify vector support:

```bash
# Connect to the database
psql r4dar_db

# Check if vector extension is enabled
\dx vector

# Check if vector operators are available
SELECT '[1,2,3]'::vector;

# Exit if everything works
\q
```

## R4dar Installation

First, clone the repository:

```bash
git clone git@github.com:muellerberndt/r4dar.git
cd r4dar
```

### Local Installation

1. Create a Python virtual environment:

```bash
pyenv virtualenv 3.12 r4dar
pyenv activate r4dar
```

2. Clone the repository and install requirements:


pip install -r requirements.txt
```

3. Create the configuration file:

```bash
cp config.example.yml config.yml
```

4. Configure the following in `config.yml`:
   - Telegram bot token and chat ID
   - Database credentials
   - API keys:
     - Block explorer API keys
     - OpenAI API key
     - GitHub API token (for GitHub watchers)
     - Quicknode API key (for onchain watchers)

5. Start the service:

```bash
r4dar --log-level INFO server start
```

### Deploying to the cloud

The easiest way to deploy R4dar to the cloud is to use a service like [Fly.io](https://fly.io).

1. Install the [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/)

2. Login to Fly.io:

```bash
fly auth signup
```

3. Create your fly.toml configuration:

```toml
app = "your-r4dar-app-name"
primary_region = "lax"

[build]
  builder = 'paketobuildpacks/builder:base'

[env]
  PORT = '8080'
  PYTHON_VERSION = '3.11'
  R4DAR_DATA_DIR = '/data'
  R4DAR_CONFIG = '/data/config.yml'
  R4DAR_WATCHERS = "immunefi,github"
  R4DAR_EXTENSIONS = "examples/proxy_implementation_upgrade_handler"
  R4DAR_EXTENSIONS_DIR = "extensions"
  PYTHONUNBUFFERED = "1"

[mounts]
  source = 'r4dar_data'
  destination = '/data'
  initial_size = '10gb'

[[vm]]
  memory = '4096MB'
  cpu_kind = 'shared'
  cpus = 2
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[deploy]
  strategy = 'rolling'

[processes]
  app = "/cnb/lifecycle/launcher python -m src.cli.main --log-level=INFO server start"
```

4. Set the environment variables:

```bash
fly secrets set R4DAR_BOT_TOKEN="your-telegram-bot-token"
fly secrets set R4DAR_CHAT_ID="your-telegram-chat-id"
fly secrets set OPEN_AI_KEY="your-openai-api-key"
fly secrets set R4DAR_ARBISCAN_KEY="your-arbiscan-api-key"
fly secrets set R4DAR_BASESCAN_KEY="your-basescan-api-key"
fly secrets set R4DAR_GITHUB_TOKEN="your-github-token"
fly secrets set R4DAR_QUICKNODE_KEY="your-quicknode-api-key"
# Add any additional API keys as needed
```

5. Create and attach a persistent volume:

```bash
fly volumes create r4dar_data --size 10 --region lax
fly volumes list
```

6. Deploy the app:

```bash
fly deploy
```

## Syncing project data

You should now be able to interact with the bot on Telegram. Run the following command to sync the database:

```bash
/immunefi silent
```
