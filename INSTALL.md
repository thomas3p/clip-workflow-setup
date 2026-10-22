# Install Clip Workflow Setup

Run this guide when the user asks to install https://github.com/thomas3p/clip-workflow-setup. The user should only need the README's installation prompt and browser login/host approvals. Respond in their language.

## 1. Select the host and preserve context

- Determine whether you are running in Codex Desktop or Claude Code from the actual host, not merely which CLIs are installed. Follow that host's branch. Install both workflow skills only if both were requested.
- Capture the user's current project directory before changing into this checkout. Claude's project MCP configuration belongs in that original project, not in the setup repository. Use the project the user specified. If no usable project is known, ask for that path while doing independent setup work.
- Resolve native Python 3.10+ (`python`, `python3`, `py -3`, or a host-bundled runtime). Do not install another agent CLI to impersonate a different host.
- Preserve existing skills, unrelated MCP servers, user changes, and account sessions. Never request credentials or transfer OAuth state between apps.

## 2. Obtain the repository and install the workflow

Use a persistent local checkout in the user's tools directory:

```sh
git clone https://github.com/thomas3p/clip-workflow-setup.git
```

If a matching checkout exists, inspect it first. Update by fast-forward only when local edits will be preserved; otherwise use another checkout. Do not reset user work. Without Git, obtain `https://github.com/thomas3p/clip-workflow-setup/archive/refs/heads/main.zip` and extract it with the platform's tools.

From that checkout select the current host:

```sh
python install.py --agent codex
python install.py --agent claude
```

A repeated identical installation is a no-op. For an update that differs, inspect user edits before `--replace`, which retains the old skill outside skill discovery. `--project PATH` is available when project scope was requested.

This installs workflow instructions/helpers. Continue to the selected CapCut branch; a copied SKILL.md alone does not complete setup.

## 3A. CapCut in Codex Desktop

Download and read the **entire current official installation runbook**:

https://sf16-sg.tiktokcdn.com/obj/eden-sg/962370eh7nupenuhbo/capcut_codex_plugin/SKILL.md

Follow it exactly in Codex: existing-install check, staged replacement only if needed, verification, account connection check, and its in-app browser login helper when required. Keep the fetched runbook in that run's temporary directory only. Do not hand-edit official Codex MCP configuration or use the Claude adapter here. Never authenticate `capcut_creation_resource`.

Continue to step 4 after connection is confirmed. Reuse its protected read-only check rather than repeating a demo.

## 3B. CapCut adapted for Claude Code

This adapts the official **source bundle** rather than executing Codex's host-specific installation procedure in Claude. Claude does not need Codex CLI or App Server.

1. Obtain the current source into a private local cache **outside this repository and skill discovery**, for example `<user-cache>/clip-workflow-setup/capcut-source`:

   ```sh
   python scripts/fetch_capcut_source.py --destination "<private-capcut-source>"
   ```

   This helper reads the current publisher document as version/source metadata, uses its exact official bundle URL, and does not persist that installation runbook or execute downloaded code. When a source update requires replacement, inspect the version and use `--replace` to retain the previous cache.

2. Adapt it for the **original user project captured in step 1**:

   ```sh
   python scripts/adapt_capcut_claude.py --source "<private-capcut-source>" --project "<user-project>"
   ```

   Read [the adapter guide](references/claude-capcut-adapter.md) for the exact options and supported capabilities. It creates project Claude skills and translates the two official HTTP entries into Claude's schema while preserving unrelated settings. Inspect conflicts before `--replace` and retain backups. Do not copy Codex's authentication helpers or invent a token.

3. Let Claude Code trust/reload the project and approve project MCP entries through its native interface when required. Open `/mcp` and authenticate only **`capcut_creation`** through Claude's normal browser OAuth. If supported by this installed Claude version, `claude mcp login capcut_creation` can start its native login. Never run Codex's `capcut-login.mjs` or log in to the identity-free resource server.

4. Leave login and consent to the user. Keep any active login process alive until it succeeds, is canceled, or fails definitively. If Claude OAuth is rejected or a feature requires a missing Codex card/browser API, report the exact remaining capability. Config creation is not successful authorization. Do not transfer credentials, silently replace endpoints, or claim features that were not verified.

## 4. Verify and start the workflow

- Confirm the workflow is in the selected host's skill directory.
- Discover one available read-only protected `search_capcut_material` tool and call it with `type=font`, `prompt=font`, `top_n=1` to verify account access. Use the actual host's tool naming. Do not create a draft or paid generation solely as an installation demo.
- If tool discovery has not refreshed, reload through the host's supported mechanism. Do not reinstall or repeat OAuth unnecessarily. Distinguish installed, authorized, and protected-tool-verified states.
- Report briefly and continue the original clip task if supplied. Otherwise give the next invocation: `$clip-workflow-setup` in Codex or `/clip-workflow-setup` in Claude.
- Local adapter tests, live OAuth completion, and successful protected operations are separate evidence. Do not claim Claude's live service compatibility was verified from local tests alone.

Publishing, GitHub account setup, customer-media uploads, and paid generation are outside this installation unless separately requested.
