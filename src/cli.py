"""CLI entry point for Agora tool."""

import asyncio
import logging
from pathlib import Path

import click

from .loader import load_config
from .pipeline import run_pipeline


def _default_config_path() -> str:
    """Find the default config file bundled with the package."""
    local_config = Path(__file__).resolve().parent / "config" / "agent.yaml"
    if local_config.exists():
        return str(local_config)

    import importlib.resources as pkg_resources
    ref = pkg_resources.files("src").joinpath("config/agents.yaml")
    with pkg_resources.as_file(ref) as path:
        return str(path)


@click.command()
@click.option(
    "--config", "-c",
    default=None,
    help="Path to YAML configuration file. Defaults to bundled agents.yaml.",
    type=click.Path(exists=True),
)
@click.option(
    "--topic", "-t",
    required=True,
    help="Discussion topic / idea to evaluate.",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Enable verbose logging.",
)
def main(config: str | None, topic: str, verbose: bool) -> None:
    """Multi-agent group discussion and voting tool.

    Agents with different LLM models discuss a topic and/or vote on it.
    Results are presented for user confirmation.

    Examples:

        # Full pipeline (uses bundled default config)
        agora -t "Should we build feature X?"

        # Custom config
        agora -c my_agents.yaml -t "Evaluate architecture Y"
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    config_path = config or _default_config_path()
    app_config = load_config(config_path)

    click.echo(f"已加载 {len(app_config.agents)} 个 Agent，配置文件：{config_path}")
    click.echo(f"讨论：{'开启' if app_config.discussion.enabled else '关闭'}")
    click.echo(f"投票：{'开启' if app_config.voting.enabled else '关闭'}")
    click.echo(f"结构化输出：{'开启' if app_config.supports_structured_output else '关闭（回退模式）'}")
    click.echo(f"话题：{topic}")
    click.echo()

    asyncio.run(run_pipeline(app_config, topic))


if __name__ == "__main__":
    main()
