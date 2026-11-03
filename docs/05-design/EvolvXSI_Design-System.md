# EvolvXSI — design system

Status: **interaction principles; visual tokens pending brand approval** · Updated: 2026-11-02

## Purpose

Create a consistent interface for task execution, evidence inspection, review, and administration. The product name is EvolvXSI. Colors, typography, and logo are unapproved, so this document defines design rules and token categories without inventing final brand assets.

## Principles

1. **Status is obvious:** users can tell whether work is running, waiting for them, failed, or approved.
2. **Evidence is adjacent:** a claim and its supporting source can be inspected with minimal navigation.
3. **Control is explicit:** approvals, external actions, and policy blocks have clear actors and consequences.
4. **Complexity is progressive:** practitioners see the task; operators can reveal traces and diagnostics.
5. **History is stable:** prior outputs and decisions remain understandable after a workflow update.

## Token categories

| Category | Required tokens | Decision status |
| --- | --- | --- |
| Color | Surface, text, border, focus, success, warning, error, information. | Palette pending; verify contrast. |
| Type | Display, heading, body, label, code, citation. | Font family and sizes pending usability review. |
| Spacing | Compact, normal, spacious; content width and panel gap. | Scale pending interface prototype. |
| Shape | Card radius, control radius, divider, elevation. | Pending visual direction. |
| Motion | Loading, step transition, panel reveal, reduced-motion behavior. | Use only where state change benefits from motion. |

## Component set

| Component | Required variants or behavior |
| --- | --- |
| Button | Primary, secondary, destructive, disabled, loading. |
| Field | Label, help, validation, error, optional state. |
| Status badge | Text label plus visual cue for task and run state. |
| Step timeline | Current, complete, waiting, failed, skipped; keyboard navigable. |
| Evidence card | Source identity, passage, location, freshness, access state. |
| Claim marker | Supported, unsupported, conflicting, user edited. |
| Approval panel | Action summary, approver, policy reason, confirm and reject. |
| Artifact editor | Generated and user-edited versions, comments, citation navigation. |
| Data table | Sorting, filtering, empty state, accessible row actions. |
| Error panel | Error category, safe detail, recovery action, run ID. |

## Content patterns

Use task verbs: “Review plan,” “Open source,” “Approve report,” and “Retry step.” Avoid vague labels such as “Proceed” when an action has consequences. Label AI-generated content and explain confidence through evidence and limitations, not an unsupported percentage. State who approved an artifact and which workflow version produced it.

## Validation before visual sign-off

Prototype the task, evidence, and approval screens. Test them with practitioners using a representative report. Measure whether users can find an unsupported claim, open its source, and identify the next action. Check keyboard navigation, screen-reader labels, contrast, zoom, and reduced-motion behavior. Record final tokens only after the brand and UI review.
