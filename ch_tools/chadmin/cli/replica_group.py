from collections import OrderedDict

from cloup import argument, group, option, option_group, pass_context

from ch_tools.chadmin.internal.table_replica import (
    get_table_replica,
    list_table_replicas,
    restart_table_replica,
    restore_table_replica,
)
from ch_tools.common import logging
from ch_tools.common.cli.formatting import print_response
from ch_tools.common.clickhouse.client import ClickhouseError
from ch_tools.common.clickhouse.config import get_cluster_name


@group("replica")
def replica_group():
    """Commands to manage table replicas."""
    pass


@replica_group.command("get")
@argument("database_name", metavar="DATABASE")
@argument("table_name", metavar="TABLE")
@pass_context
def get_replica_command(ctx, database_name, table_name):
    """
    Get table replica.
    """
    print_response(ctx, get_table_replica(ctx, database_name, table_name))


@replica_group.command("list")
@option(
    "-d",
    "--database",
    "database_pattern",
    help="Filter in replicas to output by the specified database name pattern."
    " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
)
@option(
    "--exclude-database",
    "exclude_database_pattern",
    help="Filter out replicas to output by the specified database name pattern."
    " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
)
@option(
    "-t",
    "--table",
    "table_pattern",
    help="Filter in replicas to output by the specified table name."
    " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
)
@option(
    "--exclude-table",
    "exclude_table_pattern",
    help="Filter out replicas to output by the specified table name."
    " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
)
@option(
    "--read-only",
    "is_readonly",
    is_flag=True,
    help="Filter in replicas in read-only state only.",
)
@option(
    "-l",
    "--limit",
    type=int,
    default=1000,
    help="Limit the max number of objects in the output.",
)
@pass_context
def list_command(ctx, **kwargs):
    """
    List table replicas.
    """

    def _table_formatter(item):
        return OrderedDict(
            (
                ("database", item["database"]),
                ("table", item["table"]),
                ("zookeeper_path", item["zookeeper_path"]),
                ("replica_name", item["replica_name"]),
                ("is_readonly", item["is_readonly"]),
                ("absolute_delay", item["absolute_delay"]),
                ("queue_size", item["queue_size"]),
                (
                    "active_replicas",
                    f"{item['active_replicas']} / {item['total_replicas']}",
                ),
            )
        )

    table_replicas = list_table_replicas(ctx, verbose=True, **kwargs)
    print_response(
        ctx,
        table_replicas,
        default_format="table",
        table_formatter=_table_formatter,
    )


@replica_group.command("restart")
@option_group(
    "Replica selection options",
    option(
        "-a",
        "--all",
        "_all",
        is_flag=True,
        help="Filter in all replicas.",
    ),
    option(
        "-d",
        "--database",
        "database_pattern",
        help="Filter in replicas to restore by the specified database name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
    option(
        "--exclude-database",
        "exclude_database_pattern",
        help="Filter out replicas to restore by the specified database name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
    option(
        "-t",
        "--table",
        "table_pattern",
        help="Filter in replicas to restore by the specified table name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
    option(
        "--exclude-table",
        "exclude_table_pattern",
        help="Filter out replicas to restore by the specified table name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
)
@option(
    "--cluster",
    "--on-cluster",
    "on_cluster",
    is_flag=True,
    help="Restart replicas on all hosts of the cluster.",
)
@option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="Enable dry run mode and do not perform any modifying actions.",
)
@pass_context
def restart_replica_command(ctx, on_cluster, dry_run, **kwargs):
    """
    Restart one or several table replicas.
    """
    cluster = get_cluster_name(ctx) if on_cluster else None
    for replica in list_table_replicas(ctx, **kwargs):
        restart_table_replica(
            ctx,
            replica["database"],
            replica["table"],
            cluster=cluster,
            dry_run=dry_run,
        )


@replica_group.command("restore")
@option_group(
    "Replica selection options",
    option(
        "-a",
        "--all",
        "_all",
        is_flag=True,
        help="Filter in all replicas.",
    ),
    option(
        "-d",
        "--database",
        "database_pattern",
        help="Filter in replicas to restore by the specified database name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
    option(
        "--exclude-database",
        "exclude_database_pattern",
        help="Filter out replicas to restore by the specified database name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
    option(
        "-t",
        "--table",
        "table_pattern",
        help="Filter in replicas to restore by the specified table name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
    option(
        "--exclude-table",
        "exclude_table_pattern",
        help="Filter out replicas to restore by the specified table name pattern."
        " The value can be either a pattern in the LIKE clause format or a comma-separated list of items to match.",
    ),
)
@option(
    "--cluster",
    "--on-cluster",
    "on_cluster",
    is_flag=True,
    help="Restore replicas on all hosts of the cluster.",
)
@option(
    "-n",
    "--dry-run",
    is_flag=True,
    default=False,
    help="Enable dry run mode and do not perform any modifying actions.",
)
@pass_context
def restore_command(ctx, _all, on_cluster, dry_run, **kwargs):
    """
    Restore one or several table replicas.
    """
    cluster = get_cluster_name(ctx) if on_cluster else None
    ro_replicas = list_table_replicas(ctx, is_readonly=True, **kwargs)
    for replica in ro_replicas:
        try:
            restore_table_replica(
                ctx,
                replica["database"],
                replica["table"],
                cluster=cluster,
                dry_run=dry_run,
            )
        except ClickhouseError as e:
            msg = e.response.text
            if "Replica has metadata in ZooKeeper" in msg or "NO_ZOOKEEPER" in msg:
                logging.warning(
                    'Failed to restore replica with error "{}", attempting to recover by restarting replica and retrying restore',
                    msg,
                )
                restart_table_replica(
                    ctx,
                    replica["database"],
                    replica["table"],
                    cluster=cluster,
                    dry_run=dry_run,
                )
                restore_table_replica(
                    ctx,
                    replica["database"],
                    replica["table"],
                    cluster=cluster,
                    dry_run=dry_run,
                )
            elif "Replica path is present" in msg:
                logging.warning(
                    'Failed to restore replica with error "{}", attempting to recover by restarting replica',
                    msg,
                )
                restart_table_replica(
                    ctx,
                    replica["database"],
                    replica["table"],
                    cluster=cluster,
                    dry_run=dry_run,
                )
            else:
                raise
