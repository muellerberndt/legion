import click
import asyncio
from src.server.server import Server
from src.config.config import Config
from src.util.logging import LogConfig, Logger
from functools import wraps
import atexit
import concurrent.futures
import threading


def cleanup_thread_pools():
    """Clean up any remaining thread pools"""
    # Shutdown any remaining thread pools
    concurrent.futures.thread._threads_queues.clear()
    # Clear threading._threads set
    if hasattr(threading, "_threads"):
        threading._threads.clear()


def async_command(f):
    """Decorator to run async click commands"""

    @wraps(f)
    def wrapper(*args, **kwargs):
        logger = Logger("CLI")
        loop = None
        try:
            # Register cleanup handler
            atexit.register(cleanup_thread_pools)

            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Run the command
            result = loop.run_until_complete(f(*args, **kwargs))
            return result

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
            if loop:
                # Cancel all running tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                # Run cleanup handlers immediately
                cleanup_thread_pools()

        except Exception as e:
            logger.error(f"Command failed: {e}")
            raise
        finally:
            if loop and not loop.is_closed():
                loop.close()
            # Ensure cleanup runs
            cleanup_thread_pools()
            # Unregister cleanup handler
            atexit.unregister(cleanup_thread_pools)

    return wrapper


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging (same as --log-level DEBUG)")
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="WARNING",
    help="Set logging level",
)
@click.pass_context
def cli(ctx, verbose, log_level):
    """Legion CLI"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["log_level"] = "DEBUG" if verbose else log_level
    ctx.obj["logger"] = Logger("CLI")

    # Configure logging
    LogConfig.set_log_level(ctx.obj["log_level"])

    # Load config
    Config()


@cli.group()
def server():
    """Server management commands"""


@server.command(name="start")
@click.option("--interface", "-i", default="telegram", help="Interface to start (default: telegram)")
@click.pass_context
@async_command
async def server_start(ctx, interface):
    """Start the server with specified interface"""
    logger = ctx.obj["logger"]

    try:
        # Set logging level
        LogConfig.set_log_level(ctx.obj["log_level"])
        await Server.run([interface])

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


if __name__ == "__main__":
    cli(obj={})
