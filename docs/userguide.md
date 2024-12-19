# User Guide

## Monitoring blockchain events

By default, Legion will run a webhook listener on port 8080. If you are running Legion locally, you can use a tool like [ngrok](https://ngrok.com/) to expose your local server to the internet.
[
To set up monitoring of proxy implementation upgrades for the [upgrade handler example](extensions/examples/proxy_implementation_upgrade_handler.py), you need to set up alerts with a provider like [Quicknode](https://www.quicknode.com/) or [Alchemy](https://www.alchemy.com/). Filter events by the 'Upgraded' topic. Here is how to do it with Quicknode:

```
tx_logs_topic0 == '0xbc7cd75a20ee27fd9adebab32041f755214dbc6bffa90cc0225b39da2e5c2d3b' 
```
