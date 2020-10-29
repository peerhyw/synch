import logging
import time
from signal import Signals
from typing import Callable, Generator, Tuple, Union

import MySQLdb
from MySQLdb.cursors import DictCursor
from pymysqlreplication import BinLogStreamReader
from pymysqlreplication.event import QueryEvent
from pymysqlreplication.row_event import DeleteRowsEvent, UpdateRowsEvent, WriteRowsEvent

from synch.broker import Broker
from synch.convert import SqlConvert
from synch.reader import Reader
from synch.redis import RedisLogPos
from synch.settings import Settings
# from synch.replication.etl import etl_create_table
from synch.factory import get_writer

logger = logging.getLogger("synch.reader.mysql")


class Mysql(Reader):
    only_events = (DeleteRowsEvent, WriteRowsEvent, UpdateRowsEvent, QueryEvent)
    fix_column_type = True

    def __init__(self, alias):
        super().__init__(alias)
        source_db = self.source_db
        self.conn = MySQLdb.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            connect_timeout=5,
            cursorclass=DictCursor,
            charset="utf8",
        )
        self.conn.autocommit(True)
        self.init_binlog_file = source_db.get("init_binlog_file")
        self.init_binlog_pos = source_db.get("init_binlog_pos")
        self.server_id = source_db.get("server_id")
        self.skip_dmls = source_db.get("skip_dmls") or []
        self.skip_delete_tables = source_db.get("skip_delete_tables") or []
        self.skip_update_tables = source_db.get("skip_update_tables") or []
        self.cursor = self.conn.cursor()
        self.databases = list(map(lambda x: x.get("database"), source_db.get("databases")))
        self.pos_handler = RedisLogPos(alias)
        self.default_schema = self.source_db.get("databases")[0].get('database')

    def get_source_select_sql(self, schema: str, table: str, sign_column: str = None):
        select = "*"
        if sign_column:
            select += f", toInt8(1) as {sign_column}"
        return f"SELECT {select} FROM mysql('{self.host}:{self.port}', '{schema}', '{table}', '{self.user}', '{self.password}')"

    def get_binlog_pos(self) -> Tuple[str, str]:
        """
        get binlog pos from master
        """
        sql = "show master status"
        result = self.execute(sql)[0]
        return result.get("File"), result.get("Position")

    def get_primary_key(self, db, table) -> Union[None, str, Tuple[str, ...]]:
        """
        get pk
        :param db:
        :param table:
        :return:
        """
        pri_sql = f"select COLUMN_NAME from information_schema.COLUMNS where TABLE_SCHEMA='{db}' and TABLE_NAME='{table}' and COLUMN_KEY='PRI'"
        result = self.execute(pri_sql)
        if not result:
            return None
        if len(result) > 1:
            return tuple(map(lambda x: x.get("COLUMN_NAME"), result))
        return result[0]["COLUMN_NAME"]

    def signal_handler(self, signum: Signals, handler: Callable):
        sig = Signals(signum)
        log_f, log_p = self.pos_handler.get_log_pos()
        logger.info(f"shutdown producer on {sig.name}, current position: {log_f}:{log_p}")
        exit()

    def start_sync(self, broker: Broker, alias: str):
        log_file, log_pos = self.pos_handler.get_log_pos()
        if not (log_file and log_pos):
            log_file = self.init_binlog_file
            log_pos = self.init_binlog_pos
            if not (log_file and log_pos):
                log_file, log_pos = self.get_binlog_pos()
            self.pos_handler.set_log_pos_slave(log_file, log_pos)

        log_pos = int(log_pos)
        logger.info(f"mysql binlog: {log_file}:{log_pos}")

        tables = []
        schema_tables = {}
        for database in self.source_db.get("databases"):
            database_name = database.get("database")
            auto_create_table = database.get("auto_create_table")
            for table in database.get("tables"):
                table_name = table.get("table")
                schema_tables.setdefault(database_name, []).append(table_name)
                pk = self.get_primary_key(database_name, table_name)
                if not pk or isinstance(pk, tuple):
                    # skip delete and update when no pk and composite pk
                    database_table = f"{database_name}.{table_name}"
                    if database_table not in database_table:
                        self.skip_delete_tables.append(database_table)
                tables.append(table_name)
        only_schemas = self.databases
        only_tables = list(set(tables))
        for schema, table, event, file, pos in self._binlog_reading(
            only_tables=only_tables,
            only_schemas=only_schemas,
            log_file=log_file,
            log_pos=log_pos,
            server_id=self.server_id,
            skip_dmls=self.skip_dmls,
            skip_delete_tables=self.skip_delete_tables,
            skip_update_tables=self.skip_update_tables,
            alias=alias,
            auto_create_table=auto_create_table
        ):

            if table and table not in schema_tables.get(schema):
                if event["action"] == "create":
                    schema_tables.get(schema).append(table)
                else:
                    continue
            event["values"] = self.deep_decode_dict(event["values"])
            broker.send(msg=event, schema=schema)
            self.pos_handler.set_log_pos_slave(file, pos)
            logger.debug(f"send to queue success: key:{schema},event:{event}")
            logger.debug(f"success set binlog pos:{file}:{pos}")
            self.after_send(schema, table)

    def _binlog_reading(
        self,
        only_tables,
        only_schemas,
        log_file,
        log_pos,
        server_id,
        skip_dmls,
        skip_delete_tables,
        skip_update_tables,
        alias,
        auto_create_table
    ) -> Generator:
        stream = BinLogStreamReader(
            connection_settings=dict(
                host=self.host, port=self.port, user=self.user, passwd=self.password,
            ),
            resume_stream=True,
            blocking=True,
            server_id=server_id,
            only_tables=only_tables,
            only_schemas=only_schemas,
            only_events=self.only_events,
            log_file=log_file,
            log_pos=log_pos,
            fail_on_table_metadata_unavailable=True,
            slave_heartbeat=10,
        )
        while True:
            for schema, table, event, stream.log_file, stream.log_pos in self.read_from_stream(stream, alias, auto_create_table):
                yield schema, table, event, stream.log_file, stream.log_pos
                if event["action"] == "create":
                    only_tables.append(table)
                    stream = BinLogStreamReader(
                        connection_settings=dict(
                            host=self.host, port=self.port, user=self.user, passwd=self.password,
                        ),
                        resume_stream=True,
                        blocking=True,
                        server_id=server_id,
                        only_tables=only_tables,
                        only_schemas=only_schemas,
                        only_events=self.only_events,
                        log_file=stream.log_file,
                        log_pos=stream.log_pos,
                        fail_on_table_metadata_unavailable=True,
                        slave_heartbeat=10,
                    )
                break

    def read_from_stream(
        self,
        stream,
        alias,
        auto_create_table
    ) -> Generator:
        for binlog_event in stream:
            if isinstance(binlog_event, QueryEvent):
                schema = binlog_event.schema.decode()
                if len(schema) == 0:
                    schema = self.default_schema
                query = binlog_event.query.lower()
                if "alter" in query:
                    table, convent_sql = SqlConvert.to_clickhouse(
                        schema, query, Settings.cluster_name()
                    )
                    if not convent_sql:
                        continue
                    event = {
                        "table": table,
                        "schema": schema,
                        "action": "query",
                        "values": {"query": convent_sql},
                        "event_unixtime": int(time.time() * 10 ** 6),
                        "action_seq": 0,
                    }
                    yield schema, table, event, stream.log_file, stream.log_pos
                elif "create" in query and auto_create_table:
                    table_name = SqlConvert.create_to_clickhouse(schema, query)
                    table = table_name
                    if not table_name:
                        continue
                    pk = self.get_primary_key(schema, table_name)
                    if not pk:
                        logger.warning(f"No pk found in {schema}.{table_name}, skip")
                        continue
                    elif isinstance(pk, tuple):
                        pk = f"({','.join(pk)})"
                    writer = get_writer(Settings.default_engine())
                    if not writer.check_table_exists(schema, table_name):
                        partition_by = Settings.default_partition_by()
                        engine_settings = Settings.default_engine_settings()
                        sign_column = Settings.default_sign_column()
                        version_column = Settings.default_version_column()
                        query = writer.get_table_create_sql(
                            reader=self,
                            schema=schema,
                            table=table_name,
                            pk=pk,
                            partition_by=partition_by,
                            engine_settings=engine_settings,
                            sign_column=sign_column,
                            version_column=version_column,
                        )
                        event = {
                            "table": table_name,
                            "schema": schema,
                            "action": "create",
                            "values": {"query": query},
                            "event_unixtime": int(time.time() * 10 ** 6),
                            "action_seq": 0,
                            "partition_by": partition_by,
                            "engine_settings": engine_settings,
                            "sign_column": sign_column,
                            "version_column": version_column,
                        }
                        self.source_db = Settings.get_source_db(alias)
                        yield schema, table, event, stream.log_file, stream.log_pos
                else:
                    continue
            else:
                schema = binlog_event.schema
                if len(schema) == 0:
                    schema = self.default_schema
                table = binlog_event.table
                skip_dml_table_name = f"{schema}.{table}"
                for row in binlog_event.rows:
                    if isinstance(binlog_event, WriteRowsEvent):
                        event = {
                            "table": table,
                            "schema": schema,
                            "action": "insert",
                            "values": row["values"],
                            "event_unixtime": int(time.time() * 10 ** 6),
                            "action_seq": 2,
                        }

                    elif isinstance(binlog_event, UpdateRowsEvent):
                        if "update" in skip_dmls or skip_dml_table_name in skip_update_tables:
                            continue
                        delete_event = {
                            "table": table,
                            "schema": schema,
                            "action": "delete",
                            "values": row["before_values"],
                            "event_unixtime": int(time.time() * 10 ** 6),
                            "action_seq": 1,
                        }
                        yield binlog_event.schema, binlog_event.table, delete_event, stream.log_file, stream.log_pos
                        event = {
                            "table": table,
                            "schema": schema,
                            "action": "insert",
                            "values": row["after_values"],
                            "event_unixtime": int(time.time() * 10 ** 6),
                            "action_seq": 2,
                        }

                    elif isinstance(binlog_event, DeleteRowsEvent):
                        if "delete" in skip_dmls or skip_dml_table_name in skip_delete_tables:
                            continue
                        event = {
                            "table": table,
                            "schema": schema,
                            "action": "delete",
                            "values": row["values"],
                            "event_unixtime": int(time.time() * 10 ** 6),
                            "action_seq": 1,
                        }
                    else:
                        return
                    yield binlog_event.schema, binlog_event.table, event, stream.log_file, stream.log_pos

    def new_tables_and_pks(self, schema: str, table: str, tables_dict: dict, tables_pk: dict):
        new_table_dict = {
            'table': table,
            'skip_decimal': False,
            'auto_full_etl': True,
            'clickhouse_engine': 'ReplacingMergeTree',
            'partition_by': None,
            'engine_settings': None,
            'sign_column': 'sign',
            'version_column': None
        }
        tables_dict[table] = new_table_dict
        new_table_pk = self.get_primary_key(schema, table)
        tables_pk[table] = new_table_pk
        return tables_dict, tables_pk
