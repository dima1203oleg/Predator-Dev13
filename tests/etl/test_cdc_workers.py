from types import SimpleNamespace

import etl.cdc_workers as cw


def test_handle_customs_data_event_triggers_opensearch(monkeypatch):
    called = {}

    def fake_delay(index_name, documents):
        called['index'] = index_name
        called['docs'] = documents

    # Patch the celery task's delay method with a sync recorder
    monkeypatch.setattr(cw.sync_to_opensearch, 'delay', lambda *a, **k: fake_delay(*a, **k))

    event = {
        'aggregate_type': 'customs_data',
        'event_type': 'customs_data.created',
        'payload': {
            'id': '1',
            'hs_code': '1234',
            'company_name': 'ACME',
            'edrpou': '12345678',
            'amount': 100.0,
            'date': '2025-11-12',
            'country_code': 'UKR',
            'customs_office': 'KBP',
            'created_at': '2025-11-12T00:00:00Z',
        },
    }

    cw.handle_customs_data_event(event)

    assert called.get('index') == 'customs_data'
    docs = called.get('docs')
    assert isinstance(docs, list)
    assert docs[0]['id'] == '1'
    assert docs[0]['company_name'] == 'ACME'


class FakeCursor:
    def __init__(self, pending=0):
        self._pending = pending

    def execute(self, query, *args, **kwargs):
        pass

    def fetchone(self):
        return (self._pending,)


class FakeConn:
    def __init__(self, pending=0):
        self._pending = pending

    def cursor(self):
        return FakeCursor(self._pending)

    def close(self):
        pass


def test_health_check_all_healthy(monkeypatch):
    # Patch pg
    monkeypatch.setattr(cw, 'get_pg_connection', lambda: FakeConn(pending=0))

    # Patch opensearch
    class FakeOS:
        def cluster(self):
            return SimpleNamespace(health=lambda: {'status': 'green'})

        def cluster_health(self):
            return {'status': 'green'}

    monkeypatch.setattr(cw, 'get_opensearch_client', lambda: SimpleNamespace(cluster=SimpleNamespace(health=lambda: {'status': 'green'})))

    # Patch qdrant
    monkeypatch.setattr(cw, 'get_qdrant_client', lambda: SimpleNamespace(get_collections=lambda: SimpleNamespace(collections=[1, 2])))

    # Patch redis
    monkeypatch.setattr(cw, 'get_redis_client', lambda: SimpleNamespace(ping=lambda: True))

    res = cw.health_check()
    assert res['overall'] == 'healthy'
    assert 'postgres' in res
    assert 'opensearch' in res
    assert 'qdrant' in res
    assert 'redis' in res


def test_health_check_degraded_when_pg_fails(monkeypatch):
    # pg raises
    monkeypatch.setattr(cw, 'get_pg_connection', lambda: (_ for _ in ()).throw(Exception('conn fail')))

    # other services healthy
    monkeypatch.setattr(cw, 'get_opensearch_client', lambda: SimpleNamespace(cluster=SimpleNamespace(health=lambda: {'status': 'green'})))
    monkeypatch.setattr(cw, 'get_qdrant_client', lambda: SimpleNamespace(get_collections=lambda: SimpleNamespace(collections=[1])))
    monkeypatch.setattr(cw, 'get_redis_client', lambda: SimpleNamespace(ping=lambda: True))

    res = cw.health_check()
    assert res['overall'] in ('degraded', 'error')
    assert res['postgres']['status'] == 'unhealthy' or 'error' in res['postgres']
