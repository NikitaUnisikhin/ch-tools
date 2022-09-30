from cloud.mdb.clickhouse.tools.chadmin.internal.utils import execute_query
from click import ClickException


def get_process(ctx, query_id):
    """
    Get executing query from system.processes table.
    """
    processes = list_processes(ctx, query_id=query_id, verbose=True)

    if not processes:
        raise ClickException(f'Process {query_id} not found.')

    return processes[0]


def list_processes(
    ctx,
    user=None,
    exclude_user=None,
    query_id=None,
    query_pattern=None,
    cluster=None,
    limit=None,
    order_by='elapsed',
    verbose=False,
):
    """
    Get list of executing queries from system.processes table.
    """
    query = """
        SELECT
        {% if cluster %}
             hostName() "host",
        {% endif %}
             query_id,
             elapsed,
             query,
             is_cancelled,
             concat(toString(read_rows), ' rows / ', formatReadableSize(read_bytes)) "read",
             concat(toString(written_rows), ' rows / ', formatReadableSize(written_bytes)) "written",
             formatReadableSize(memory_usage) "memory usage",
             user,
             multiIf(empty(client_name),
                     http_user_agent,
                     concat(client_name, ' ',
                            toString(client_version_major), '.',
                            toString(client_version_minor), '.',
        {% if not verbose %}
                            toString(client_version_patch))) "client"
        {% else %}
                            toString(client_version_patch))) "client",
        {%     if version_ge('21.8') -%}
        ProfileEvents,
        Settings
        {%     else -%}
        ProfileEvents.Names,
        ProfileEvents.Values,
        Settings.Names,
        Settings.Values
        {%     endif -%}
        {% endif %}
        {% if cluster %}
        FROM clusterAllReplicas({{ cluster }}, system.processes)
        {% else %}
        FROM system.processes
        {% endif %}
        WHERE 1
        {% if user %}
          AND user = '{{ user }}'
        {% endif %}
        {% if exclude_user %}
          AND user != '{{ exclude_user }}'
        {% endif %}
        {% if query_id %}
          AND query_id = '{{ query_id }}'
        {% endif %}
        {% if query_pattern %}
          AND lower(query) LIKE lower('{{ query_pattern }}')
        {% endif %}
        {% if not query_id %}
        ORDER BY {{ order_by }} DESC
        {% endif %}
        {% if limit %}
        LIMIT {{ limit }}
        {% endif %}
        """
    return execute_query(
        ctx,
        query,
        user=user,
        exclude_user=exclude_user,
        query_id=query_id,
        query_pattern=query_pattern,
        cluster=cluster,
        limit=limit,
        verbose=verbose,
        order_by=order_by,
        format='JSON',
    )['data']


def kill_process(ctx, query_id=None, user=None, exclude_user=None):
    """
    Perform "KILL QUERY".
    """
    query_str = """
        KILL QUERY
        WHERE 1
        {% if user %}
          AND user = '{{ user }}'
        {% endif %}
        {% if exclude_user %}
          AND user != '{{ exclude_user }}'
        {% endif %}
        {% if query_id %}
          AND query_id = '{{ query_id }}'
        {% endif %}
        """
    print(execute_query(ctx, query_str, query_id=query_id, user=user, exclude_user=exclude_user))


def list_merges(ctx, *, cluster=None, limit=None):
    """
    Get list of executing merges from system.merges table.
    """
    query = """
        SELECT
        {% if cluster %}
            hostName() "host",
        {% endif %}
            database,
            table,
            elapsed,
            progress,
            is_mutation,
        {% if version_ge('21.3') -%}
            merge_type,
            merge_algorithm,
        {% endif %}
            partition_id,
            num_parts,
            source_part_names,
            result_part_name,
            source_part_paths,
            result_part_path,
            total_size_bytes_compressed,
            total_size_marks,
            bytes_read_uncompressed,
            rows_read,
            bytes_written_uncompressed,
            rows_written,
            columns_written,
            memory_usage,
            thread_id
        {% if cluster %}
        FROM clusterAllReplicas({{ cluster }}, system.merges)
        {% else %}
        FROM system.merges
        {% endif %}
        {% if limit %}
        LIMIT {{ limit }}
        {% endif %}
        """
    return execute_query(
        ctx,
        query,
        cluster=cluster,
        limit=limit,
        format='JSON',
    )['data']