from click import Choice, argument, group, option, pass_context
from cloud.mdb.cli.common.formatting import print_response

from cloud.mdb.clickhouse.tools.chadmin.cli import get_cluster_name
from cloud.mdb.clickhouse.tools.chadmin.internal.process import get_process, list_processes, kill_process
from cloud.mdb.clickhouse.tools.chadmin.internal.utils import format_query

FIELD_FORMATTERS = {
    'query': format_query,
}


@group('process')
def process_group():
    """Process management commands."""
    pass


@process_group.command('get')
@argument('query_id')
@pass_context
def get_process_command(ctx, query_id):
    """
    Get process.
    """
    process = get_process(ctx, query_id)
    print_response(ctx, process, default_format='yaml', field_formatters=FIELD_FORMATTERS)


@process_group.command('list')
@option('-u', '--user')
@option('-U', '--exclude-user')
@option('--query')
@option('-v', '--verbose', is_flag=True)
@option('--cluster', '--on-cluster', 'on_cluster', is_flag=True, help='Get records from all hosts in the cluster.')
@option('--order-by', type=Choice(['elapsed', 'memory_usage']), default='elapsed')
@option('-l', '--limit', type=int, help='Limit the max number of objects in the output.')
@pass_context
def list_processes_command(ctx, user, exclude_user, query, verbose, on_cluster, order_by, limit):
    """
    List processes.
    """
    cluster = get_cluster_name(ctx) if on_cluster else None

    processes = list_processes(
        ctx,
        user=user,
        exclude_user=exclude_user,
        query_pattern=query,
        cluster=cluster,
        limit=limit,
        order_by=order_by,
        verbose=verbose,
    )

    print_response(ctx, processes, default_format='yaml', field_formatters=FIELD_FORMATTERS)


@process_group.command('kill')
@argument('query_id', required=False)
@option('-u', '--user')
@option('-U', '--exclude-user')
@option('-a', '--all', is_flag=True, help='Kill all processes.')
@pass_context
def kill_process_command(ctx, query_id, all, user, exclude_user):
    """
    Kill one or several processes using "KILL QUERY" query.
    """
    if not any((query_id, all, user, exclude_user)):
        ctx.fail('At least one of QUERY_ID, --all, --user and --exclude-user options must be specified.')

    kill_process(ctx, query_id=query_id, user=user, exclude_user=exclude_user)
