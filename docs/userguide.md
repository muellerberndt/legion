# User Guide

Welcome to Legion! This guide will help you get started with using Legion's features through its Telegram interface.

## Getting Started

### Checking System Status

The first thing you might want to do is check if Legion is running properly. Use the `/status` command to see:
- Running and completed jobs
- Database statistics
- Installed extensions
- Scheduled actions
- Webhook server status

```
/status
```

### Getting Help

To see all available commands, use:
```
/help
```

For detailed help about a specific command:
```
/help <command_name>
```

## Basic Usage

Legion offers two ways to interact with the system:
1. Direct commands (e.g., `/status`, `/help`)
2. Natural language requests to the AI chatbot

### Using Direct Commands

Commands follow this format:
```
/command_name [parameters]
```

For example:
```
/help status     # Get help about the status command
/immunefi silent # Sync Immunefi data without notifications
```

### Chatting with the AI

Instead of remembering commands, you can simply tell Legion what you want to do. The AI will understand and execute the appropriate commands:

```
"Show me the system status"
"What commands are available?"
"Check if there are any new GitHub updates"
```

## Working with Data

### Querying the Database

While Legion has a direct database query system, it's recommended to use natural language queries through the chatbot:

```
"Show me all projects with high severity bugs"
"Find vulnerabilities reported in the last 24 hours"
"List all smart contract projects using Solidity"
```

The chatbot will translate these requests into proper database queries and format the results nicely for you.

## Complex Tasks with Autobot

For more complex tasks that require multiple steps use the `/autobot` command. Autobot is an autonomous agent that can plan and execute sequences of actions.

### Basic Autobot Usage

```
TODO - example
```

### Example Complex Tasks

Here are some examples of what you can ask autobot to do:

```
TODO - examples
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

