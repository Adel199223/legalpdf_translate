# Bootstrap Capability Discovery

## What This Module Is For
This module prevents new project harnesses from hardcoding stale assumptions about skills, MCP servers, and local tooling.

Instead of assuming a fixed capability set, the bootstrap should inspect the live environment and record only the capabilities that are actually present and relevant.

## Discovery Order
1. Inspect `AGENTS.md` for the current skill inventory
2. Inspect the currently available MCP/tooling surface
3. Inspect relevant local tools and CLIs on the actual host that will run the project
4. Record only the capabilities that materially affect the project harness

## Output Artifact For New Projects
Generate a project-local capability inventory, for example:
- `docs/assistant/LOCAL_CAPABILITIES.md`

That file should record:
- discovered skills relevant to the project
- discovered MCP-backed doc or automation capabilities
- relevant external/local tools that may affect workflows
- host assumptions for each major capability

## Routing Rules
- If `winui-app` is available and the project is Windows/WinUI, route to it.
- If a desktop UI/control skill exists, include it only if it is actually discoverable.
- If `openai-docs` is available, use it for OpenAI product/API guidance.
- Do not hardcode names for local skills that may not exist in the current environment.

## Tool Inventory Examples
The generated capability inventory may include tools like:
- `gog` or other authenticated local CLIs
- browser automation toolchains
- desktop-specific CLIs
- PDF/DOCX helpers
- cloud deployment CLIs

## Hard Rule
Generated repos should prefer dynamic discovery over hardcoded local assumptions.
If a capability is not discoverable, the harness should not pretend it exists.
