"""Real local Git tests; no GitHub mutation or merge authorization."""
import subprocess


def git(path, *args, ok=True):
    result = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True)
    if ok:
        assert result.returncode == 0, result.stderr
    return result


def test_worktrees_and_stale_reconciliation(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    git(repo, 'init', '-b', 'main')
    git(repo, 'config', 'user.email', 'test@example.invalid')
    git(repo, 'config', 'user.name', 'Test')
    (repo / 'shared').write_text('base')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'base')
    first, second = tmp_path / 'first', tmp_path / 'second'
    git(repo, 'worktree', 'add', '-b', 'first', str(first))
    git(repo, 'worktree', 'add', '-b', 'second', str(second))
    (first / 'shared').write_text('first')
    assert (second / 'shared').read_text() == 'base'
    assert git(second, 'status', '--porcelain').stdout == ''
    git(first, 'commit', '-am', 'first')
    (second / 'shared').write_text('second')
    git(second, 'commit', '-am', 'second')
    old = git(second, 'rev-parse', 'HEAD').stdout
    assert git(second, 'merge', '--ff-only', 'first', ok=False).returncode != 0
    assert git(second, 'rev-parse', 'HEAD').stdout == old
    assert git(second, 'merge', 'first', ok=False).returncode != 0
    git(second, 'merge', '--abort')
    assert (second / 'shared').read_text() == 'second'
    assert git(second, 'rev-parse', 'HEAD').stdout == old
    # Explicit reconciliation preserves both histories without a force push.
    git(second, 'merge', 'first', ok=False)
    (second / 'shared').write_text('first + second')
    git(second, 'add', 'shared')
    git(second, 'commit', '-m', 'resolve both changes')
    git(second, 'merge-base', '--is-ancestor', 'first', 'HEAD')
    git(second, 'merge-base', '--is-ancestor', old.strip(), 'HEAD')
