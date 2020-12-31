'''
Author: peer
Date: 2020-10-27 18:20:15
LastEditTime: 2020-12-25 13:36:47
Description: file content
'''
from synchp.common import cluster_sql
from synchp.enums import ClickHouseEngine
from synchp.reader import Reader
from synchp.writer.collapsing_merge_tree import ClickHouseCollapsingMergeTree


class ClickHouseVersionedCollapsingMergeTree(ClickHouseCollapsingMergeTree):
    engine = ClickHouseEngine.versioned_collapsing_merge_tree

    def get_table_create_sql(
        self,
        reader: Reader,
        schema: str,
        table: str,
        pk,
        partition_by: str = None,
        engine_settings: str = None,
        sign_column: str = None,
        version_column: str = None,
    ):
        super(ClickHouseVersionedCollapsingMergeTree, self).get_table_create_sql(
            reader, schema, table, pk, partition_by, engine_settings, sign_column=sign_column
        )
        select_sql = reader.get_source_select_sql(schema, table, sign_column)
        partition_by_str = ""
        engine_settings_str = ""
        if partition_by:
            partition_by_str = f" PARTITION BY {partition_by} "
        if engine_settings:
            engine_settings_str = f" SETTINGS {engine_settings} "
        return f"CREATE TABLE {schema}.{table}{cluster_sql(self.cluster_name)} ENGINE = {self.engine}({sign_column},{version_column}) {partition_by_str} ORDER BY {pk} {engine_settings_str} AS {select_sql} limit 0"

    def get_full_insert_sql(self, reader: Reader, schema: str, table: str, sign_column: str = None):
        return f"insert into {schema}.{table} {reader.get_source_select_sql(schema, table, sign_column)}"
