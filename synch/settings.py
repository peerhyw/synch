import functools
from typing import Dict, List

import yaml

import logging
logger = logging.getLogger("synch.reader.mysql")


class Settings:
    _config: Dict
    _file_path: str

    @classmethod
    def init(cls, file_path: str):
        cls._file_path = file_path
        with open(file_path, "r") as f:
            cls._config = yaml.safe_load(f)

    @classmethod
    def debug(cls):
        return cls.get("core", "debug")

    @classmethod
    def monitoring(cls):
        return cls.get("core", "monitoring")

    @classmethod
    def insert_interval(cls):
        return cls.get("core", "insert_interval")

    @classmethod
    def insert_num(cls):
        return cls.get("core", "insert_num")

    @classmethod
    @functools.lru_cache()
    def get_source_db(cls, alias: str) -> Dict:
        return next(filter(lambda x: x.get("alias") == alias, cls.get("source_dbs")))

    @classmethod
    @functools.lru_cache()
    def is_cluster(cls):
        return True if cls.get("clickhouse").get("cluster_name") else False

    @classmethod
    @functools.lru_cache()
    def cluster_name(cls):
        return cls.get("clickhouse").get("cluster_name")

    @classmethod
    @functools.lru_cache()
    def get_source_db_database(cls, alias: str, database: str) -> Dict:
        source_db = cls.get_source_db(alias)
        return next(filter(lambda x: x.get("database") == database, source_db.get("databases")))

    @classmethod
    @functools.lru_cache()
    def get_source_db_database_tables_name(cls, alias: str, database: str) -> List[str]:
        return list(
            map(lambda x: x.get("table"), cls.get_source_db_database_tables(alias, database))
        )

    @classmethod
    @functools.lru_cache()
    def get_source_db_database_tables(cls, alias: str, database: str) -> List[Dict]:
        """
        get table list
        """
        source_db_database = cls.get_source_db_database(alias, database)
        return source_db_database.get("tables")

    @classmethod
    @functools.lru_cache()
    def get_source_db_database_tables_by_tables_name(
        cls, alias: str, database: str, tables: List[str]
    ):
        source_db_database_tables = cls.get_source_db_database_tables(alias, database)
        return list(filter(lambda x: x.get("table") in tables, source_db_database_tables))

    @classmethod
    @functools.lru_cache()
    def get_source_db_database_tables_dict(cls, alias: str, database: str) -> Dict:
        ret = {}
        for table in cls.get_source_db_database_tables(alias, database):
            ret[table.get("table")] = table
        return ret

    @classmethod
    @functools.lru_cache()
    def get_source_db_database_table(cls, alias: str, database: str, table: str) -> Dict:
        """
        get table dict
        """
        return next(
            filter(
                lambda x: x.get("table") == table,
                cls.get_source_db_database_tables(alias, database),
            )
        )

    @classmethod
    @functools.lru_cache()
    def default_engine(cls):
        return cls.get("clickhouse").get("default_engine")

    @classmethod
    @functools.lru_cache()
    def default_sign_column(cls):
        return cls.get("clickhouse").get("default_sign_column")

    @classmethod
    @functools.lru_cache()
    def default_version_column(cls):
        return cls.get("clickhouse").get("default_version_column")

    @classmethod
    @functools.lru_cache()
    def default_partition_by(cls):
        return cls.get("clickhouse").get("default_partition_by")

    @classmethod
    @functools.lru_cache()
    def default_engine_settings(cls):
        return cls.get("clickhouse").get("default_engine_settings")

    @classmethod
    @functools.lru_cache()
    def default_skip_decimal(cls):
        return cls.get("clickhouse").get("default_skip_decimal")

    @classmethod
    @functools.lru_cache()
    def get(cls, *args):
        """
        get config item
        """
        c = cls._config
        for arg in args:
            c = c.get(arg)
        return c

    @classmethod
    @functools.lru_cache()
    def set_table(cls, alias: str, schema: str, table_name: str):
        flag = f'#table_flag_{alias}_{schema}...'
        data = ''
        logger.debug(f"{flag} {cls._file_path}")
        with open(cls._file_path, 'r+') as f:
            for line in f.readlines():
                if(line.find(flag) != -1):
                    indent = '\t\t\t\t\t'
                    line = indent + '- table: %s' % table_name + '\n'
                    line += indent + '\t# optional, default false, if your table has decimal column with nullable, there is a bug with full data etl will, see https://github.com/ClickHouse/ClickHouse/issues/7690.\n'
                    line += indent + '\tskip_decimal: false' + '\n'
                    line += indent + '\t# optional, default true\n'
                    line += indent + '\tauto_full_etl: true' + '\n'
                    line += indent + '\t# optional, default ReplacingMergeTree\n'
                    line += indent + '\tclickhouse_engine: ReplacingMergeTree' + '\n'
                    line += indent + '\t# optional\n'
                    line += indent + '\tpartition_by:' + '\n'
                    line += indent + '\t# optional\n'
                    line += indent + '\tengine_settings:' + '\n'
                    line += indent + '\t# optional\n'
                    line += indent + '\tsign_column: sign' + '\n'
                    line += indent + '\t# optional\n'
                    line += indent + '\tversion_column:' + '\n'
                    line += indent + flag + '\n'
                data += line

        with open(cls._file_path, 'r+') as f:
            f.writelines(data)
