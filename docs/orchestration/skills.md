# Portable harness skills (format 1)

Canonical assets live in `harness/skills/<id>/SKILL.md`. Ordinary byte-identical copies live in `.agents/skills/` and `.claude/skills/`. Edit canonical files only; sync regenerates existing files and adds missing files, without deleting unexpected files. No symlinks, junctions, hardlinks, global installation, new dependencies or provider runtime settings are required. Copy the complete canonical directory for a future installer; procedures use repository conventions rather than absolute paths.

| Procedure | Use |
| --- | --- |
| repo-discovery | Inspect an unfamiliar checkout or recover live context |
| research-first | Resolve API/version uncertainty with primary evidence |
| task-planning | Bound outputs, ownership, dependencies and checks |
| handoff | Transfer current-head self-reported work between roles |
| independent-review | Obtain non-author exact-head findings |
| pr-delivery | Deliver tested PR work to the trusted controller |

Read [roles.md](roles.md) for authority boundaries, [handoff.md](handoff.md) for the transfer schema, and [context-pack.md](context-pack.md) for recovery. These are internal repository procedures. Shared authority rules come from engineering policy; each procedure adds only its decision-specific steps. No external skill text was copied.

## Validation and sync

Run from repository root with Python 3.12 and locked dependencies:

```powershell
uv run --locked python -m agent_workflow_pilot.skills --sync
uv run --locked python -m agent_workflow_pilot.skills
uv run --locked pytest
```

Default is read-only comparison; `--root PATH` selects a checkout explicitly. Exit 0 means canonical validation and matching copies (or completed sync); exit 1 means invalid input, filesystem failure or drift; argument misuse exits 2. JSON lists drift in stable provider/path order and always reports runtime discovery as not verified. A successful sync reports the paths it repaired; a subsequent check must report no drift. All roots are preflighted before writes. Writes are idempotent, not a multi-file transaction: after interruption rerun sync. Use an exclusively owned checkout; this is not a concurrent filesystem sandbox.

Format 1 permits Markdown files beneath each skill and exactly two frontmatter fields, `name` and `description`, as JSON-quoted YAML strings. IDs are unique lowercase slugs of at most 63 characters matching the directory; descriptions are nonblank and at most 500 characters. Duplicate/unknown metadata, requirement declarations, control characters, Windows device names, case aliases and filesystem redirects fail. Only inline local Markdown links to existing files within that individual skill are supported; remote URLs, anchors, reference links and HTML are rejected. Use repository-relative paths in code spans for host repository conventions, not bundled links. Extra provider files block sync for deliberate manual reconciliation; no destructive cleanup is performed.

Unsafe-requirement lint rejects dependency/tool declarations and a small set of dangerous command/instruction patterns. It is deliberately conservative and incomplete: it does not prove arbitrary prose safe, authenticate assets, inspect external destinations, execute commands or grant permissions. Policy and independent review remain necessary.

## Provider guidance and honest discovery

The `.agents/skills` copy targets Codex-compatible repository skill discovery; `.claude/skills` targets Claude-compatible repository discovery. These are packaging targets, not a claim about every client version. No generated copy contains provider-specific runtime configuration. T3 routing, installed runtimes, session caches and provider availability are separate concerns; do not load both copies as separate skills in one provider session.

This milestone validates files and exercises sync locally on Windows. It has not demonstrated automatic discovery, selection or activation in a fresh Codex or Claude provider session. Existing session catalogs can predate these files. To establish runtime evidence, start a fresh supported session in the checkout, inspect its catalog for each ID, invoke a bounded procedure and record provider/version, head and observed behavior. Report missing discovery as a limitation rather than silently substituting a provider. Manual reading can exercise procedure content but does not prove automatic discovery. Provider-specific settings belong outside universal policy.
