"""
Tests for the rq_exporter.utils module.

"""

import unittest
from unittest.mock import patch, mock_open, Mock

from redis.exceptions import RedisError

from rq_exporter import config
from rq_exporter.utils import get_redis_connection, get_workers_stats


class GetRedisConnectionTestCase(unittest.TestCase):
    """Tests for the `get_redis_connection` function."""

    @patch.multiple(
        config,
        REDIS_URL = 'redis://',
        REDIS_HOST = 'redis_host',
        REDIS_PORT = '6363',
        REDIS_DB = '1',
        REDIS_AUTH = '123456',
        REDIS_AUTH_FILE = '/run/secrets/redis_pass'
    )
    @patch('builtins.open', mock_open())
    def test_creating_redis_connection_from_url(self):
        """When `config.REDIS_URL` is set connection must be created with `Redis.from_url`."""
        with patch('rq_exporter.utils.Redis') as Redis:
            connection = get_redis_connection()

            Redis.from_url.assert_called_with('redis://')

            open.assert_not_called()

            Redis.assert_not_called()

            self.assertEqual(connection, Redis.from_url.return_value)

    @patch.multiple(
        config,
        REDIS_URL = None,
        REDIS_HOST = 'redis_host',
        REDIS_PORT = '6363',
        REDIS_DB = '1',
        REDIS_AUTH = None,
        REDIS_AUTH_FILE = None
    )
    @patch('builtins.open', mock_open())
    def test_creating_redis_connection_without_url(self):
        """When `config.REDIS_URL` is not set the connection must be created from the other options."""
        with patch('rq_exporter.utils.Redis') as Redis:
            connection = get_redis_connection()

            Redis.from_url.assert_not_called()

            open.assert_not_called()

            Redis.assert_called_with(
                host = 'redis_host',
                port = '6363',
                db = '1',
                password = None
            )

            self.assertEqual(connection, Redis.return_value)

    @patch.multiple(
        config,
        REDIS_URL = None,
        REDIS_HOST = 'redis_host',
        REDIS_PORT = '6379',
        REDIS_DB = '0',
        REDIS_AUTH = '123456',
        REDIS_AUTH_FILE = None
    )
    @patch('builtins.open', mock_open())
    def test_creating_redis_connection_with_password(self):
        """The option `config.REDIS_AUTH` must be used if `config.REDIS_AUTH_FILE` is not set."""
        with patch('rq_exporter.utils.Redis') as Redis:
            connection = get_redis_connection()

            Redis.from_url.assert_not_called()

            open.assert_not_called()

            Redis.assert_called_with(
                host = 'redis_host',
                port = '6379',
                db = '0',
                password = '123456'
            )

            self.assertEqual(connection, Redis.return_value)

    @patch.multiple(
        config,
        REDIS_URL = None,
        REDIS_HOST = 'redis_host',
        REDIS_PORT = '6379',
        REDIS_DB = '0',
        REDIS_AUTH = '123456',
        REDIS_AUTH_FILE = '/path/to/redis_pass'
    )
    @patch('builtins.open', mock_open(read_data=' FILEPASS \n'))
    def test_creating_redis_connection_with_password_from_file(self):
        """The option `config.REDIS_AUTH_FILE` must be used if set."""
        with patch('rq_exporter.utils.Redis') as Redis:
            connection = get_redis_connection()

            Redis.from_url.assert_not_called()

            open.assert_called_with('/path/to/redis_pass', 'r')

            Redis.assert_called_with(
                host = 'redis_host',
                port = '6379',
                db = '0',
                password = 'FILEPASS'
            )

            self.assertEqual(connection, Redis.return_value)

    @patch.multiple(
        config,
        REDIS_URL = None,
        REDIS_HOST = 'redis_host',
        REDIS_PORT = '6379',
        REDIS_DB = '0',
        REDIS_AUTH = '123456',
        REDIS_AUTH_FILE = '/path/to/redis_pass'
    )
    @patch('builtins.open', mock_open())
    def test_creating_redis_connection_open_file_raises_IOError(self):
        """An `IOError` exception must be raised if there was error while opening the password file."""
        open.side_effect = IOError('Error opening the file')

        with patch('rq_exporter.utils.Redis') as Redis:

            with self.assertRaises(IOError):
                get_redis_connection()

            Redis.from_url.assert_not_called()

            open.assert_called_with('/path/to/redis_pass', 'r')

            Redis.assert_not_called()


class GetWorkersStatsTestCase(unittest.TestCase):
    """Tests for the `get_workers_stats` function."""

    @patch('rq_exporter.utils.Worker')
    def test_on_redis_errors_raises_RedisError(self, Worker):
        """On Redis connection errors, exceptions subclasses of `RedisError` will be raised."""
        Worker.all.side_effect = RedisError('Connection error')

        connection = Mock()

        with self.assertRaises(RedisError):

            get_workers_stats(connection)

        Worker.all.assert_called_with(connection=connection)

    @patch('rq_exporter.utils.Worker')
    def test_returns_empty_list_without_workers(self, Worker):
        """Without any available workers an empty list must be returned."""
        Worker.all.return_value = []

        connection = Mock()

        workers = get_workers_stats(connection)

        Worker.all.assert_called_with(connection=connection)

        self.assertEqual(workers, [])

    @patch('rq_exporter.utils.Worker')
    def test_returns_worker_stats(self, Worker):
        """When there are workers, a list of worker info dicts must be returned."""
        q_default = Mock()
        q_default.configure_mock(name='default')

        q_high = Mock()
        q_high.configure_mock(name='high')

        q_low = Mock()
        q_low.configure_mock(name='low')

        worker_one = Mock()
        worker_one_attrs = {
            'name': 'worker_one',
            'queues': [q_default],
            'get_state.return_value': 'idle'
        }
        worker_one.configure_mock(**worker_one_attrs)

        worker_two = Mock()
        worker_two_attrs = {
            'name': 'worker_two',
            'queues': [q_high, q_default, q_low],
            'get_state.return_value': 'busy'
        }
        worker_two.configure_mock(**worker_two_attrs)


        Worker.all.return_value = [worker_one, worker_two]

        connection = Mock()

        workers = get_workers_stats(connection)

        Worker.all.assert_called_with(connection=connection)

        self.assertEqual(
            workers,
            [
                {
                    'name': 'worker_one',
                    'queues': ['default'],
                    'state': 'idle'
                },
                {
                    'name': 'worker_two',
                    'queues': ['high', 'default', 'low'],
                    'state': 'busy'
                }
            ]
        )
