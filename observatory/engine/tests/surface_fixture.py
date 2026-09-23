"""A known measured project and an unmeasured peer, with isolated path readers."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
from dashboard_fixture import seed as dashboard_seed

PROJECT = 'project:fixture-a'
UNMEASURED = 'project:fixture-b'


def reload_readers():
    for name in ('paths', 'store.db', 'store.ledger', 'degradations', 'survey', 'build_findings'):
        if name in sys.modules:
            importlib.reload(sys.modules[name])


@contextmanager
def active(*, samples=2):
    previous = dict(os.environ)
    with tempfile.TemporaryDirectory(prefix='observatory-surface-fixture-') as tmp:
        root = Path(tmp)
        env = dashboard_seed(root, samples=samples)
        os.environ.update(env)
        reload_readers()
        try:
            from store import db, ledger
            now = datetime.now(timezone.utc)
            stamp = now.strftime('%Y-%m-%dT%H:%M:%SZ')
            monday = (now - timedelta(days=now.weekday())).date().isoformat()
            conn = db.connect(root/'state/data.db')
            with conn:
                conn.execute('INSERT INTO project_week(project_id,week,week_start,commits,active_days,authors,sessions,worked_days,computed_at) VALUES (?,?,?,?,?,?,?,?,?)',
                             (PROJECT,now.strftime('%G-W%V'),monday,1,1,1,0,1,stamp))
            ledger.append(conn, owner='agent:fixture', statement='Synthetic proposed observation',
                          why='Fixture evidence', project_id=PROJECT, kind='observation')
            conn.close()
            rels=json.loads((root/'registry/relations.json').read_text())['relations']
            rid=next(r['to'] for r in rels if r['from']==PROJECT and r['type']=='implemented_by')
            finding={'id':'finding:fixture-repo','type':'repo.stale_remote','subject':rid,
                     'severity':'warning','title':'Synthetic repository finding','detail':'Fixture evidence',
                     'action':'Review synthetic mapping','evidence':['SRC-0012']}
            (root/'registry/findings.json').write_text(json.dumps({'findings':[finding]}))
            yield root
        finally:
            os.environ.clear();os.environ.update(previous)
            reload_readers()
