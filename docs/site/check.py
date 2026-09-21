#!/usr/bin/env python3
"""Check only the public static artifact; never inspect local operational state."""
from html.parser import HTMLParser
from pathlib import Path
import sys
import json
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[2] / 'site'
ALLOWED = {'index.html', 'style.css', 'tokens.css', 'app.js', 'mark.svg', 'robots.txt', 'sitemap.xml', 'llms.txt', '_headers'}
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids=[]; self.links=[]; self.assets=[]; self.headings=0
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        if 'id' in a: self.ids.append(a['id'])
        if tag == 'h1': self.headings += 1
        if tag == 'a' and a.get('href'): self.links.append(a['href'])
        if tag in {'script','img','iframe','source'} and a.get('src'): self.assets.append(a['src'])
        if tag == 'link' and a.get('rel') != 'canonical': self.assets.append(a.get('href',''))

def check(root):
    failures=[]
    files={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if files != ALLOWED: failures.append('static file allowlist differs')
    if any(p.is_symlink() for p in root.rglob('*')): failures.append('symlink in static artifact')
    text=(root/'index.html').read_text(); page=Page(); page.feed(text)
    if page.headings != 1: failures.append('expected one primary heading')
    if len(page.ids) != len(set(page.ids)): failures.append('duplicate HTML ids')
    for ref in page.links + page.assets:
        if ref.startswith('#'):
            if ref[1:] not in page.ids: failures.append('missing anchor')
        elif not ref.startswith(('https://','http://','mailto:','data:')):
            target=(root/ref.split('#')[0]).resolve()
            if not target.is_relative_to(root.resolve()) or not target.exists(): failures.append('unresolved local reference')
    if any(ref.startswith(('https://','http://')) for ref in page.assets): failures.append('third-party asset request')
    for required in ['SYNTHETIC EXAMPLE','known secret values','PORTABLE EDITION','Never paste them into agent chat','docs/ONBOARDING.md','docs/MIGRATION.md']:
        if required not in text: failures.append('missing public scope disclosure: '+required)
    for p in root.iterdir():
        if p.is_file():
            body=p.read_text()
            if any(s in body for s in ['/Users/', 'BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY', 'store.db', '.keyserver-token']): failures.append('private marker in artifact')
    aggregate = json.loads((Path(__file__).parent / 'case-study.json').read_text())
    if aggregate['total'] != sum(row['count'] for row in aggregate['surfaces']): failures.append('historical aggregate arithmetic')
    if str(aggregate['total']) + ' recorded value replacements' not in text: failures.append('historical aggregate/site mismatch')
    return failures

if __name__ == '__main__':
    errors=check(ROOT)
    if '--self-test' in sys.argv:
        for case in ('unexpected-file', 'private-marker', 'aggregate-mismatch'):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / 'site'
                shutil.copytree(ROOT, root)
                if case == 'unexpected-file':
                    (root / 'extra.txt').write_text('synthetic')
                elif case == 'private-marker':
                    (root / 'app.js').write_text('// ' + '/Users/' + 'synthetic')
                else:
                    target = root / 'index.html'
                    target.write_text(target.read_text().replace('202 recorded value replacements', '203 recorded value replacements'))
                if not check(root): errors.append('negative probe accepted: ' + case)
        print('Negative probes: unexpected file, private marker, aggregate mismatch')
    print('FAIL: '+ '; '.join(errors) if errors else f'PASS: {len(ALLOWED)} allowlisted static files; local links, public-scope disclosures and remote-asset boundary')
    sys.exit(bool(errors))
