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
    # This is problematic and can cause errors on shutdown.
    # The default atexit handlers should be sufficient.
    pass


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
@click.pass_context
@async_command
async def server_start(ctx):
    """Start the server"""
    logger = ctx.obj["logger"]

    try:
        # Set logging level
        LogConfig.set_log_level(ctx.obj["log_level"])
        await Server.run()

    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise


@cli.group()
def project():
    """Project management commands"""


@project.command(name="create")
@click.argument("project_name")
@click.argument("project_type")
@click.argument("project_source")
@click.argument("keywords", required=False)
@click.pass_context
def project_create(ctx, project_name, project_type, project_source, keywords):
    """Create a new project"""
    from src.backend.database import DBSessionMixin
    from src.models.base import Project

    logger = ctx.obj["logger"]

    # Parse keywords if provided
    keyword_list = keywords.split(",") if keywords else []

    # Create session handler
    session_handler = DBSessionMixin()

    try:
        with session_handler.get_session() as session:
            project = Project(
                name=project_name,
                project_type=project_type,
                project_source=project_source,
                source_url=project_source if project_source.startswith("http") else None,
                keywords=keyword_list,
            )
            session.add(project)
            session.commit()
            logger.info(f"Created project {project.id}: {project_name}")
            return project.id
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise


@cli.command(name="import_assets")
@click.argument("project_id", type=int)
@click.argument("path", type=click.Path(exists=True))
@click.pass_context
def import_assets(ctx, project_id, path):
    """Import assets from a directory into a project"""
    from src.util.asset_import import AssetImporter

    logger = ctx.obj["logger"]

    try:
        importer = AssetImporter(project_id)
        imported_count = importer.import_directory(path)
        logger.info(f"Successfully imported {imported_count} assets")
    except Exception as e:
        logger.error(f"Failed to import assets: {e}")
        raise


@cli.command(name="expand_repos")
@click.argument("project_id", type=int, required=False)
@click.option("--all", is_flag=True, help="Process all projects with GitHub repos")
@click.pass_context
@async_command
async def expand_repos(ctx, project_id, all):
    """Expand GitHub repo assets into individual contract files"""
    from src.util.asset_import import RepoExpander

    logger = ctx.obj["logger"]

    try:
        if all:
            if project_id:
                logger.warning("Project ID ignored when --all flag is used")
            results = await RepoExpander.expand_all_projects()
            total_imported = sum(results.values())
            logger.info(f"Processed {len(results)} projects, imported {total_imported} files total")
            # Log individual project results
            for pid, count in results.items():
                logger.info(f"Project {pid}: imported {count} files")
        else:
            if not project_id:
                logger.error("Project ID required when not using --all flag")
                return
            expander = RepoExpander(project_id)
            imported_count = expander.expand_repos()
            logger.info(f"Successfully imported {imported_count} contract files from repos")
    except Exception as e:
        logger.error(f"Failed to expand repos: {e}")
        raise


if __name__ == "__main__":
    cli(obj={})
