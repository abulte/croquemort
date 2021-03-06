import json
from mock import ANY

import pytest
from nameko.runners import ServiceRunner
from nameko.standalone.events import event_dispatcher
from nameko.testing.utils import get_container
from nameko.testing.services import entrypoint_waiter, replace_dependencies

from croquemort.crawler import CrawlerService
from croquemort.http import HttpService


@pytest.yield_fixture
def runner_factory(container_config):
    all_runners = []

    def make_runner(*service_classes):
        runner = ServiceRunner(container_config)
        for service_cls in service_classes:
            runner.add_service(service_cls)
        all_runners.append(runner)
        return runner

    yield make_runner

    for r in all_runners:
        try:
            r.stop()
        except:
            pass


def test_retrieve_url(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.get_url = lambda url_hash: {'url': url_hash}
    runner.start()
    rv = web_session.get('/url', data=json.dumps({
        'url': 'http://example.org/test_retrieve_url'
    }))
    assert rv.json()['url'] == '9c01c218'
    assert 'group' not in rv.json()


def test_cache_report(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.set_cache.return_value = None
    storage.get_cache.return_value = None
    storage.expire_cache.return_value = None
    runner.start()

    rv = web_session.get('/')
    cache_duration = 60 * 60 * 2  # Equals 2 hours.
    default_key = 'cache-display_report-'
    assert rv.text.startswith('<!doctype html>')
    storage.get_cache.assert_called_once_with(default_key)
    storage.set_cache.assert_called_once_with(default_key, ANY)  # HTML.
    storage.expire_cache.assert_called_once_with(default_key, cache_duration)


def test_retrieve_url_with_group(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.get_url = lambda url_hash: {
        'url': url_hash,
        'group': 'datagouvfr'
    }
    runner.start()
    rv = web_session.get('/url', data=json.dumps({
        'url': 'http://example.org/test_retrieve_url_with_group'
    }))
    assert rv.json()['url'] == '462bd375'
    assert rv.json()['group'] == 'datagouvfr'


def test_retrieve_group(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.get_group = lambda group_hash: {
        'url': group_hash,
        'name': 'datagouvfr',
        'url_hash': 'url'
    }
    storage.get_url = lambda url_hash: {'url': url_hash}
    runner.start()
    rv = web_session.get('/group', data=json.dumps({
        'group': 'datagouvfr'
    }))
    result = rv.json()
    assert result['name'] == 'datagouvfr'
    assert 'url_hash' in result['urls'][0].values()


def test_retrieve_group_filtered(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.get_group = lambda group_hash: {
        'url': group_hash,
        'name': 'datagouvfr',
        'url_hash1': 'url1',
        'url_hash2': 'url1',
    }

    def get_url(url_hash):
        result = {'url': url_hash}
        if url_hash == 'url_hash1':
            result['metadata'] = 'meta'
        return result

    storage.get_url = get_url
    runner.start()
    rv = web_session.get('/group', data=json.dumps({
        'group': 'datagouvfr',
        'filter_metadata': 'meta'
    }))
    result = rv.json()
    assert result['name'] == 'datagouvfr'
    assert 'url_hash1' in result['urls'][0].values()
    assert 'url_hash2' not in result['urls'][0].values()


def test_retrieve_group_excluded(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.get_group = lambda group_hash: {
        'url': group_hash,
        'name': 'datagouvfr',
        'url_hash1': 'url1',
        'url_hash2': 'url1',
    }

    def get_url(url_hash):
        result = {'url': url_hash}
        if url_hash == 'url_hash1':
            result['metadata'] = 'meta'
        return result

    storage.get_url = get_url
    runner.start()
    rv = web_session.get('/group', data=json.dumps({
        'group': 'datagouvfr',
        'exclude_metadata': 'meta'
    }))
    result = rv.json()
    assert result['name'] == 'datagouvfr'
    assert 'url_hash1' not in result['urls'][0].values()
    assert 'url_hash2' in result['urls'][0].values()


def test_retrieve_group_excluded_empty(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    storage = replace_dependencies(http_container, 'storage')
    storage.get_group = lambda group_hash: {
        'url': group_hash,
        'name': 'datagouvfr',
        'url_hash1': 'url1',
        'url_hash2': 'url1',
    }

    def get_url(url_hash):
        result = {'url': url_hash}
        if url_hash == 'url_hash1':
            result['metadata'] = ''
        return result

    storage.get_url = get_url
    runner.start()
    rv = web_session.get('/group', data=json.dumps({
        'group': 'datagouvfr',
        'exclude_metadata': ''
    }))
    result = rv.json()
    assert result['name'] == 'datagouvfr'
    assert 'url_hash1' not in result['urls'][0].values()
    assert 'url_hash2' in result['urls'][0].values()


def test_checking_one(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    dispatch = replace_dependencies(http_container, 'dispatch')
    runner.start()
    rv = web_session.post('/check/one', data=json.dumps({
        'url': 'http://example.org/test_checking_one'
    }))
    assert rv.json()['url-hash'] == 'a55f9fb5'
    assert dispatch.call_count == 1


def test_checking_many(runner_factory, web_session):
    runner = runner_factory(HttpService)
    http_container = get_container(runner, HttpService)
    dispatch = replace_dependencies(http_container, 'dispatch')
    runner.start()
    rv = web_session.post('/check/many', data=json.dumps({
        'urls': [
            'http://example.org/test_checking_many',
            'http://example.com/test_checking_many'
        ],
        'group': 'datagouvfr'
    }))
    assert rv.json()['group-hash'] == 'efcf3897'
    assert dispatch.call_count == 2


def test_fetching(runner_factory, rpc_proxy_factory):
    runner = runner_factory(HttpService)
    http_server = rpc_proxy_factory('http_server')
    http_container = get_container(runner, HttpService)
    dispatch = replace_dependencies(http_container, 'dispatch')
    runner.start()
    http_server.fetch('http://example.org/test_fetching')
    assert dispatch.call_count == 1


def test_crawling_url(runner_factory, rpc_proxy_factory):
    runner = runner_factory(CrawlerService)
    crawler_container = get_container(runner, CrawlerService)
    storage = replace_dependencies(crawler_container, 'storage')
    runner.start()
    config = {'AMQP_URI': 'amqp://guest:guest@localhost:5672/nameko_test'}
    dispatch = event_dispatcher(config)
    with entrypoint_waiter(crawler_container, 'check_url'):
        dispatch('http_server', 'url_to_check',
                 ['http://example.org/test_crawling_url', None, None])
    assert storage.store_url.call_count == 1
    assert storage.store_group.call_count == 0
    assert storage.store_metadata.call_count == 1


def test_crawling_group(runner_factory, rpc_proxy_factory):
    runner = runner_factory(CrawlerService)
    crawler_container = get_container(runner, CrawlerService)
    storage = replace_dependencies(crawler_container, 'storage')
    runner.start()
    config = {'AMQP_URI': 'amqp://guest:guest@localhost:5672/nameko_test'}
    dispatch = event_dispatcher(config)
    with entrypoint_waiter(crawler_container, 'check_url'):
        dispatch('http_server', 'url_to_check',
                 ['http://example.org/test_crawling_group',
                  'datagouvfr', None])
    assert storage.store_url.call_count == 1
    assert storage.store_group.call_count == 1
    assert storage.store_metadata.call_count == 1
