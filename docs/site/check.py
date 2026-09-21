#!/usr/bin/env python3
"""Validate the public static tree without reading any runtime state."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, unquote
import hashlib
import sys
import json
import tempfile
import shutil

ROOT = Path(__file__).resolve().parents[2] / 'site'
ALLOWED = {'index.html', 'style.css', 'tokens.css', 'app.js', 'mark.svg', 'robots.txt', 'sitemap.xml', 'llms.txt', '_headers', 'field-notes/index.html', 'assets/observatory-cover.png'}
COVER_HASH = '70403cdb6ffc4029edcf2febbf63dec88a3118fa6cea9d7d6b17150d853d4833'
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
    root=root.resolve(); failures=[]
    files={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
    if files != ALLOWED: failures.append('static file allowlist differs')
    if any(p.is_symlink() for p in root.rglob('*')): return failures+['symlink in static artifact']
    pages={}
    for rel in sorted(files):
        p=root/rel
        if rel == 'assets/observatory-cover.png':
            data=p.read_bytes()
            if hashlib.sha256(data).hexdigest()!=COVER_HASH or not data.startswith(b'\x89PNG\r\n\x1a\n'): failures.append('unreviewed cover image')
            continue
        try: body=p.read_text()
        except UnicodeError:
            failures.append('unreviewed binary'); continue
        if any(s in body for s in ['/Users/', 'BEGIN PRIVATE KEY', 'BEGIN RSA PRIVATE KEY', 'store.db', '.keyserver-token']): failures.append('private marker in artifact')
        if p.suffix=='.html':
            page=Page();page.feed(body);pages[p]=page
            if page.headings!=1: failures.append('expected one primary heading: '+rel)
            if len(page.ids)!=len(set(page.ids)): failures.append('duplicate HTML ids: '+rel)
            if any(urlsplit(ref).scheme or ref.startswith('//') for ref in page.assets): failures.append('nonlocal asset request')
    for source,page in pages.items():
        for ref in page.links+page.assets:
            url=urlsplit(ref)
            if url.scheme or url.netloc:
                if url.scheme not in {'http','https','mailto'}: failures.append('unexpected link scheme')
                continue
            path=unquote(url.path)
            target=((root/path.lstrip('/')) if path.startswith('/') else (source.parent/path) if path else source).resolve()
            if target.is_dir():target=target/'index.html'
            if not target.is_relative_to(root) or not target.is_file(): failures.append('unresolved local reference');continue
            if url.fragment and (target not in pages or unquote(url.fragment) not in pages[target].ids): failures.append('missing anchor')
    text=(root/'index.html').read_text() if (root/'index.html').is_file() else ''
    for required in ['SYNTHETIC EXAMPLE','known secret values','COMPLETE LOCAL ENGINE','Never paste them into agent chat','docs/ONBOARDING.md','docs/MIGRATION.md']:
        if required not in text: failures.append('missing public scope disclosure: '+required)
    aggregate=json.loads((Path(__file__).parent/'case-study.json').read_text())
    if aggregate['total']!=sum(row['count'] for row in aggregate['surfaces']):failures.append('historical aggregate arithmetic')
    if str(aggregate['total'])+' recorded value replacements' not in text:failures.append('historical aggregate/site mismatch')
    return failures

if __name__=='__main__':
    errors=check(ROOT)
    if '--self-test' in sys.argv:
        cases=('unexpected-file','private-marker','aggregate-mismatch','image-tamper','article-anchor','article-link')
        for case in cases:
            with tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary)/'site';shutil.copytree(ROOT,root)
                if case=='unexpected-file':(root/'extra.txt').write_text('synthetic')
                elif case=='private-marker':(root/'app.js').write_text('// /Users/synthetic')
                elif case=='image-tamper':
                    with (root/'assets/observatory-cover.png').open('ab') as f:f.write(b'changed')
                elif case in {'article-anchor','article-link'}:
                    target=root/'field-notes/index.html'
                    target.write_text(target.read_text().replace('href="../#start"','href="../#absent"' if case=='article-anchor' else 'href="../../private.html"'))
                else:
                    target=root/'index.html';target.write_text(target.read_text().replace('202 recorded value replacements','203 recorded value replacements'))
                if not check(root):errors.append('negative probe accepted: '+case)
        print(f'Negative probes: {len(cases)}')
    print('FAIL: '+'; '.join(errors) if errors else f'PASS: {len(ALLOWED)} reviewed static files; both pages, local links, scope and cover digest')
    sys.exit(bool(errors))
