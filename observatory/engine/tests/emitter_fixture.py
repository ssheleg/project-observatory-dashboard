"""Frozen synthetic inputs for emitter behavior tests; no personal raw store."""
from pathlib import Path
import json
import os


def seed(root: Path) -> dict[str, str]:
    raw, registry, curated = root / 'raw', root / 'registry', root / 'curation'
    raw.mkdir(); registry.mkdir(); curated.mkdir()
    def write(path, value):
        path.write_text(json.dumps(value), encoding='utf-8')
    project = dict(anchor='fixture', ownership='owned', owners=['fixture'], archived=False,
                   description='', kinds=[], folders=[], last_activity=None,
                   has_note=False, rules=[], vault=None, sites=[])
    projects = {'fixture-a': dict(project, name='Fixture A', repos=['fixture/service']),
                'fixture-b': dict(project, name='Fixture B', repos=[])}
    repo = dict(host='github', url='https://github.com/fixture/service', visibility='private',
                description='Synthetic repository', archived=False, fork=False, language=None,
                topics=[], pushed_at=None, created_at=None, source='github-api', local=None)
    write(raw / 'model.json', dict(projects=projects, repositories={'fixture/service': repo},
                                   duplicate_repo_names=[]))
    for name, key in [('projects', 'projects'), ('repositories', 'repositories'),
                      ('domains', 'domains'), ('sources', 'sources')]:
        # The public engine versions projects/repositories/relations at 2, the rest at 1.
        write(registry / (name + '.json'), {'schema_version': 2 if name in ('projects', 'repositories') else 1, key: []})
    write(registry / 'relations.json', {'schema_version': 2, 'relation_types': {}, 'relations': []})
    for name, key in [('project_overrides', 'projects'), ('repo_status', 'repositories'),
                      ('repo_overrides', 'repositories')]:
        write(curated / (name + '.json'), {key: {}})
    write(curated / 'products.json', {'products': {}, 'roles': []})
    return environment(root)


def environment(root: Path) -> dict[str, str]:
    raw, registry = root / 'raw', root / 'registry'
    return {**os.environ, 'OBSERVATORY_REGISTRY': str(registry), 'OBSERVATORY_SCRATCH': str(raw),
            'OBSERVATORY_CURATION': str(root / 'curation'),
            'OBSERVATORY_DB': str(root / 'absent.db'), 'OBSERVATORY_STATE': str(root / 'state'),
            'OBSERVATORY_VAULT_DIR': str(root / 'empty-vault')}
