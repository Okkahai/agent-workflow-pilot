# Portable onboarding (format 1)

Run from this harness checkout, using Python 3.12, Git and its locked uv environment.
The target needs only a local Git repository with an existing commit; it need not
use Python, uv, or this package. Nothing is installed globally. Commands do not
fetch, contact a host, commit, change Git config, enable CI or merge anything.

Choose a reviewed integration commit containing every asset in `mapping()` (older
milestone pins lack the new entrypoint/templates and fail without writing).
`FULL_REVIEWED_SHA` below is a placeholder, never a branch or tag. Record the
installer and asset SHA trust decisions before adoption.

```powershell
uv run --locked python -m agent_workflow_pilot.onboard init --target "C:\path\to\target" --pin FULL_REVIEWED_SHA --dry-run
uv run --locked python -m agent_workflow_pilot.onboard init --target "C:\path\to\target" --pin FULL_REVIEWED_SHA
uv run --locked python -m agent_workflow_pilot.onboard check --target "C:\path\to\target"
```


These are instructions for future authorized adoption, not evidence of adoption.
This milestone accesses no OpsPilot, MarketOS, Alibi or other real target project;
all target tests use disposable temporary Git repositories.

## Contents and adoption

The code's fixed `mapping()` is the allowlist. It copies committed blobs only:
universal standard, roles, skill and graph/handoff documentation, context recovery,
onboarding template, six canonical skills, and standalone graph/handoff/gate
validators. Assets live under `.agent-harness/`; ordinary skill copies also live
under `.agents/skills/` and `.claude/skills/`. No calculator, sample graph, example
handoff, CI, provider runtime configuration, MCP configuration or root instructions
are copied. The pilot repository, its worktrees, and targets whose remote contains
`agent-workflow-pilot` are rejected. A renamed clone without that identity cannot
be recognized as the pilot: this is a guardrail, not an access sandbox.

After installation open `.agent-harness/START.md` in the target. It supplies
standalone commands, corrected installed paths and links to the reusable adoption
workflow and editable templates. See [project-adoption.md](project-adoption.md).
Upstream docs remain reference contracts; their pilot package commands are not
target commands. Target toolchains and systems are preserved.

The generated `.agent-harness/initial-graph.json` is valid under the installed
schema. It contains one completed inventory-recording node, no project tasks or
ownership. Inventory records Git root/head and root instruction presence only;
stack, owners, checks, architecture, permissions and runtime discovery stay unknown.
Both are managed historical snapshots. Keep ongoing facts/plans in editable copies.

## Pin and trust boundary

`--pin` must be the full lowercase SHA of a locally available commit. Branches,
tags, abbreviations and missing objects fail. The manifest records that exact SHA
and SHA-256 of installed bytes. The installer reads allowlisted regular blobs via
Git, ignoring dirty working-tree assets. Review both the executing installer
checkout and chosen asset commit. A SHA provides identity, not authenticity, safety
or authorization. Review the pin as an explicit trust decision; no publisher signature or automatic
provenance verification is supplied.
Local manifests and rollback data are unauthenticated; do not trust them after
untrusted edits. `check` also compares asset hashes with the recorded commit.
No secrets, remote capabilities, effective protections or delivery rights are
inferred from local files.

## Upgrade and rollback

1. Run `check`. Review and archive `.agent-harness/rollback.json` outside the target
   if accepting the previous operation; remove that snapshot deliberately before
   starting another changed operation. The tool refuses to overwrite recovery data.
2. Review a new locally available full commit SHA. Run `upgrade --target PATH
   --pin FULL_SHA --dry-run` using the same module invocation above. Resolve all
   conflicts manually; there is no force flag or silent overwrite.
3. Run the same upgrade without `--dry-run`, then `check`. Every owned file must
   match its previous hash before writes. New/unowned collisions block init.
4. To undo the last operation (including a partial write), run `rollback --target
   PATH --dry-run`, then without `--dry-run`. Rollback preflights every path against
   before/after hashes and refuses intervening edits; it restores prior bytes or
   removes newly installed files. It does not delete unrelated files or directories.

`init` with the same pin is idempotent; changing pins requires `upgrade`. Same-pin
upgrade is a no-op. JSON output lists changed paths; errors exit 1 and argument
errors exit 2. `--dry-run` writes no files. Read-only `check` requires an installed
manifest and detects missing/changed owned files; unrelated files are preserved.

## Limits

Single-writer, trusted local filesystem only. Symlinks, junctions/reparse points,
hardlinked managed files and case aliases on managed paths are rejected. These
checks do not close concurrent filesystem races or defend against malicious Git
configuration, hooks/filters, replacement objects, or a compromised executable.
Use exclusively owned, authorized checkouts. No target package scripts are run.

A persisted rollback snapshot precedes per-file replacements; this is **not a
multi-file transaction**, and it is not crash/power-loss durable. There is no fsync
or automatic rollback guarantee. Disk/permission failures can leave partial files;
keep the snapshot, resolve environmental failures and run rollback. Empty directories
and file metadata are not restored. Interrupted rollback is retryable while each
file still matches a recorded before/after hash. Tampered recovery records require
manual recovery. Windows symlink tests may skip without symlink privileges; ordinary
installation, hardlinks, lifecycle and failure recovery are exercised on Windows.
