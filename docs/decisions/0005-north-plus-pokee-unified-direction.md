# Decision 0005 — North's governed workspace plus Pokee-style action agents

Status: **proposed** · Date: 2026-11-11

## Context

The product direction so far follows Cohere North: a governed workspace with knowledge sources, permissions, audit and vertical packs. The owner asked for a combination of North and Pokee as one product.

Source for Pokee: the vendor's own home page (pokee.ai, read 2026-11-11). These are marketing claims. Nothing here was measured or tested by EvolvXSI, and numbers on that page are the vendor's own.

What the page says Pokee is:

- An enterprise agent platform deployed inside the customer's boundary: Pokee-managed tenant, the customer's VPC, on premises, air-gapped or on device (the last two on request).
- Its own model family (Pokee-Isaac, a long-context model) and an agent harness described as plan, act, verify, cite, trained with reinforcement learning across nine enterprise verticals.
- One-click sign-in connections to 90+ apps ("1000s of tools") so agents act across a company's tools.
- Verticals as a selling point (finance, health care, e-commerce, legal, education, manufacturing).
- A pilot of two to three real workflows on the customer's data.

## Decision

Build one product with two layers:

1. **Governed workspace (North side, mostly built):** home, search, libraries, inbox, route policy, audit, settings, packs.
2. **Action agents (Pokee side, to build):** agents that carry out multi-step work across connected apps inside the workspace's rules.

The action layer is not allowed to bypass the governed layer. Every outward action is a named step that:

- is checked against the route policy and the user's own access before any content is sent;
- needs an approval bound to that exact action and payload where the pack requires it, with an idempotency key;
- is written to the audit trail and shown in the inbox.

EvolvXSI does not train or ship its own model. Hybrid routing stays the way models are chosen: local, private or cloud, inside administrator policy.

## What changes in the delivery plan

- A5 (knowledge and permissions) stays first: agents act on data the user may see.
- A6 becomes the centre of the product: approval-gated actions, run history, replay and retry, with the inbox tying each approval to one action.
- A7 treats connectors as actions as well as sources, with per-pack allow-lists of permitted actions.
- A8 needs real model access before agent quality can be judged; until then the approval flow is tested against mock routes.
- A10 keeps deployment options (managed, customer cloud, on premises) in scope, matching the hybrid promise.

## Not decided

- Which apps come first as action targets (needs the first customer and vertical).
- Whether to build the connector catalogue ourselves or reuse the adapted source connectors for actions.
- Whether any claim from Pokee's page is reflected in our own marketing. None should be, without our own evidence.
