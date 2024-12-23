# User Guide

Welcome to Legion! This guide will help you get started with using Legion's features through its Telegram interface.

## Basic Usage

Legion offers two ways to interact with the system:

1. "Low level" commands (e.g., `/file_search`, `/db_query`)
2. Natural language requests to the AI chatbot

Normally, you'll want to use the chatbot to interact with the database and local files.

### System Status and Help

To see all available commands, use:
```
/help
```

For detailed help about a specific command:
```
/help <command_name>
```

To see the status of the system, use:
```
/status
```

### Using Direct Commands

Commands follow this format:
```
/command_name [parameters]
```

For example:
```
/help status     # Get help about the status command
/immunefi silent # Sync Immunefi data without notifications
/list_jobs       # List all running jobs
```

### Chatting with the AI

For most operations including database queries and file searches, you'll likely want to use the chatbot. The AI will understand and execute the appropriate commands:

```
"Show me the system status"
"What commands are available?"
"Search all assets for the string 'using SignatureUtil for bytes', then give me a list of the associated projects"
"Give me the name of the project that address 0xa0ed89af63367ddc8e1dd6b992f20d1214ccb51c is associated with, if any."

```

## Working with Data

### Querying the Database

While Legion has a direct database query system, it's recommended to use natural language queries through the chatbot:

```
"Show me 5 projects that have been updated in the last 30 days"
"List all smart contract projects that use Rust and have been updated in the last 30 days"
```

## Working with Jobs

Legion uses a job system for long-running tasks. The GitHub monitor is a good example:

```
/github_monitor
```

This creates a job that:
1. Checks all tracked GitHub repositories
2. Fetches new commits and pull requests
3. Analyzes changes
4. Sends notifications for important updates

### Managing Jobs

To see running jobs:
```
/jobs list
```

To get a job's result:
```
/job get <job_id>
```

To stop a running job:
```
/job stop <job_id>
```

## Scheduling Actions

Legion can run actions on a schedule. Configure scheduled actions in your `config.yml`:

```yaml
schedules:
  github_monitor:
    command: "github_monitor"
    interval_minutes: 60
    enabled: true

  security_scan:
    command: "autobot"
    args: "TODO - example"
    interval_minutes: 1440  # Daily
    enabled: true
```

This configuration:
1. Runs GitHub monitoring every hour
2. Executes a daily security scan using autobot

The scheduler will maintain these tasks and restart them if needed. You can check scheduled tasks status using the `/status` command.

