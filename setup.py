'''
Author: peer
Date: 2020-11-06 13:24:02
LastEditTime: 2020-12-25 13:14:25
Description: file content
'''
# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
    ['synchp', 'synchp.broker', 'synchp.reader', 'synchp.replication', 'synchp.writer']

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
    {'console_scripts': ['synch-dev = synchp.cli:cli']}

setup_kwargs = {
    'name': 'synch-dev',
    'version': '0.7.1',
    'description': 'Sync data from other DB to ClickHouse, current support postgres and mysql, and support full and increment ETL.',
    'long_description': 'Sync data from other DB to ClickHouse, current support postgres and mysql, and support full and increment ETL.',
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
