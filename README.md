# R4dar - Your friendly web3 bug hunting assistant

A tool to monitor and analyze security programs and bug bounties.

## Setup

### 1. Install Dependencies

#### macOS
```bash
# Install PostgreSQL and pgvector
brew install postgresql
brew install pgvector

# Start PostgreSQL service
brew services start postgresql
```

#### Ubuntu/Debian
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

### 2. Create Database

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

### 3. Configure Application

1. Copy the example config:g
```bash
cp config.yml.example config.yml
```

2. Edit `config.yml` and set:
   - Database credentials
   - API keys (Etherscan, OpenAI)
   - Telegram bot settings (optional)

### 4. Initialize Application

```bash
# Install Python dependencies
pip install -r requirements.txt

# Initialize database schema and sync initial data
python -m src.cli.main initialize
```

## Usage

Start the server with Telegram interface:
```bash
python -m src.cli.main server start
```


