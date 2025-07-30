"""Command-line interface for database management."""

import click
from flask import Flask
from .config import get_config
from .database import init_database
from .migrations import (
    setup_database, reset_database, get_database_info,
    create_sample_data_if_needed
)
from .db_utils import cleanup_inactive_tables, get_database_health


def create_app(config_name: str = 'development') -> Flask:
    """Create Flask app for CLI operations."""
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))
    init_database(app)
    return app


@click.group()
def cli():
    """Online Poker Platform Database CLI."""
    pass


@cli.command()
@click.option('--config', default='development', help='Configuration to use')
@click.option('--sample-data', is_flag=True, help='Create sample data')
def init_db(config, sample_data):
    """Initialize the database."""
    app = create_app(config)
    setup_database(app, create_sample_data=sample_data)
    click.echo("Database initialized successfully!")


@cli.command()
@click.option('--config', default='development', help='Configuration to use')
def reset_db(config):
    """Reset the database (WARNING: This will delete all data!)."""
    if click.confirm('This will delete all data. Are you sure?'):
        app = create_app(config)
        reset_database(app)
        click.echo("Database reset successfully!")
    else:
        click.echo("Operation cancelled.")


@cli.command()
@click.option('--config', default='development', help='Configuration to use')
def db_info(config):
    """Show database information."""
    app = create_app(config)
    info = get_database_info(app)
    
    click.echo("Database Information:")
    click.echo(f"  URL: {info['database_url']}")
    click.echo(f"  Tables: {', '.join(info['tables'])}")
    click.echo(f"  Users: {info['user_count']}")
    click.echo(f"  Tables: {info['table_count']}")
    click.echo(f"  Transactions: {info['transaction_count']}")
    click.echo(f"  Game History: {info['game_history_count']}")


@cli.command()
@click.option('--config', default='development', help='Configuration to use')
def create_sample_data(config):
    """Create sample data for development."""
    app = create_app(config)
    with app.app_context():
        create_sample_data_if_needed()
    click.echo("Sample data created!")


@cli.command()
@click.option('--config', default='development', help='Configuration to use')
@click.option('--timeout', default=30, help='Timeout in minutes')
def cleanup_tables(config, timeout):
    """Clean up inactive tables."""
    app = create_app(config)
    with app.app_context():
        count = cleanup_inactive_tables(timeout)
    click.echo(f"Cleaned up {count} inactive tables.")


@cli.command()
@click.option('--config', default='development', help='Configuration to use')
def health_check(config):
    """Check database health."""
    app = create_app(config)
    with app.app_context():
        health = get_database_health()
    
    click.echo("Database Health Check:")
    click.echo(f"  Status: {health['status']}")
    
    if health['status'] == 'healthy':
        click.echo(f"  Users: {health['user_count']}")
        click.echo(f"  Active Tables: {health['active_tables']}")
        click.echo(f"  Transactions: {health['total_transactions']}")
        click.echo(f"  Games: {health['total_games']}")
    else:
        click.echo(f"  Error: {health.get('error', 'Unknown error')}")


if __name__ == '__main__':
    cli()