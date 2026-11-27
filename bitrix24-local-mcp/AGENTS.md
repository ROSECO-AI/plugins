# Bitrix24 Local MCP

Local stdio MCP connector, derived from the existing Python bitrix24-local implementation.
Python 3.10+, standard library only. All user credentials and deployed runtime live
outside the plugin cache and repository. Never read a real config for publication,
never commit portal exports, tokens, local user paths or personal identities.

- Keep universal REST functionality; classify unknown methods conservatively as writes.
- Never treat a method-name suffix as proof of read-only behavior.
- Keep batch disabled unless an implementation inspects every subcall and tests it.
- Preserve full API envelopes, especially next and total; never silently truncate results.
- No automatic retries for writes. A lost response can mean a successful remote mutation.
- MCP annotations are hints; consent is enforced by the host/user workflow, not a boolean
  argument supplied by the model. Local writes_enabled is a separate capability switch.
- Installer resolves sys.executable; avoid a fixed macOS or Windows command in manifests.
- Match versions and metadata in both manifests and runtime. Keep README and CURRENT_STATE current.
- Run `python3 -m unittest discover -s tests -v` from this directory before release.
- CI must run on Windows, macOS and Linux. Use only synthetic credentials in tests.
- Publish to the existing ROSECO-AI/plugins marketplace, preserving other plugins.

