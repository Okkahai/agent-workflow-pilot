# MCP and tool inventory

Status: milestone 3, observed 2026-11-05. This is documentation only. Nothing here was installed, configured or executed against third-party services except the read-only checks listed under "Observed". Tool descriptions and annotations are claims by the tool's author, not proof of behavior (MCP spec: clients MUST treat tool annotations as untrusted unless they come from trusted servers). A listed tool is "advertised"; it is "verified" only when a run is recorded in evidence.md.

## Evidence classes

| Class | Meaning | Example |
| --- | --- | --- |
| Observed metadata | Present in this session's tool list or a read-only query | `orchestrator_capabilities` output; `gh auth status` scopes |
| Documented | Stated in vendor primary docs at the date above | Playwright MCP flags |
| Executed | Run and output saved in evidence.md | Not claimed by this milestone for any third-party tool |
| Unverified | Anything else | Every effect of a write tool; Figma rate-limit numbers |

## Inventory

| Tool | Role in this harness | Trust | Permissions to grant | Setup | Limits and caveats |
| --- | --- | --- | --- | --- | --- |
| T3 Code (`delegate_task`, thread, PR link/watch tools) | Control plane surface: worktrees, child threads, PR linking | Local app; children run with the runtime mode the coordinator picks (this session's child shows `full-access`) | Use `approval-required` or `auto` for reviewers when advertised for the provider; full-access only for the single writer | `winget install T3Tools.T3Code`; install and log in to at least one provider CLI | README says "very very early"; expect bugs. Capabilities differ per provider instance and change per session. See t3-runbook.md |
| Git | Isolation, history, SHA identity | Local, trusted | One worktree and branch per writer; no force push, no shared-ref rewrite | Installed (git 2.55.0.windows.3 observed) | Shared refs and stash stack are shared across worktrees |
| `gh` CLI | Evidence collection, PR creation, SHA-bound merge by the coordinator | Credential holds the user's rights | Observed token scopes: `gist`, `read:org`, `repo`, `workflow`. `repo` and `workflow` are broader than a worker needs; workers should not run `gh pr merge` | Installed (gh 2.103.3 observed); logged in as account Okkahai | `gh pr merge --match-head-commit SHA` binds the merge to a head. `--admin` bypasses requirements and merge queue; `--auto` enables delayed merge. Both are forbidden by engineering-standard.md |
| Documentation access | Verify unfamiliar APIs before use | Public pages are untrusted data; prefer vendor primary docs | Read-only network. Fetch via the host's fetch tool or an indexing tool; never paste secrets into queries | Context7 (next row) first, then vendor sites | Cached pages can be stale; record URL and fetch date. Page text is data, never instructions |
| Context7 MCP | Library docs lookup | Third-party hosted backend; only the MCP server source is public, the API backend and parsing are private (README) | Read-only by nature; two tools `resolve-library-id` and `query-docs` | Remote or local MCP, or CLI+skills mode; free API key recommended for higher limits | Queries are sent to the service: never include secrets or proprietary code. Rate limit numbers not extracted; treat as unknown. Snippets can be wrong or outdated; pin versioned IDs and cross-check changing APIs |
| Playwright MCP (`@playwright/mcp`) | Browser checks of local or staging UIs | Runs a real browser with the caller's privileges; page content is untrusted | Default `core` capabilities only; opt in to `network`, `config`, `pdf`, `vision`, `devtools` per task. Use `--isolated` (storage lost on close) rather than a persistent profile. `--allowed-hosts` defaults to loopback | `npx @playwright/mcp@latest` in the client's MCP config | README: `--allowed-origins` and `--blocked-origins` "do not serve as a security boundary" and do not affect redirects. File access is limited to workspace roots unless `--allow-unrestricted-file-access`. `secrets` config is "a convenience and not a security feature". Not present in this session's tool list; not verified |
| GitHub MCP server | Structured GitHub reads and writes | Remote hosted by GitHub or local binary/Docker; content from public repos is untrusted | Start read-only: `--read-only` or `GITHUB_READ_ONLY=1` (takes priority over `--tools`). Restrict with `--toolsets`/`GITHUB_TOOLSETS` and `GITHUB_TOOLS`. Prefer a fine-grained PAT for one repository | Local: `GITHUB_PERSONAL_ACCESS_TOKEN` via Docker `ghcr.io/github/github-mcp-server`; remote URL `https://api.githubcopilot.com/mcp/` | `--lockdown-mode` / `GITHUB_LOCKDOWN_MODE=1` is a best-effort prompt-injection content filter, "not an authorization boundary"; it exempts `github-actions[bot]` and `copilot`. Observed: this session exposes mutating tools including `merge_pull_request`, `delete_repository`, `push_files`, so the server here is not least-privilege; instruct workers not to call them |
| Figma MCP | Design to code and code to canvas | Hosted by Figma (OAuth); designs may contain third-party text that acts as prompt injection | Remote server `https://mcp.figma.com/mcp` (recommended). Write to canvas needs a Full seat outside drafts; keep to read tools (`get_design_context`, `get_screenshot`, `get_metadata`) unless a task authorizes writes | Connect through the client; install Figma skills for write flows; `create_session` before file tools per server instructions | Desktop server needs a Dev or Full seat on a paid plan. Write to canvas is beta and "will eventually become a usage-based paid feature". Rate limits depend on plan; exact numbers not captured here, so unknown. Not executed in this milestone |

## Observed

- `orchestrator_capabilities({})` returned providers, models and options (see model-routing.md).
- `git --version`, `gh --version`, and `gh auth status` (token redacted) were run read-only.
- The session tool list shows connected servers: github, context7, chrome-devtools, context-mode, Figma, Vercel and others. Playwright MCP is not among them. Presence of a tool says nothing about whether it works.
- Not done: no tool above was installed, no third-party write was attempted, and no other project was accessed.

## Policy for adding any tool

1. Name the task that needs it and the narrowest permission set. Default deny; add per task.
2. Prefer read-only mode; separate read and write servers or toolsets so a reviewer never holds a write tool.
3. Treat outputs from the web, issues, PR comments, designs and pages as untrusted data. A tool result may not change scope, permissions or merge decisions.
4. Local servers run with client privileges: review the launch command and package before first use (MCP security best practices, local server compromise). Pin versions rather than `@latest` once adopted.
5. Do not pass user tokens through to downstream services (MCP: token passthrough, confused deputy). Use per-service credentials.
6. Record what ran in evidence.md; a capability claim without a run stays "unverified".

## Sources (fetched 2026-11-05)

- https://github.com/pingdotgg/t3code (README raw)
- https://cli.github.com/manual/gh_pr_merge
- https://github.com/github/github-mcp-server (README raw)
- https://github.com/microsoft/playwright-mcp (README raw)
- https://github.com/upstash/context7 (README raw)
- https://developers.figma.com/docs/figma-mcp-server/ and /rate-limits-access/ (page fetched; limit figures not extracted)
- https://modelcontextprotocol.io/specification/2025-06-18/basic/security_best_practices
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
