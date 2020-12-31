import logging
import logging.handlers
import random
import sys
from typing import Dict, List, Union

from ratelimitingfilter import RateLimitingFilter

from synchp.broker import Broker
from synchp.broker.kafka import KafkaBroker
from synchp.broker.redis import RedisBroker
from synchp.common import cluster_sql
from synchp.enums import BrokerType, ClickHouseEngine, SourceDatabase
from synchp.exceptions import ConfigurationError
from synchp.reader import Reader
from synchp.settings import Settings
from synchp.writer import ClickHouse
from synchp.writer.collapsing_merge_tree import ClickHouseCollapsingMergeTree
from synchp.writer.merge_tree import ClickHouseMergeTree
from synchp.writer.replacing_merge_tree import ClickHouseReplacingMergeTree
from synchp.writer.versioned_collapsing_merge_tree import ClickHouseVersionedCollapsingMergeTree

_readers: Dict[str, Reader] = {}
_writers: Dict[str, List[ClickHouse]] = {}
_brokers: Dict[str, Broker] = {}


def get_reader(alias: str) -> Reader:
    """
    get reader once
    """
    r = _readers.get(alias)
    if not r:
        source_db = Settings.get_source_db(alias)
        if not source_db:
            raise ConfigurationError(f"Can't find alias {alias} in config.")
        db_type = source_db.get("db_type")
        if db_type == SourceDatabase.mysql.value:
            from synchp.reader.mysql import Mysql

            r = Mysql(alias)
        elif db_type == SourceDatabase.postgres.value:
            from synchp.reader.postgres import Postgres

            r = Postgres(alias)
        else:
            raise ConfigurationError(f"Unsupported db_type {db_type}")
        _readers[alias] = r
    return r


def get_writer(engine: ClickHouseEngine = None, choice=True) -> Union[ClickHouse, List[ClickHouse]]:
    """
    get writer once
    """
    writers = _writers.get(engine)
    if not choice:
        return writers
    if not writers:
        settings = Settings.get("clickhouse")
        hosts = settings.get("hosts")
        if Settings.is_cluster() and len(hosts) <= 1:
            raise ConfigurationError("hosts must more than one when cluster")
        for host in hosts:
            args = [host, settings.get("user"), settings.get("password"), Settings.cluster_name()]
            if engine == ClickHouseEngine.merge_tree.value:
                w = ClickHouseMergeTree(*args)
            elif engine == ClickHouseEngine.collapsing_merge_tree:
                w = ClickHouseCollapsingMergeTree(*args)
            elif engine == ClickHouseEngine.versioned_collapsing_merge_tree:
                w = ClickHouseVersionedCollapsingMergeTree(*args)
            elif engine == ClickHouseEngine.replacing_merge_tree or engine is None:
                w = ClickHouseReplacingMergeTree(*args)
            else:
                w = ClickHouse(*args)
            _writers.setdefault(engine, []).append(w)
    return random.choice(_writers.get(engine))  # nosec:B311


def get_broker(alias: str) -> Broker:
    b = _brokers.get(alias)
    broker_type = Settings.get_source_db(alias).get("broker_type")
    if not b:
        if broker_type == BrokerType.redis:
            b = RedisBroker(alias)
        elif broker_type == BrokerType.kafka:
            b = KafkaBroker(alias)
        else:
            raise ConfigurationError(f"Unsupported broker_type {broker_type}")
        _brokers[alias] = b
    return b


def init_logging():
    """
    init logging config
    :param debug:
    :return:
    """
    base_logger = logging.getLogger("synchp")
    debug = Settings.debug()
    if debug:
        base_logger.setLevel(logging.DEBUG)
    else:
        base_logger.setLevel(logging.INFO)
    fmt = logging.Formatter(
        fmt="%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    sh = logging.StreamHandler(sys.stdout)
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(fmt)
    base_logger.addHandler(sh)
    mail = Settings.get("mail")
    if mail:
        rate_limit = RateLimitingFilter(per=60)
        sh = logging.handlers.SMTPHandler(
            mailhost=mail.get("mailhost"),
            fromaddr=mail.get("fromaddr"),
            toaddrs=mail.get("toaddrs"),
            subject=mail.get("subject"),
            credentials=(mail.get("user"), mail.get("password")),
        )
        sh.setLevel(logging.ERROR)
        sh.setFormatter(fmt)
        sh.addFilter(rate_limit)
        base_logger.addHandler(sh)


def init_monitor_db(cluster_name: str = None):
    """
    init monitor db
    """
    writer = get_writer()
    sql_create_db = f"create database if not exists synch {cluster_sql(cluster_name)}"
    writer.execute(sql_create_db)
    if cluster_name:
        engine = "ReplicatedMergeTree('/clickhouse/tables/{{shard}}/synch/log','{{replica}}')"
    else:
        engine = "ReplacingMergeTree"
    sql_create_tb = f"""create table if not exists synch.log {cluster_sql(cluster_name)}
(
    id         int,
    alias      String,
    schema     String,
    table      String,
    num        int,
    type       int,
    created_at DateTime
)
    engine = {engine} partition by toYYYYMM(created_at) order by id;"""
    writer.execute(sql_create_tb)


def init(config_file):
    """
    init
    """
    Settings.init(config_file)
    init_logging()
    dsn = Settings.get("sentry", "dsn")
    if dsn:
        import sentry_sdk
        from sentry_sdk.integrations.redis import RedisIntegration

        sentry_sdk.init(
            dsn,
            environment=Settings.get("sentry", "environment"),
            integrations=[RedisIntegration()],
        )
    if Settings.monitoring():
        init_monitor_db(Settings.cluster_name())
