import functools
from typing import Dict, List

import yaml

import logging
logger = logging.getLogger("synch.reader.mysql")


class Settings:
    _config: Dict
    _file_path: str
    _update_config: bool

    @classmethod
    def init(cls, file_path: str):
        cls._file_path = file_path
        with open(file_path, "r") as f:
            cls._config = yaml.safe_load(f)
        cls._update_config = False

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
        if cls._update_config == True:
            c = cls.reload_yaml()
        else:
            c = cls._config
        for arg in args:
            c = c.get(arg)
        return c

    @classmethod
    @functools.lru_cache()
    def reload_yaml(cls):
        with open(cls._file_path, "r") as f:
            c = cls._config = yaml.safe_load(f)
        return c

    @classmethod
    @functools.lru_cache()
    def set_table(cls, alias: str, schema: str, table_name: str):
        flag = f'#table_flag_{alias}_{schema}...'
        indent = '  '  # 2 spaces/indent
        indent_t = indent * 5
        indent_d = indent * 6
        lines = '- table: %s' % table_name + '\n'
        lines += indent_d + '# optional, default false, if your table has decimal column with nullable, there is a bug with full data etl will, see https://github.com/ClickHouse/ClickHouse/issues/7690.\n'
        lines += indent_d + 'skip_decimal: false' + '\n'
        lines += indent_d + '# optional, default true\n'
        lines += indent_d + 'auto_full_etl: true' + '\n'
        lines += indent_d + '# optional, default ReplacingMergeTree\n'
        lines += indent_d + 'clickhouse_engine: ReplacingMergeTree' + '\n'
        lines += indent_d + '# optional\n'
        lines += indent_d + 'partition_by:' + '\n'
        lines += indent_d + '# optional\n'
        lines += indent_d + 'engine_settings:' + '\n'
        lines += indent_d + '# optional\n'
        lines += indent_d + 'sign_column: sign' + '\n'
        lines += indent_d + '# optional\n'
        lines += indent_d + 'version_column:' + '\n' + indent_t

        file = open(cls._file_path, "r")
        content = file.read()
        pos = content.find(flag)
        if pos != -1:
            content = content[:pos] + lines + content[pos:]
            file = open(cls._file_path, "w")
            file.write(content)
            file.close()
            cls._update_config = True
