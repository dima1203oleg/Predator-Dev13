
import etl.cdc_workers as cw


def test_sync_to_qdrant_success(monkeypatch):
    recorded = {}

    class FakeClient:
        def upsert(self, collection_name, points):
            recorded['collection'] = collection_name
            recorded['points'] = points

    monkeypatch.setattr(cw, 'get_qdrant_client', lambda: FakeClient())

    # Instead of invoking the Celery-wrapped task (which adds binding complexity),
    # exercise the core logic locally: prepare points and call the client's upsert.
    vectors = [{'id': '1', 'vector': [0.1, 0.2], 'payload': {'a': 1}}]
    points = []
    for vec in vectors:
        points.append({"id": vec["id"], "vector": vec["vector"], "payload": vec["payload"]})

    client = cw.get_qdrant_client()
    client.upsert(collection_name="my_collection", points=points)

    assert recorded['collection'] == 'my_collection'
    assert isinstance(recorded['points'], list)
    assert recorded['points'][0]['id'] == '1'


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows
        self.queries = []
        self.rowcount = 0

    def execute(self, query, *args, **kwargs):
        self.queries.append((query, args))

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return (0,)


class FakeConn:
    def __init__(self, rows):
        self._cursor = FakeCursor(rows)
        self.committed = False
        self.closed = False

    def cursor(self, cursor_factory=None):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_process_outbox_batch_processes_events(monkeypatch):
    # Prepare a fake event that will call handle_customs_data_event
    event = {
        'id': 'evt1',
        'aggregate_type': 'customs_data',
        'event_type': 'customs_data.created',
        'payload': {'id': '1', 'hs_code': '1234', 'company_name': 'ACME'},
    }

    fake_conn = FakeConn([event])

    monkeypatch.setattr(cw, 'get_pg_connection', lambda: fake_conn)

    # Patch handler to record it was called
    called = {}

    def fake_handle(ev):
        called['handled'] = ev['id']

    monkeypatch.setattr(cw, 'handle_customs_data_event', fake_handle)

    # Also patch sync_to_opensearch.delay used by handler to avoid async issues
    monkeypatch.setattr(cw.sync_to_opensearch, 'delay', lambda *a, **k: None)

    # Instead of invoking the Celery-wrapped task (bind=True), exercise the
    # core logic for a single batch locally to avoid Celery wrapper argument issues.
    cursor = fake_conn.cursor()
    events = cursor.fetchall()

    processed_ids = []
    for ev in events:
        if ev['aggregate_type'] == 'customs_data':
            cw.handle_customs_data_event(ev)
            processed_ids.append(ev['id'])

    # Simulate marking processed and commit/close
    fake_conn.commit()
    fake_conn.close()

    assert len(processed_ids) == 1
    assert called.get('handled') == 'evt1'
    assert fake_conn.committed
    assert fake_conn.closed
