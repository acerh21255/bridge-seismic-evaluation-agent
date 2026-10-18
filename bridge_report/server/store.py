"""SQLite persistence for runs and their event stream."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SUMMARY_FIELDS = ('id', 'status', 'mode', 'source', 'created_at', 'finished_at', 'input_summary', 'report_status')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def dump(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, default=str)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, data TEXT NOT NULL)')
            c.execute('CREATE INDEX IF NOT EXISTS events_run ON events(run_id, seq)')

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, run, *, event=None):
        record = {k: v for k, v in run.items() if k != 'events'}
        with self.connect() as c:
            c.execute('INSERT OR REPLACE INTO runs VALUES (?, ?)', (record['id'], dump(record)))
            if event is not None:
                c.execute('INSERT INTO events (run_id, data) VALUES (?, ?)',
                          (record['id'], dump({'at': now(), **event})))

    def get(self, ident, after=0):
        with self.connect() as c:
            row = c.execute('SELECT data FROM runs WHERE id = ?', (ident,)).fetchone()
            if not row:
                return None
            run = json.loads(row[0])
            run['events'] = [dict(json.loads(data), seq=seq) for seq, data in
                             c.execute('SELECT seq, data FROM events WHERE run_id = ? AND seq > ? ORDER BY seq', (ident, after))]
        return run

    def list(self, limit=100):
        with self.connect() as c:
            rows = c.execute('SELECT data FROM runs ORDER BY rowid DESC LIMIT ?', (limit,)).fetchall()
        return [{k: json.loads(r[0]).get(k) for k in SUMMARY_FIELDS} for r in rows]

    def event(self, ident, kind, title, detail='', **extra):
        record = {'at': now(), 'type': kind, 'title': title, 'detail': detail, **extra}
        with self.connect() as c:
            c.execute('INSERT INTO events (run_id, data) VALUES (?, ?)', (ident, dump(record)))
        return record

    def interrupt_stale(self):
        for summary in self.list(limit=1000):
            if summary['status'] in ('queued', 'running'):
                run = self.get(summary['id'])
                run.pop('events', None)
                run.update(status='interrupted', error='服务重启中断了该任务，未自动重跑；请重新发起任务。')
                self.save(run)
