'''
Author: peer
Date: 2020-11-06 13:24:02
LastEditTime: 2020-11-06 14:08:53
Description: file content
'''
# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
    ['synch', 'synch.broker', 'synch.reader', 'synch.replication', 'synch.writer']

package_data = \
    {'': ['*']}

install_requires = \
    ['click',
     'clickhouse-driver',
     'kafka-python',
     'mysql-replication',
     'mysqlclient',
     'mysqlparse',
     'psycopg2',
     'python-dateutil',
     'pyyaml',
     'ratelimitingfilter',
     'redis',
     'sentry-sdk']

entry_points = \
    {'console_scripts': ['synch-dev = synch.cli:cli']}

setup_kwargs = {
    'name': 'synch-dev',
    'version': '0.7.1',
    'description': 'Sync data from other DB to ClickHouse, current support postgres and mysql, and support full and increment ETL.',
    'long_description': '# Synch\n\n![pypi](https://img.shields.io/pypi/v/synch.svg?style=flat)\n![docker](https://img.shields.io/docker/cloud/build/long2ice/synch)\n![license](https://img.shields.io/github/license/long2ice/synch)\n![workflows](https://github.com/long2ice/synch/workflows/pypi/badge.svg)\n![workflows](https://github.com/long2ice/synch/workflows/ci/badge.svg)\n\n[中文文档](https://github.com/long2ice/synch/blob/dev/README-zh.md)\n\n## Introduction\n\nSync data from other DB to ClickHouse, current support postgres and mysql, and support full and increment ETL.\n\n![synch](https://github.com/long2ice/synch/raw/dev/images/synch.png)\n\n## Features\n\n- Full data etl and real time increment etl.\n- Support DDL and DML sync, current support `add column` and `drop column` and `change column` of DDL, and full support of DML also.\n- Email error report.\n- Support kafka and redis as broker.\n- Multiple source db sync to ClickHouse at the same time。\n- Support ClickHouse `MergeTree`,`CollapsingMergeTree`,`VersionedCollapsingMergeTree`,`ReplacingMergeTree`.\n- Support ClickHouse cluster.\n\n## Requirements\n\n- Python >= 3.7\n- [redis](https://redis.io), cache mysql binlog file and position and as broker, support redis cluster also.\n- [kafka](https://kafka.apache.org), need if you use kafka as broker.\n- [clickhouse-jdbc-bridge](https://github.com/long2ice/clickhouse-jdbc-bridge), need if you use postgres and set `auto_full_etl = true`, or exec `synch etl` command.\n- [sentry](https://github.com/getsentry/sentry), error reporting, worked if set `dsn` in config.\n\n## Install\n\n```shell\n> pip install synch\n```\n\n## Usage\n\n### Config file `synch.yaml`\n\nsynch will read default config from `./synch.yaml`, or you can use `synch -c` specify config file.\n\nSee full example config in [`synch.yaml`](https://github.com/long2ice/synch/blob/dev/synch.yaml).\n\n### Full data etl\n\nMaybe you need make full data etl before continuous sync data from MySQL to ClickHouse or redo data etl with `--renew`.\n\n```shell\n> synch --alias mysql_db etl -h\n\nUsage: synch etl [OPTIONS]\n\n  Make etl from source table to ClickHouse.\n\nOptions:\n  --schema TEXT     Schema to full etl.\n  --renew           Etl after try to drop the target tables.\n  -t, --table TEXT  Tables to full etl.\n  -h, --help        Show this message and exit.\n```\n\nFull etl from table `test.test`:\n\n```shell\n> synch etl --schema test --table test --table test2\n```\n\n### Produce\n\nListen all MySQL binlog and produce to broker.\n\n```shell\n> synch --alias mysql_db produce\n```\n\n### Consume\n\nConsume message from broker and insert to ClickHouse,and you can skip error rows with `--skip-error`. And synch will do full etl at first when set `auto_full_etl = true` in config.\n\n```shell\n> synch --alias mysql_db consume -h\n\nUsage: synch consume [OPTIONS]\n\n  Consume from broker and insert into ClickHouse.\n\nOptions:\n  --schema TEXT       Schema to consume.  [required]\n  --skip-error        Skip error rows.\n  --last-msg-id TEXT  Redis stream last msg id or kafka msg offset, depend on\n                      broker_type in config.\n\n  -h, --help          Show this message and exit.\n```\n\nConsume schema `test` and insert into `ClickHouse`:\n\n```shell\n> synch --alias mysql_db consume --schema test\n```\n\n### Monitor\n\nSet `true` to `core.monitoring`, which will create database `synch` in `ClickHouse` automatically and insert monitoring data.\n\nTable struct:\n\n```sql\ncreate table if not exists synch.log\n(\n    alias      String,\n    schema     String,\n    table      String,\n    num        int,\n    type       int, -- 1:producer, 2:consumer\n    created_at DateTime\n)\n    engine = MergeTree partition by toYYYYMM(created_at) order by created_at;\n```\n\n### ClickHouse Table Engine\n\nNow synch support `MergeTree`, `CollapsingMergeTree`, `VersionedCollapsingMergeTree`, `ReplacingMergeTree`.\n\n- `MergeTree`, default common choices.\n- `CollapsingMergeTree`, see detail in [CollapsingMergeTree](https://clickhouse.tech/docs/zh/engines/table-engines/mergetree-family/collapsingmergetree/).\n- `VersionedCollapsingMergeTree`, see detail in [VersionedCollapsingMergeTree](https://clickhouse.tech/docs/zh/engines/table-engines/mergetree-family/versionedcollapsingmergetree/).\n- `ReplacingMergeTree`, see detail in [ReplacingMergeTree](https://clickhouse.tech/docs/zh/engines/table-engines/mergetree-family/replacingmergetree/).\n\n## Use docker-compose(recommended)\n\n<details>\n<summary>Redis Broker, lightweight and for low concurrency</summary>\n\n```yaml\nversion: "3"\nservices:\n  producer:\n    depends_on:\n      - redis\n    image: long2ice/synch\n    command: synch --alias mysql_db produce\n    volumes:\n      - ./synch.yaml:/synch/synch.yaml\n  # one service consume on schema\n  consumer.test:\n    depends_on:\n      - redis\n    image: long2ice/synch\n    command: synch --alias mysql_db consume --schema test\n    volumes:\n      - ./synch.yaml:/synch/synch.yaml\n  redis:\n    hostname: redis\n    image: redis:latest\n    volumes:\n      - redis\nvolumes:\n  redis:\n```\n\n</details>\n\n<details>\n<summary>Kafka Broker, for high concurrency</summary>\n\n```yaml\nversion: "3"\nservices:\n  zookeeper:\n    image: bitnami/zookeeper:3\n    hostname: zookeeper\n    environment:\n      - ALLOW_ANONYMOUS_LOGIN=yes\n    volumes:\n      - zookeeper:/bitnami\n  kafka:\n    image: bitnami/kafka:2\n    hostname: kafka\n    environment:\n      - KAFKA_CFG_ZOOKEEPER_CONNECT=zookeeper:2181\n      - ALLOW_PLAINTEXT_LISTENER=yes\n      - JMX_PORT=23456\n      - KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE=true\n      - KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:9092\n    depends_on:\n      - zookeeper\n    volumes:\n      - kafka:/bitnami\n  kafka-manager:\n    image: hlebalbau/kafka-manager\n    ports:\n      - "9000:9000"\n    environment:\n      ZK_HOSTS: "zookeeper:2181"\n      KAFKA_MANAGER_AUTH_ENABLED: "false"\n    command: -Dpidfile.path=/dev/null\n  producer:\n    depends_on:\n      - redis\n      - kafka\n      - zookeeper\n    image: long2ice/synch\n    command: synch --alias mysql_db produce\n    volumes:\n      - ./synch.yaml:/synch/synch.yaml\n  # one service consume on schema\n  consumer.test:\n    depends_on:\n      - redis\n      - kafka\n      - zookeeper\n    image: long2ice/synch\n    command: synch --alias mysql_db consume --schema test\n    volumes:\n      - ./synch.yaml:/synch/synch.yaml\n  redis:\n    hostname: redis\n    image: redis:latest\n    volumes:\n      - redis:/data\nvolumes:\n  redis:\n  kafka:\n  zookeeper:\n```\n\n</details>\n\n## Important\n\n- You need always keep a primary key or unique key without null or composite primary key.\n- DDL sync not support postgres.\n- Postgres sync is not fully test, be careful use it in production.\n\n## Support this project\n\n| AliPay                                                                                | WeChatPay                                                                                | PayPal                                                           |\n| ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |\n| <img width="200" src="https://github.com/long2ice/synch/raw/dev/images/alipay.jpeg"/> | <img width="200" src="https://github.com/long2ice/synch/raw/dev/images/wechatpay.jpeg"/> | [PayPal](https://www.paypal.me/long2ice) to my account long2ice. |\n\n## ThanksTo\n\nPowerful Python IDE [Pycharm](https://www.jetbrains.com/pycharm/?from=synch) from [Jetbrains](https://www.jetbrains.com/?from=synch).\n\n![jetbrains](https://github.com/long2ice/synch/raw/dev/images/jetbrains.svg)\n\n## License\n\nThis project is licensed under the [Apache-2.0](https://github.com/long2ice/synch/blob/master/LICENSE) License.\n',
    'author': 'peer',
    'author_email': 'peerforcheer@foxmail.com',
    'maintainer': None,
    'maintainer_email': None,
    'url': 'https://github.com/peerhyw/synch',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'entry_points': entry_points,
    'python_requires': '>=3.7,<4.0',
}


setup(**setup_kwargs)
