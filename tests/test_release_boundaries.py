"""Synthetic rejection tests for public source, image history and wheel boundaries."""
from __future__ import annotations
import base64
import csv
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'tools'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

privacy=load('check_public_release')
package=load('check_package')

class ReleaseBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='observatory-release-test-')
        self.root=Path(self.temp.name).resolve()
    def tearDown(self):self.temp.cleanup()
    def put(self,path,data):
        file=self.root/path;file.parent.mkdir(parents=True,exist_ok=True)
        file.write_bytes(data if isinstance(data,bytes) else data.encode());return file
    def git(self,*args):
        env={**os.environ,'GIT_AUTHOR_NAME':'Fixture Maintainer','GIT_COMMITTER_NAME':'Fixture Maintainer',
             'GIT_AUTHOR_EMAIL':'fixture@example.invalid','GIT_COMMITTER_EMAIL':'fixture@example.invalid'}
        return subprocess.run(['git','-C',str(self.root),*args],env=env,check=True,capture_output=True)
    def test_engine_code_allowlist_excludes_mutable_data_and_hidden_credentials(self):
        for allowed in ('observatory/engine/store/schema.sql','observatory/engine/store/db.py',
                        'observatory/engine/defaults/settings.json','observatory/engine/tools/tick.sh',
                        'observatory/engine/skill/.claude-plugin/marketplace.json'):
            self.assertTrue(privacy.allowed_path(Path(allowed)),allowed)
        for refused in ('observatory/engine/store/observatory.db','observatory/engine/store/retention.json',
                        'observatory/engine/registry/projects.json','observatory/engine/secrets/key.json',
                        'observatory/engine/.env','observatory/engine/tools/unreviewed.sh',
                        'observatory/engine/.keyserver-token'):
            self.assertFalse(privacy.allowed_path(Path(refused)),refused)
    def test_current_filename_is_scanned_without_echoing_private_identifier(self):
        self.put('docs/Confidential-Fixture.md','Generic text')
        result=privacy.audit(self.root,['confidential-fixture'],False)
        self.assertFalse(result['passed']);self.assertNotIn('Confidential-Fixture',json.dumps(result))
    def test_private_identifier_match_is_case_insensitive_but_not_substring(self):
        self.assertEqual(privacy.scan_text('public-Confidential-Fixture-tools',['confidential-fixture']),{})
        self.assertTrue(privacy.scan_text('CONFIDENTIAL-FIXTURE.git',['confidential-fixture']))
    def test_reviewed_image_bytes_are_bound_to_path_digest_and_size(self):
        path='site/assets/fixture.png';data=b'\x89PNG\r\n\x1a\nsynthetic-image'
        approved={path:{hashlib.sha256(data).hexdigest()}}
        with patch.dict(privacy.PUBLIC_IMAGES,approved,clear=True):
            self.put(path,data)
            self.assertTrue(privacy.audit(self.root,[],False)['passed'])
            self.put(path,data+b'changed')
            self.assertFalse(privacy.audit(self.root,[],False)['passed'])
            self.assertFalse(privacy.approved_image('site/assets/other.png',data))
            large=b'\x89PNG\r\n\x1a\n'+b'x'*(4*1024*1024)
            privacy.PUBLIC_IMAGES[path]={hashlib.sha256(large).hexdigest()}
            self.assertFalse(privacy.approved_image(path,large))
    def test_history_checks_removed_secret_and_prior_unreviewed_image(self):
        path='site/assets/fixture.png';approved=b'\x89PNG\r\n\x1a\nreviewed'
        with patch.dict(privacy.PUBLIC_IMAGES,{path:{hashlib.sha256(approved).hexdigest()}},clear=True):
            self.git('init','-q')
            self.put('docs/history.md','removed confidential-fixture')
            self.put(path,b'\x89PNG\r\n\x1a\nnot-reviewed')
            self.git('add','.');self.git('commit','-qm','Synthetic earlier state')
            self.put('docs/history.md','Generic current text');self.put(path,approved)
            self.git('add','.');self.git('commit','-qm','Synthetic reviewed state')
            self.assertTrue(privacy.audit(self.root,['confidential-fixture'],False)['passed'])
            result=privacy.audit(self.root,['confidential-fixture'],True)
            kinds={item['kind'] for item in result['findings']}
            self.assertIn('history:private-identifier',kinds)
            self.assertIn('history:unreviewed-image',kinds)
            self.assertNotIn('confidential-fixture',json.dumps(result))
    def package_files(self):
        self.put('pyproject.toml','[project]\nname="project-observatory"\nversion="0.2.0"\n')
        runtime={'observatory/__init__.py':b'', 'observatory/engine/example.py':b'VALUE = 1\n'}
        manifest={'files':[{'path':'example.py','export_sha256':hashlib.sha256(runtime['observatory/engine/example.py']).hexdigest()}]}
        runtime['observatory/engine/SOURCE-INVENTORY.json']=json.dumps(manifest).encode()
        for name,data in runtime.items():self.put(name,data)
        runtime.update({'project_observatory-0.2.0.dist-info/METADATA':b'Metadata-Version: 2.4\nName: project-observatory\nVersion: 0.2.0\n',
                        'project_observatory-0.2.0.dist-info/WHEEL':b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'})
        return runtime
    def wheel(self,files,*,record_overrides=None,symlink=None,duplicate=None):
        record='project_observatory-0.2.0.dist-info/RECORD'
        rows=[]
        for name,data in files.items():
            digest='sha256='+base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b'=').decode()
            rows.append([name,digest,str(len(data))])
        rows.append([record,'',''])
        if record_overrides:record_overrides(rows)
        output=io.StringIO();csv.writer(output,lineterminator='\n').writerows(rows)
        files={**files,record:output.getvalue().encode()}
        wheel=self.root/'fixture.whl'
        with warnings.catch_warnings(),zipfile.ZipFile(wheel,'w') as archive:
            warnings.simplefilter('ignore',UserWarning)
            for name,data in files.items():
                info=zipfile.ZipInfo(name);info.create_system=3
                info.external_attr=((stat.S_IFLNK if name==symlink else stat.S_IFREG)|0o644)<<16
                archive.writestr(info,data)
            if duplicate:archive.writestr(duplicate,files[duplicate])
        return wheel
    def checked(self,wheel):
        with patch.object(package,'ROOT',self.root):return package.check(wheel)
    def test_valid_reviewed_wheel_and_record_pass(self):
        self.assertTrue(self.checked(self.wheel(self.package_files()))['passed'])
    def test_wheel_rejects_missing_tampered_duplicate_and_unsafe_members(self):
        original=self.package_files()
        variants=[{k:v for k,v in original.items() if k!='observatory/engine/example.py'},
                  {**original,'observatory/engine/example.py':b'changed'},
                  {**original,'../escape.py':b'escape'},
                  {**original,'observatory/engine/extra.json':b'{}'}]
        for files in variants:self.assertFalse(self.checked(self.wheel(files))['passed'])
        self.assertFalse(self.checked(self.wheel(original,duplicate='observatory/engine/example.py'))['passed'])
    def test_wheel_rejects_symlink_even_when_content_matches_source(self):
        self.assertFalse(self.checked(self.wheel(self.package_files(),symlink='observatory/engine/example.py'))['passed'])
    def test_wheel_rejects_unreviewed_dist_info_payload(self):
        files=self.package_files();files['project_observatory-0.2.0.dist-info/secrets.json']=b'{}'
        self.assertFalse(self.checked(self.wheel(files))['passed'])
    def test_wheel_record_requires_exact_members_valid_hashes_and_sizes(self):
        files=self.package_files()
        changes=[lambda rows:rows.pop(0),lambda rows:rows.append(rows[0]),
                 lambda rows:rows[0].__setitem__(1,'sha256=wrong'),
                 lambda rows:rows[0].__setitem__(2,'999')]
        for change in changes:self.assertFalse(self.checked(self.wheel(files,record_overrides=change))['passed'])

if __name__=='__main__':unittest.main()
