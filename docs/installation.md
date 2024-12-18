# Installation Guide

This guide provides detailed instructions for setting up Legion on your system.

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
CREATE USER legion WITH PASSWORD 'your-password';
CREATE DATABASE legion_db OWNER legion;
\c legion_db

# Enable vector extension
CREATE EXTENSION IF NOT EXISTS vector;

# Create vector index type
CREATE ACCESS METHOD vector_l2_ops USING ivfflat;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE legion_db TO legion;
GRANT ALL ON ALL TABLES IN SCHEMA public TO legion;
\q
```

2. Verify vector support:

```bash
# Connect to the database
psql legion_db

# Check if vector extension is enabled
\dx vector

# Check if vector operators are available
SELECT '[1,2,3]'::vector;

# Exit if everything works
\q
```

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
legion --log-level INFO server start
```

### Deploying to the cloud

The easiest way to deploy Legion to the cloud is to use a service like [Fly.io](https://fly.io).

1. Install the [Fly.io CLI](https://fly.io/docs/hands-on/install-flyctl/)

2. Login to Fly.io:

```bash
fly auth signup
```

3. Create your fly.toml configuration:

```toml
app = "your-legion-app-name"
primary_region = "lax"

[build]
  builder = 'paketobuildpacks/builder:base'

[env]
  PORT = '8080'
  PYTHON_VERSION = '3.11'
  LEGION_DATA_DIR = '/data'
  LEGION_CONFIG = '/data/config.yml'
  LEGION_WATCHERS = "immunefi,github"
  LEGION_EXTENSIONS = "examples/proxy_implementation_upgrade_handler"
  LEGION_EXTENSIONS_DIR = "extensions"
  PYTHONUNBUFFERED = "1"

[mounts]
  source = 'legion_data'
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
fly secrets set LEGION_BOT_TOKEN="your-telegram-bot-token"
fly secrets set LEGION_CHAT_ID="your-telegram-chat-id"
fly secrets set OPEN_AI_KEY="your-openai-api-key"
fly secrets set LEGION_ARBISCAN_KEY="your-arbiscan-api-key"
fly secrets set LEGION_BASESCAN_KEY="your-basescan-api-key"
fly secrets set LEGION_GITHUB_TOKEN="your-github-token"
fly secrets set LEGION_QUICKNODE_KEY="your-quicknode-api-key"
# Add any additional API keys as needed
```

5. Create and attach a persistent volume:

```bash
fly volumes create legion_data --size 10 --region lax
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
