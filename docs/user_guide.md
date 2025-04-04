# User Guide

Welcome to Legion! This guide will help you get started with using Legion's features through its Telegram interface.

## Basic Usage

Legion is meant to be used as a base framework for security researchers. By adding your own actions, jobs and agent prompts, you can build up an army of agents that do your bidding. However, Legion also ships with a few built-in features that can be used as a starting point for your own projects.

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

### Built-in tools

The base version of Legion has a few built-in tools. Those are meant to be run regularly to keep the system up to date (you can schedule them in the config individually or schedule an autobot that runs them).

- `/immunefi` - Sync Immunefi data. Run with `silent` to sync without notifications. Will detect newly added projects and changes to existing ones. 
- `/github_monitor` - Monitor GitHub repositories. This will fetch the latest commits and pull requests for all tracked repositories and evaluate whether the changes might impact the security of the project.
- `/proxy_monitor` - Downloads the implementations of all proxy contracts (EVM) and checks for implementation upgrades.
- `/embeddings` - Create embeddings for all assets in the database. The embeddings are used by the `/semantic_search` command.

## Working with Data

### Querying the Database

While Legion has a direct database query system, it's recommended to use natural language queries through the chatbot:

```
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

