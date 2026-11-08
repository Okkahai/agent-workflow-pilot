# PC3 Coordinator continuation contract

Use Python 3.12 in this reviewed worktree. This helper does not dispatch, collect
host facts, authenticate artifacts, approve work, or merge. One trusted writer
owns one journal and all binding/delivery files. Do not create a second journal
for the same running program. Scope and plan fingerprint are immutable.

The inherited approved plan is commit d20477e (parent baseline 3f241bb).
The Builder's already prepared PC2 intent/binding remains Coordinator-owned;
this PR does not manufacture or replace that native identity. Builder delivery
is report-ready until merged; it cannot satisfy a code dependency. The A/B
experiment depends on merged PC2, not merged PC3, and runs the reviewed helper.

## Actual A to B experiment

1. Collect current PC1/PC2 merged evidence into `observations.json` using the
   existing program schema (full Git head, verified head, merge commit, target
   tip, verified ancestry, terminal children). Include the current
   `program.fingerprint(plan, root)` as `plan_hash`. Preserve unrelated evidence.
   Use scope `["pc3-a", "pc3-b"]`; original gaps and PR14 remain unauthorized.
2. Prepare A with the existing lifecycle API/CLI, before invoking the native
   read-only task. On first preparation, Coordinator explicitly invokes native
   A once with its persisted intent; on recovery, reconcile that intent with
   native records instead. Attach the returned task/thread using `lifecycle.attach`.
   A returns its complete inventory as text, never writes files. Coordinator
   checks host facts, writes the artifact, hashes its exact bytes, independently
   accepts it, and adds the observation below. Keep the native terminal record.
3. Call `continuation.advance` (or CLI below). Only a fresh `dispatch=true`
   response permits the Coordinator to invoke B once using the returned intent.
   Its binding and delivery intent already exist before this return. B consumes
   the pinned A artifact and original M1-5 sources, returns priorities as text,
   and never writes files. Attach B via the lifecycle API, verify and pin B.
4. Call advance with B's binding, B's exact artifact hash, native record,
   event `b-stop`, and `successor=null`. Expect `action=stop`, `dispatch=false`.
   Journal `active=null` records completion within scope. No gaps are dispatched.

Runnable API preparation (supply real controller-owned observations):

```python
from pathlib import Path
from agent_workflow_pilot.controller import program as p, lifecycle as l
root = Path('docs/program')
plan = p.load(root / 'roadmap.json')
obs = p.load('observations.json')
scope = ['pc3-a', 'pc3-b']
# Create an existing private local directory; use absolute stable paths.
state = Path('coordinator-state').resolve()
state.mkdir(exist_ok=True)
l.prepare(plan, root, state/'a.json', state/'a-delivery.json', obs, scope,
          'pc3-a', ['Verified PC1/PC2 inventory'], 'unique-native-a-intent')
# Coordinator native call happens here, exactly once, outside this package.
# l.attach(plan, root, state/'a.json', obs, scope,
#          {'task': REAL_TASK_ID, 'thread': REAL_THREAD_ID})
```

Artifact observation for `tasks.pc3-a` / `tasks.pc3-b`:

```json
{"state":"delivered","head":"<SHA256 of pinned bytes>",
 "verified_head":"<same independently verified SHA256>",
 "ref":"<immutable artifact and independent acceptance evidence reference>",
 "children_terminal":true,"accepted":true,"independent":true}
```

`head` is artifact content identity here, not the repository head. SHA-256 is
supported for artifacts; legacy 40-hex artifact identities remain compatible.
Code evidence still requires Git SHA and merged ancestry. Booleans are trusted
controller assertions, never worker approval. Keep artifact bytes and acceptance
records outside the worker's write scope.

Save the following as controller-owned `advance.json`, replacing placeholders
with absolute paths and real native values:

```json
{"journal":"<absolute>/serial.json","binding":"<absolute>/a.json",
 "scope":["pc3-a","pc3-b"],"event":"a-to-b",
 "native":{"task":"<native A task>","thread":"<native A thread>",
           "status":"completed","children_terminal":true,"ref":"<native evidence>"},
 "head":"<A artifact SHA256>",
 "successor":{"binding":"<absolute>/b.json","delivery":"<absolute>/b-delivery.json",
              "task":"pc3-b","acceptance":["Prioritized remaining gaps from accepted A"],
              "intent":"unique-native-b-intent"}}
```

```powershell
uv run --locked python -m agent_workflow_pilot.controller.continuation --observations observations.json --input advance.json
```

Exact API: `advance(plan, root, journal, binding, observations, scope, event,
native, head, successor=None)`. CLI uses the same keyword payload in `--input`;
`--plan` defaults to `docs/program/roadmap.json`. Errors return exit 1. Blocked
native or budget results return exit 0 with `dispatch=false` and the slot held.
Selection uses `(priority, task id)` within scope. Missing selected successor
contract fails before retirement. Bindings remain immutable archives.

Same event + same request returns the recorded result with `dispatch=false`;
conflicting replay raises. Fresh observations are validated even on replay.
Pending preparation pins the event/request before successor files are written.
A fresh process can finish that preparation, but returns no dispatch grant.
Any uncertain native outcome must be reconciled by Coordinator with native
records; never create a replacement event or journal to retry dispatch.

## Limits and verification

Local filesystem atomic replacement, one writer, no distributed lock or remote
exactly-once guarantee. A crash after a grant is persisted but before its native
call is intentionally ambiguous: local replay cannot authorize another call.
Do not delete recovery files. No daemon, scheduler, service, dependency, CI,
permission or configuration changes. Local tests simulate terminal assertions;
they do not prove live native A/B execution or independent artifact acceptance.
Coordinator must run and record that experiment after exact-head review.

### Pin acceptance and attach real identities

After each native call, use the actual returned identifiers, never example IDs:

```python
l.attach(plan, root, state/'a.json', obs, scope,
         {'task': actual_a_task_id, 'thread': actual_a_thread_id})
```

After independent host verification, the Coordinator saves the returned text and
an acceptance record in its private state directory (outside worker write scope):

```python
import hashlib
import json
artifact_path = state / 'a-artifact.txt'
artifact_path.write_text(actual_a_text, encoding='utf-8')
digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
acceptance_path = state / 'a-acceptance.json'
acceptance_path.write_text(json.dumps({
    'artifact': str(artifact_path), 'sha256': digest,
    'native_task': actual_a_task_id, 'native_thread': actual_a_thread_id,
    'verification_ref': independent_host_verification_ref,
    'accepted_by': coordinator_identity,
}), encoding='utf-8')
obs['tasks']['pc3-a'] = dict(
    state='delivered', head=digest, verified_head=digest,
    ref=str(acceptance_path), children_terminal=True,
    accepted=True, independent=True)
(state/'observations.json').write_text(json.dumps(obs), encoding='utf-8')
```

These booleans are recorded only after actual verification, not by executing a
snippet blindly. Preserve the bytes and acceptance record without overwriting.
Use the same procedure for B with its own paths/IDs and `pc3-b` observation.
Attach B using `l.attach(..., state/'b.json', ..., actual_b_refs)`.
For the final CLI call, copy the advance payload with `binding` set to B,
`event` set to `b-stop`, B's native record and hash, and `successor` set to null.
Replays use the original payload and never issue another native call.
