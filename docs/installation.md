# Installation Guide

This guide provides detailed instructions for setting up R4dar on your system.

## Prerequisites

- Python 3.9 or higher
- PostgreSQL 13 or higher
- pgvector extension for PostgreSQL

## System-specific Installation

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
CREATE EXTENSION vector;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE r4dar_db TO r4dar;
\q
```

## R4dar Installation

1. Clone the repository and install requirements:

```bash
git clone git@github.com:muellerberndt/r4dar.git
cd r4dar
pip install -r requirements.txt
```

2. Create the configuration file:

```bash
cp config.example.yml config.yml
```

3. Configure the following in `config.yml`:
   - Telegram bot token and chat ID
   - Database credentials
   - API keys:
     - Block explorer API keys
     - OpenAI API key
     - GitHub API token (for GitHub watcher)
     - Quicknode API key

4. Initialize the database:

```bash
./r4dar.sh init-db
./r4dar.sh initial-sync
```

5. Start the service:

```bash
r4dar --log-level INFO server start
```

You should now be able to interact with the bot on Telegram using the following commands:

```bash
/start
/help0
```
