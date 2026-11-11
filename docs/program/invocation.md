# B1 trusted controller invocation boundary — implemented draft

Status: B1 (approved 2026-11-11, Draft PR only) over main 0beeb7e6aeeb27763c5a6c5bd21b51fb1e97d950. Plan: [b1-trusted-invocation.md](../plans/universal-modernization/b1-trusted-invocation.md). Evidence is Windows 11 / CPython 3.12.14 / uv 0.12.12 unless a Linux CI run is cited separately. This is a bounded supervised-controller CLI boundary — not a sandbox, authenticator, scheduler, distribution or portability claim.

## What it is

`agent_workflow_pilot.controller.invocation.invoke(runtime, project, operation, args, *, authority, git_dir, cwd=None, timeout=30)` runs **one existing controller CLI per fresh process**:

```text
<trusted absolute python> -I -B -X utf8 -m <fixed module> <fixed subcommand> <validated fixed args> --mode project --expect <per-call expectation>
```

`shell=False`, argv built by the controller, never from worker text. No caller module, Python code, executable override, environment, mode or free argument tail exists. The boundary never passes `--mode legacy` and never relies on the CLIs' `--plan` default (hazard INV-DEFAULT-PLAN in the [register](../readiness/routing-gap-register.md): defaulted cwd-relative `--plan` can select the wrong roadmap; public legacy defaults are intentionally unchanged).

## Trust model (read first)

| Trusted before launch (controller assumption, not checked here) | Checked here |
| --- | --- |
| Interpreter, base install, `site-packages`/`.pth`, `sitecustomize`, `pyvenv.cfg`, DLLs/extensions, existing bytecode, Git binary, toolchain, filesystem access to them, **provenance of the wheel** (`Runtime.provenance` is a reference, never verified) | Package content hash (`*.py` + `py.typed`, read from files without executing the candidate) equals the pin; then a fixed child identity report (`-m …invocation`) must show the pinned minor version and the pinned package location |

Importing the candidate to report where it lives does **not** authenticate an untrusted interpreter: startup/package code runs before any comparison. The checks detect *mismatches*; they do not prevent hostile startup code. This is tested with harmless fixtures and classified: package tampering → detected from file bytes before launch; `sitecustomize` startup code → **not prevented** (it runs). `-I -B` mitigate cwd/`PYTHON*`/bytecode-write influence only; `-B` does not stop bytecode reads. There is a check/use window between pin check and launch. No arbitrary-untrusted-interpreter verifier, immutable-runtime, OS-sandbox or tree-isolation claim is made.

Expectation/approval and ownership inputs are controller **assertions**: Python cannot tell who wrote a file. `authority()` must build the expectation freshly from independently current controller permission on every call (nothing is cached; no `Verified` object crosses calls; roadmap `approved`/`decision` booleans are never authority — every task in `scope` needs a current `valid` approval bound to this project). A revocation inside the window of one call is an accepted race; recheck authority again at any real native/merge action. Output success is never authority: results are checked to carry `authorizes`/`merge_authorized`/`dispatch` literally `false`. Local `origin` config strings are not repository ownership authentication.

## Inputs and path domains

| Input | Domain / rule |
| --- | --- |
| `Runtime(python, minor, package_root, package_sha256, provenance)` | absolute interpreter and installed package directory; minor ≥ 3.12; pin from `package_digest(package_root)`. Provisioning/publishing/rollback are **not** implemented here |
| `Project(project_id, checkout, common_dir, state_dir, writer)` | approved checkout root and Git common dir (absolute); `state_dir` existing, absolute, **disjoint from the checkout**, controller-owned; `writer` = exclusive-writer assertion |
| `git_dir` | absolute directory containing `git`; becomes the whole `PATH` of the child |
| `cwd` | optional existing absolute directory; default is a fresh empty directory under the controller state. `-I` makes neutral/target/hostile/Python-bearing cwd equivalent for imports |
| `plan` (program/identity/lifecycle) | **filesystem** path, absolute, `.json`, inside the approved checkout; specs resolve relative to `plan.parent`; validated in-process (`program.validate`) before launch. External-to-checkout roadmaps are unsupported (identity observes the checkout containing the plan) |
| `plan` (task_context) | **repository-relative** path joined to the explicit checkout root (not an absolute path); `file` must lie in the checkout or controller state |
| `binding`, `delivery` | single path component names (`[A-Za-z0-9][A-Za-z0-9._-]{0,63}`) resolved inside `state_dir`; no separators, links, reserved names or `.identity.json` suffix |
| `observations`, `scope`, `native`, `refs`, `head`, `acceptance`, `intent` | JSON values validated before launch and written by the controller into a per-call directory under `state_dir/.calls/` (removed after clean outcomes, retained when ambiguous) |

Environment of the child: only `PATH=<git_dir>`, `TEMP/TMP/TMPDIR` = per-call directory, and `SystemRoot` on Windows (required by `subprocess` for side-by-side assemblies). Anything else, including `HOME`/`USERPROFILE`, is absent; Git behaviour beyond the fixtures is untested.

## Named operations

| Operation | Command | Writes (state_dir only) | Result (validated) | Notes / replay |
| --- | --- | --- | --- | --- |
| `program.check` / `program.next` | program check/next | none | `plan_hash, task, tasks, explanation, merge_authorized=false` | optional `observations` |
| `program.resume` | program resume | none | same | needs complete binding+envelope pair |
| `identity.check` | identity check | none | `authorizes=false, merge_authorized=false, project_id, repository, task, approval, checkout` | needs current approval for `task` |
| `identity.verify` | identity verify | none | same + `binding_sha256` | envelope must be complete |
| `task_context.validate` | task_context | none | `authorizes=false, context_hash, context` | failures reveal only "task context rejected" |
| `lifecycle.prepare` | lifecycle prepare | `binding`, `binding.identity.json`, `delivery` | `action=reconcile_native_intent, intent, dispatch=false` | replay with identical arguments rewrites nothing; changed arguments are rejected by the CLI |
| `lifecycle.attach` | lifecycle attach | `delivery` | valid checkpoint, `lifecycle=building` | receipts deduplicate replay; conflicting native identity rejected |
| `lifecycle.reconcile` | lifecycle reconcile | none | `action, slot, merge_authorized=false` | `awaiting_authorization` for an unmerged report; never merge authority |

Snapshot hashes of `state_dir` before/after enforce the write set; any other change is an unauthorized write → ambiguous. Pre-launch, the controller also validates the existing binding, its `delivery` (regular file in `state_dir`, valid checkpoint, same task) and the identity envelope. **Missing or torn envelope, binding without envelope, or envelope without binding blocks with no repair** (the CLI's replay would otherwise re-create a missing envelope; the boundary refuses to launch it).

### Explicitly unsupported (exact blockers)

| Operation | Why it is rejected (`kind=unsupported`) |
| --- | --- |
| `continuation.advance` | writes a journal, successor binding/delivery and issues dispatch grants from caller-supplied absolute paths; successor checks use the default observer (A1-P3-03) and interrupted-write recovery depends on A1-P3-02 |
| `identity.bind` / repair / rebind | would complete or recreate envelopes (marker repair) — forbidden unattended; relocation and rebind are unsupported |
| `program.record` | duplicates `lifecycle.prepare`; arbitrary delivery references |
| `onboard` | `onboard.ROOT` derives from the package location, so it fails from an installed wheel (B0 probe 048); needs a separately pinned source/asset checkout (B2) |
| native dispatch / merge / PR | not in this package; B1 launches no native tool |
| runtime provisioning, publishing, rollback | out of scope; no runtime-switch compatibility was tested, so **runtime rollback is unverified** |

## Process contract

Collection is bounded *while reading*: stdout ≤ 64 KiB, stderr ≤ 16 KiB, reader threads stop at the cap and the child is killed (no capture-then-truncate). Explicit wall-clock timeout (0–600 s). stdout must be strict UTF-8, bounded duplicate-key-rejecting JSON object matching the operation schema; non-zero exit, timeout, overflow, non-JSON, wrong shape all fail closed. Cleanup: best-effort tree kill (`taskkill /T /F` on Windows, process-group `SIGKILL` on POSIX — `Popen.kill()` alone is `TerminateProcess` on Windows and does not touch descendants), bounded `wait`, bounded thread joins. A descendant that keeps an inherited pipe open after the child exits is reported as `pipe_held` (reader threads are daemons; they are not waited on indefinitely). Diagnostics returned to callers are single-line bounded excerpts of the runtime's fixed messages with quoted fragments, state/checkout/Git paths and approval references redacted; stdout content is never echoed.

**Stateful ambiguity:** `lifecycle.prepare`/`attach` hold an exclusive `state_dir/.writer.lock` (created `x`). A clean outcome (success, or a rejection that changed nothing) releases it. A timeout, kill, output problem, partial write or unauthorized write leaves the lock (marked ambiguous), the state and the per-call files in place and blocks every later operation on that state, including read-only ones, until a human reconciles. A timeout does **not** prove "no effects", tree-wide termination or exactly-once; remote crash behaviour is untested. `.owner.json` binds a state directory to one `(project_id, writer)`; a different project or writer is refused. Directories and locks are bookkeeping, not OS isolation or authentication.

## Observed vs unmeasured

Observed in `tests/test_invocation.py` (installed wheel in a throwaway venv; non-Python Git fixture in a path with spaces and parentheses; no network, no real remote): checkout tree, installed-runtime tree (including `__pycache__` listing) and `src/` file list are unchanged by all read-only operations and by stateful ones; state changes equal the documented write sets. **Unmeasured:** uv/pip caches, OS caches, Git index timestamps, global user configuration effects, concurrent writers, Linux behaviour not executed by CI, symlink behaviour on hosts without symlink privilege (test skipped there), 8.3/network paths.

## Evidence and sources

Current Python 3.12 documentation reports 3.12.16 while the probe interpreter was 3.12.14; uv docs are unversioned "latest" against uv 0.12.12; the T3 document was read from the `main` branch without a pinned revision and no native call was made. Retrieved 2026-11-11.

- Python subprocess (`Popen.kill` alias of `terminate` on Windows; `wait` deadlock warning with `PIPE`; `env` must include `SystemRoot` for side-by-side assemblies): <https://docs.python.org/3.12/library/subprocess.html>
- Python command line (`-I` implies `-E -P -s`, `PYTHON*` ignored; `-B`; `-X utf8`): <https://docs.python.org/3.12/using/cmdline.html>
- Python site initialization (`.pth`, `sitecustomize`): <https://docs.python.org/3.12/library/site.html>
- Python on Windows: <https://docs.python.org/3.12/using/windows.html>
- uv CLI reference (`--project` vs `--directory`, `--locked`, `pip install --link-mode`, default `hardlink` on Windows): <https://docs.astral.sh/uv/reference/cli/>
- uv running commands (`uv run` ensures the environment is up to date, so it may write — not used per call): <https://docs.astral.sh/uv/concepts/projects/run/>
- uv building distributions (`uv build --wheel`, used only by test fixtures): <https://docs.astral.sh/uv/concepts/projects/build/>
- T3 orchestrator MCP server (child provider/model inherit rules, `clientRequestId`; nothing tells a worker how to run external Python): <https://github.com/pingdotgg/t3code/blob/main/docs/orchestration-v2/orchestrator-mcp-server.md>

Test-fixture lesson recorded: on Windows `uv pip install` defaults to hardlinks into the uv cache; rewriting an installed file corrupted the cache until fixtures used `--link-mode copy`. Fixtures must never write through hardlinked installs.

B0 context: the Coordinator's local, uncommitted B0 artifacts (`b0-invocation-decision.md`, `b0-independent-critique.md`, `b0-evidence/`) informed this design; they are not copied into the repository.

## Not included

B2 onboarding/distribution (the 41/31-path onboarding manifests, `mapping()`, installed-wheel onboarding), C/D/E, A1-P3-01/02/03 repairs, registry/signing, adoption, schedulers or daemons, new checkpoint or approval formats, runtime upgrade/rollback, Linux portability claims beyond separately executed CI.
