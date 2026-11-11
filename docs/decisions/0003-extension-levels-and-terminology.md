# Decision 0003: extension levels and terminology

Date: 2026-11-10. Status: **proposed**, recorded from the product owner's direction that users should be able to add skills, plugins and connectors.

## Decision

1. **Terms.** A connector links a data source or app. A skill is a versioned reusable capability. A plugin is a signed package that adds skills, tools or interface. An MCP server is a tool server reached through the Model Context Protocol. A pack bundles agents, skills, templates and rules for a domain. Use these terms consistently.
2. **Levels.** An administrator sets Off, Request or Self-serve for each extension type. Suggested defaults: connectors Self-serve for personal accounts the administrator allows; skills Self-serve for personal use only; plugins and MCP servers Request only.
3. **Limits that always hold.** Declaring a permission grants nothing. A personal item is visible only to its owner, never widens the owner's access, and cannot use a route, tool or data class that policy blocks. Output from a personal item inherits its restrictions. External writes still need approval bound to the exact action and payload. Content from connectors and tools is untrusted. Sharing a personal skill requires evaluation and approval. Administrators can list and disable any personal item.

## Open items

- Whether personal skills may use Cloud routes when policy allows; the suggested start is Local and Private only.
- Whether Skills and Plugins become top-level tabs; they are currently sub-tabs.
- Which first connectors to build.

## Consequences

PF-08.06, F-29, API rows, data records, user story and P11D acceptance are added in the documents. This record selects no stack, approves no vertical and claims no implementation.
