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

1. Install the package:

```bash
pip install r4dar
```

2. Create configuration file:

```bash
cp config.example.yml config.yml
```

3. Configure the following in `config.yml`:
   - Database credentials
   - API keys:
     - Etherscan API key (for contract monitoring)
     - OpenAI API key (for AI analysis)
   - Telegram bot token (optional, for notifications)

4. Initialize the application:

```bash
r4dar initialize
```

## Verification

To verify your installation:

1. Start the service:

```bash
r4dar start
```

2. Check the logs for any errors:

```bash
r4dar logs
```

3. If using Telegram, send a test message to your bot:

```bash
/start
/help
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Check PostgreSQL service is running
   - Verify database credentials in config.yml
   - Ensure pgvector extension is installed

2. **API Key Issues**
   - Verify API keys are correctly set in config.yml
   - Check API key permissions and quotas

3. **Telegram Bot Not Responding**
   - Ensure bot token is correct
   - Check if bot is properly initialized with BotFather
   - Verify network connectivity

For more help, please [open an issue](https://github.com/yourusername/r4dar/issues) on our GitHub repository. 