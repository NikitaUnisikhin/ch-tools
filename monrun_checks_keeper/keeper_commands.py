import os
import re
import socket
import time

from click import command, pass_context
from kazoo.client import KazooClient
from cloud.mdb.clickhouse.tools.common.result import Result
from cloud.mdb.clickhouse.tools.common.clickhouse import ClickhouseKeeperConfig

ZOOKEEPER_CFG_FILE = '/etc/zookeeper/conf/zoo.cfg'
DEFAULT_ZOOKEEPER_DATA_DIR = '/var/lib/zookeeper'
DEFAULT_ZOOKEEPER_DATA_LOG_DIR = '/var/log/zookeeper'


@command('alive')
@pass_context
def alive_command(ctx):
    """Check (Zoo)Keeper service is alive"""
    try:
        keeper_port = get_keeper_port()
        client = KazooClient(
            f'127.0.0.1:{keeper_port}',
            connection_retry=ctx.obj.get('retries'),
            command_retry=ctx.obj.get('retries'),
            timeout=ctx.obj.get('timeout'),
        )
        client.start()
        client.get("/")
        client.create(path='/{0}_alive'.format(socket.getfqdn()), ephemeral=True)
        client.stop()
    except Exception as e:
        return Result(2, repr(e))

    return Result(0, 'OK')


@command('avg_latency')
@pass_context
def avg_latency_command(ctx):
    """Check average (Zoo)Keeper latency"""
    return Result(0, keeper_mntr(ctx)['zk_avg_latency'])


@command('min_latency')
@pass_context
def min_latency_command(ctx):
    """Check minimum (Zoo)Keeper latency"""
    return Result(0, keeper_mntr(ctx)['zk_min_latency'])


@command('max_latency')
@pass_context
def max_latency_command(ctx):
    """Check maximum (Zoo)Keeper latency"""
    return Result(0, keeper_mntr(ctx)['zk_max_latency'])


@command('queue')
@pass_context
def queue_command(ctx):
    """Check number of queued requests on (Zoo)Keeper server"""
    return Result(0, keeper_mntr(ctx)['zk_outstanding_requests'])


@command('descriptors')
@pass_context
def descriptors_command(ctx):
    """Check number of open file descriptors on (Zoo)Keeper server"""
    return Result(0, keeper_mntr(ctx)['zk_open_file_descriptor_count'])


@command('version')
@pass_context
def get_version_command(ctx):
    """Check (Zoo)Keeper version"""
    return Result(0, keeper_mntr(ctx)['zk_version'])


@command('snapshot')
def check_snapshots():
    """Check (Zoo)Keeper snapshots"""
    latest = 'No (zoo)keeper snapshots done yet'
    if os.path.exists(ZOOKEEPER_CFG_FILE):
        files = get_snapshot_files(read_zookeeper_config().get('dataDir', DEFAULT_ZOOKEEPER_DATA_DIR))
    else:
        files = get_snapshot_files(ClickhouseKeeperConfig.load().snapshots_dir)
    if len(files) > 0:
        latest = sorted(files, key=os.path.getctime, reverse=True)[0]
    return Result(0, latest)


@command('last_null_pointer')
def check_last_null_pointer_exc():
    """
    Get moment from Zookeeper logs then NullPointerException appeared during last 24 hours
    """
    if not os.path.exists(ZOOKEEPER_CFG_FILE):
        return Result(0, 'OK')

    files = get_zookeeper_log_files_for_last_day()
    if len(files) == 0:
        return Result(0, 'OK')
    prev_line = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getctime(files[0])))
    latest = None
    for file in files:
        with open(file) as f:
            for line in f:
                if 'java.lang.NullPointerException' in line:
                    latest = prev_line.split('[')[0].strip()
                prev_line = line
    if latest:
        return Result(1, latest)
    return Result(0, 'OK')


def get_zookeeper_log_files_for_last_day():
    """Collect Zookeeper logs for last 24 hours"""
    current_timestamp = time.time()
    logs_path = read_zookeeper_config().get('dataLogDir', DEFAULT_ZOOKEEPER_DATA_LOG_DIR)
    log_files = filter(
        lambda file: (current_timestamp - os.path.getmtime(file)) < 60 * 60 * 24,
        [os.path.join(root, name) for root, _, files in os.walk(logs_path) for name in files if name.endswith('.log')],
    )
    return sorted(log_files, key=os.path.getctime)


def get_snapshot_files(snapshots_dir):
    """Get snapshot file in mentioned directory"""
    return [
        os.path.join(root, name)
        for root, _, files in os.walk(snapshots_dir)
        for name in files
        if name.startswith('snapshot')
    ]


def read_zookeeper_config():
    """Read Zookeeper configuration file and return content as dict"""
    config = {}
    if not os.path.exists(ZOOKEEPER_CFG_FILE):
        return config
    with open(ZOOKEEPER_CFG_FILE) as f:
        for line in f:
            conf_line = line.split('=')
            if len(conf_line) > 1:
                config[conf_line[0].strip()] = conf_line[1].strip()
    return config


def get_keeper_port():
    """
    Return port for (Zoo)Keeper - default(2181) or from CH configs
    """
    try:
        return ClickhouseKeeperConfig.load().port or 2181
    except FileNotFoundError:
        return 2181


def keeper_command(command, timeout):
    """
    Execute (Zoo)Keeper 4-letter command.
    """
    port = int(get_keeper_port())
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect(("localhost", port))
        s.sendall(command.encode())
        return s.makefile().read(-1)


def keeper_mntr(ctx):
    """
    Execute (Zoo)Keeper mntr command and parse its output.
    """
    result = {}
    attempt = 0
    while True:
        try:
            response = keeper_command('mntr', ctx.obj.get('timeout', 3))
            for line in response.split('\n'):
                key_value = re.split('\\s+', line, 1)
                if len(key_value) == 2:
                    result[key_value[0]] = key_value[1]

            if len(result) <= 1:
                raise RuntimeError(f'Too short response: {response.strip()}')

            break
        except Exception as e:
            if attempt >= ctx.obj.get('retries', 3):
                raise e
            attempt += 1
            time.sleep(0.5)
    return result