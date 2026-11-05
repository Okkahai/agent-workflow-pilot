"""Temporary controlled CI failure; remove only after recording the failed run."""
def test_controlled_ci_failure():
    assert False, 'Controlled negative experiment: merge must remain blocked'
