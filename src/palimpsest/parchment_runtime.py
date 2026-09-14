"""Atomic exact W composition, without a model job or Knowledge changes."""

from hashlib import sha256
from importlib.resources import files
import json

from psycopg.types.json import Jsonb

from . import parchment
from .canonical_store import connection
from .data import request_id
from .errors import PalimpsestError
from .i2k import digest
from .knowledge import _text
from .wisdom_runtime import WisdomRuntime


class ParchmentRuntime:
    def __init__(self, dsn):
        self.dsn = dsn

    @staticmethod
    def _parchment(conn, identifier):
        row = conn.execute('SELECT snapshot,snapshot_sha256 FROM canonical_store.parchments WHERE parchment_id=%s',
                           (request_id(identifier),)).fetchone()
        if row is None:
            raise PalimpsestError('parchment_not_found', 'Parchment가 없습니다.', 2)
        value = parchment.check_snapshot(row['snapshot'])
        if value['snapshot_sha256'] != row['snapshot_sha256']:
            parchment._fail('parchment_snapshot_changed')
        return value

    def compose(self, identifier, *, title, wisdom_ids, actor):
        identifier = request_id(identifier)
        _text(title, code='invalid_parchment_title')
        _text(actor, code='invalid_parchment_actor')
        if not isinstance(wisdom_ids, (list, tuple)) or not wisdom_ids:
            parchment._fail('parchment_wisdom_required')
        refs = [request_id(value) for value in wisdom_ids]
        if len(set(refs)) != len(refs):
            parchment._fail('duplicate_parchment_wisdom')
        request = {'title': title, 'wisdom_ids': refs, 'actor': actor}
        fingerprint = digest(request)
        with connection(self.dsn) as conn, conn.transaction():
            conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('w2p:' + identifier,))
            prior = conn.execute('SELECT parchment_id,request_fingerprint FROM canonical_store.parchments WHERE request_id=%s',
                                 (identifier,)).fetchone()
            if prior:
                if prior['request_fingerprint'] != fingerprint:
                    raise PalimpsestError('idempotency_conflict', '같은 요청 ID의 문서 입력이 변경되었습니다.', 6)
                return {**self._parchment(conn, str(prior['parchment_id'])), 'replayed': True}
            inputs = [WisdomRuntime._wisdom(conn, value) for value in refs]
            allocation = conn.execute('SELECT uuidv7() AS id,CURRENT_TIMESTAMP AS created_at').fetchone()
            snapshot = parchment.build_snapshot(inputs, parchment_id=str(allocation['id']), title=title,
                actor=actor, created_at=allocation['created_at'].isoformat(), implementation_sha256={
                    name: sha256(files('palimpsest').joinpath(name).read_bytes()).hexdigest()
                    for name in ('parchment.py', 'parchment_runtime.py')})
            conn.execute('''INSERT INTO canonical_store.parchments
                (parchment_id,request_id,request_fingerprint,title,actor,snapshot,snapshot_bytes,snapshot_sha256,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''', (snapshot['parchment_id'], identifier, fingerprint,
                    title, actor, Jsonb(snapshot), json.dumps({key: value for key, value in snapshot.items()
                        if key != 'snapshot_sha256'}, ensure_ascii=False, sort_keys=True,
                        separators=(',', ':'), allow_nan=False).encode('utf-8'),
                    snapshot['snapshot_sha256'], allocation['created_at']))
            for index, value in enumerate(inputs):
                conn.execute('''INSERT INTO canonical_store.parchment_wisdoms
                    (parchment_id,ordinal,wisdom_id,wisdom_snapshot_sha256) VALUES (%s,%s,%s,%s)''',
                    (snapshot['parchment_id'], index, value['wisdom_id'], value['snapshot_sha256']))
            return {**snapshot, 'replayed': False}

    def parchment(self, identifier):
        with connection(self.dsn) as conn:
            return self._parchment(conn, identifier)

    def catalog(self):
        with connection(self.dsn) as conn:
            rows = conn.execute('''SELECT parchment_id,title,actor,created_at,
                snapshot->'input_wisdom_ids' AS input_wisdom_ids,snapshot_sha256
                FROM canonical_store.parchments ORDER BY created_at,parchment_id''').fetchall()
            return {'schema_version': 'parchment-catalog-v1', 'parchments': [
                {**row, 'parchment_id': str(row['parchment_id']), 'created_at': row['created_at'].isoformat()} for row in rows]}
