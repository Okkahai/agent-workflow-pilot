from pathlib import Path
import json
import os
import subprocess

import pytest

from agent_workflow_pilot import onboard as ob

PIN = subprocess.check_output(['git', '-C', str(ob.ROOT), 'rev-parse', 'HEAD'], text=True).strip()


@pytest.fixture
def repo(tmp_path):
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True)
    ob.git(tmp_path, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
           'commit', '--allow-empty', '-m', 'initial')
    return tmp_path


def snapshot(repo):
    return {p.relative_to(repo).as_posix(): p.read_bytes() for p in repo.rglob('*')
            if p.is_file() and '.git' not in p.relative_to(repo).parts}


def test_lifecycle_and_preservation(repo):
    for name in ('AGENTS.md', '.mcp.json', '.agents/skills/unrelated/SKILL.md'):
        p = repo / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('existing instructions')
    before = snapshot(repo)
    assert ob.run('init', repo, PIN, True)['changed']
    assert snapshot(repo) == before
    assert ob.run('init', repo, PIN)['changed']
    assert ob.run('check', repo)['drift'] == []
    assert ob.run('init', repo, PIN)['changed'] == []
    assert ob.run('upgrade', repo, PIN)['changed'] == []
    for name, data in before.items():
        assert (repo / name).read_bytes() == data
    assert not any('calculator' in p or 'examples' in p or 'workflows' in p for p in snapshot(repo))
    inventory = json.loads((repo / ob.INVENTORY).read_bytes())
    assert inventory['graph'] is None
    installed = snapshot(repo)
    ob.run('rollback', repo, dry_run=True)
    assert snapshot(repo) == installed
    ob.run('rollback', repo)
    assert snapshot(repo) == before


@pytest.mark.parametrize('pin', ['main', '95ac900', 'a'*40, '../main', 'A'*40])
def test_bad_pin_no_write(repo, pin):
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        ob.run('init', repo, pin)
    assert snapshot(repo) == {}


@pytest.mark.parametrize('name', [ob.STATE, ob.INVENTORY,
                                   '.agents/skills/handoff/SKILL.md',
                                   '.agent-harness/docs/engineering-standard.md'])
def test_collisions_no_write(repo, name):
    p = repo / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{}' if name == ob.STATE else 'user owned')
    before = snapshot(repo)
    with pytest.raises(ValueError):
        ob.run('init', repo, PIN)
    assert snapshot(repo) == before


@pytest.mark.parametrize('command', ['check', 'init', 'upgrade', 'rollback'])
def test_drift_fails_closed(repo, command):
    ob.run('init', repo, PIN)
    (repo / '.agents/skills/handoff/SKILL.md').write_text('edited')
    before = snapshot(repo)
    with pytest.raises(ValueError):
        ob.run(command, repo, PIN)
    assert snapshot(repo) == before


def test_tampered_manifest_path(repo):
    ob.run('init', repo, PIN)
    p = repo / ob.STATE
    doc = json.loads(p.read_bytes())
    doc['files']['../escape'] = 'a'*64
    p.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='manifest'):
        ob.run('upgrade', repo, PIN)


def test_reject_non_repo_and_subdirectory(tmp_path, repo):
    sub = repo / 'sub'
    sub.mkdir()
    with pytest.raises(ValueError, match='root'):
        ob.run('init', sub, PIN)
    plain = tmp_path / 'plain'
    plain.mkdir()
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        ob.run('init', plain, PIN)


def test_redirect_and_hardlink(repo, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    try:
        (repo / '.agent-harness').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('symlink creation unavailable')
    with pytest.raises(ValueError, match='redirect'):
        ob.run('init', repo, PIN)
    assert list(outside.iterdir()) == []


def test_hardlink(repo):
    original = repo / 'original'
    original.write_text('preserve')
    dest = repo / ob.INVENTORY
    dest.parent.mkdir()
    os.link(original, dest)
    with pytest.raises(ValueError, match='redirect'):
        ob.run('init', repo, PIN)
    assert original.read_text() == 'preserve'


def test_failure_recovery(repo, monkeypatch):
    original = ob.write
    count = 0
    def fail(root, name, data):
        nonlocal count
        count += 1
        if count == 5:
            raise OSError('injected write failure')
        original(root, name, data)
    monkeypatch.setattr(ob, 'write', fail)
    with pytest.raises(OSError, match='injected'):
        ob.run('init', repo, PIN)
    monkeypatch.setattr(ob, 'write', original)
    ob.run('rollback', repo)
    assert snapshot(repo) == {}


def test_upgrade_new_committed_pin(repo, tmp_path, monkeypatch):
    source = tmp_path / 'source'
    subprocess.run(['git', 'clone', '--no-hardlinks', str(ob.ROOT), str(source)],
                   check=True, capture_output=True)
    monkeypatch.setattr(ob, 'ROOT', source)
    ob.run('init', repo, PIN)
    (repo / ob.JOURNAL).unlink()  # deliberate acceptance of previous installation
    asset = source / 'docs/engineering-standard.md'
    asset.write_bytes(asset.read_bytes() + b'\nUpgrade test\n')
    ob.git(source, 'add', 'docs/engineering-standard.md')
    ob.git(source, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
           'commit', '-m', 'fixture revision')
    pin = ob.git(source, 'rev-parse', 'HEAD').decode()
    before = snapshot(repo)
    assert ob.run('upgrade', repo, pin, True)['changed']
    assert snapshot(repo) == before
    ob.run('upgrade', repo, pin)
    assert ob.run('check', repo)['pin'] == pin
    ob.run('rollback', repo)
    assert snapshot(repo) == before


def test_cli(repo, capsys):
    assert ob.main(['init', '--target', str(repo), '--pin', PIN, '--dry-run']) == 0
    assert json.loads(capsys.readouterr().out)['dry_run'] is True
    assert ob.main(['check', '--target', str(repo)]) == 1


def test_pilot_identity_and_remote_rejected(repo, monkeypatch):
    monkeypatch.setattr(ob, 'ROOT', repo)
    with pytest.raises(ValueError, match='pilot repository'):
        ob.run('init', repo, PIN)


def test_pilot_remote_rejected(repo):
    ob.git(repo, 'remote', 'add', 'origin', 'https://github.com/Okkahai/agent-workflow-pilot.git')
    with pytest.raises(ValueError, match='pilot remote'):
        ob.run('init', repo, PIN)
    assert snapshot(repo) == {}


def test_case_alias_and_directory_collision(repo):
    (repo / '.AGENT-HARNESS').mkdir()
    with pytest.raises(ValueError, match='case alias'):
        ob.run('init', repo, PIN)


def test_rollback_path_escape(repo):
    (repo / ob.JOURNAL).parent.mkdir()
    (repo / ob.JOURNAL).write_text(json.dumps({'before': {'../escape': None}, 'after': {}}))
    with pytest.raises(ValueError, match='paths'):
        ob.run('rollback', repo)


def test_rollback_preserves_postinstall_user_change(repo):
    ob.run('init', repo, PIN)
    (repo / ob.STATE).write_bytes((repo / ob.STATE).read_bytes() + b' ')
    before = snapshot(repo)
    with pytest.raises(ValueError, match='rollback conflict'):
        ob.run('rollback', repo)
    assert snapshot(repo) == before


def test_uninitialized_upgrade(repo):
    with pytest.raises(ValueError, match='initialization'):
        ob.run('upgrade', repo, PIN)


@pytest.mark.parametrize('raw', ['null', '[]', '{}', '{"version":1,"pin":null,"files":{}}'])
def test_malformed_manifest(repo, raw):
    (repo / ob.STATE).parent.mkdir()
    (repo / ob.STATE).write_text(raw)
    assert ob.main(['check', '--target', str(repo)]) == 1
