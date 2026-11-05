# Reusable task workflow

Run from the target root; replace UPPERCASE placeholders with independently
observed facts. This workflow does not require rebuilding existing project systems.

1. Recover context: read target instructions, START, policy and role contracts;
   inspect branch/head/dirty state and repository facts. Identify the authorized
   problem, exclusions, exact owned paths, existing check commands and unknowns.
   Copy the task template to a project-owned plan. Research only unresolved APIs
   or consequential choices. Do not infer a backlog from filenames or inventory.
2. Plan bounded work with explicit acceptance checks. If an accepted task warrants
   a graph, author a project-owned JSON file using the installed graph schema;
   validate with `python .agent-harness/validators/graph.py TASK-GRAPH.json`.
   Dependencies and ownership express accepted work only; no automatic workers
   or scheduling are created. Preserve existing architecture and dependencies.
3. Implement within assigned ownership on an isolated branch. Run the PROJECT's
   existing documented test/lint/build commands, including relevant negative paths.
   Save commands, output, environment and exact tested head; mark tests not run
   explicitly. Keep mocked checks, local integration and live checks distinct.
4. Push a focused PR and hand off exact SHA, checks, evidence and limitations using
   a filled handoff template. Validate independently resolved SHA and role with
   `python .agent-harness/validators/handoff.py --role reviewer --current-head FULL_SHA HANDOFF.json`.
   Reviewer must be a non-author; record findings using the review template.
   Any new commit invalidates review and CI evidence. Corrections require rechecks
   and fresh independent review. A role contract is not an enforced sandbox.
5. Controller independently collects current head/base, required check source apps,
   effective rules/protections, permissions and independent review evidence. Missing
   or inaccessible evidence blocks merging. Evaluate trusted normalized gate JSON:
   `Get-Content CONTROLLER-EVIDENCE.json | python .agent-harness/validators/gate.py`.
   Exit 0 is policy eligibility only. Controller merges within authorization using
   expected head and normal host controls; no bypass. Release remains separately
   authorized. Workers never merge or certify their own independent review.

For recovery, upgrades and rollback return to the trusted harness checkout.
Archive the previous rollback journal deliberately before a changed upgrade;
conflicts require manual inspection, never forced overwrite.
