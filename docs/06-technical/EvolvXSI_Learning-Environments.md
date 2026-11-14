# EvolvXSI — learning environments and controlled improvement

> **Where this lives in code (2026-11-14).** Service and package names here (`services/control-plane`, `services/execution`, `services/knowledge`, `packages/*`, `evaluations`) are logical owners from the design stage. [Decision 0006](../decisions/0006-scalable-repository-structure.md) maps them to the code: the three services are implemented inside `services/core`, and the packages and evaluations are planned modules in `modules.json`, created when their first code arrives.

Status: proposed capability; no implementation or training authorized · Updated: 2026-11-05

## Purpose and scope

Improve agents on repeated, measurable tasks using reproducible environments, recorded outcomes and controlled promotion. Instruction, skill and workflow experiments can operate with fixed provider models. Model-weight reinforcement learning is a separate later capability requiring an authorized training interface or trainable model, compute budget and evidence of benefit. An inference SDK alone does not enable model training.

The first release retains its existing scope. No automatic production self-modification is introduced. Candidate generation and training occur outside production; only evaluated, approved immutable versions can be activated.

## System boundary

Approved examples and feedback -> versioned task environment -> candidate execution -> verification and reward -> candidate improvement -> held-out evaluation -> human approval -> versioned release -> monitored rollout and rollback.

Execution runs the candidate through the same tool and policy contracts used by the platform, with simulated adapters and isolated storage. Training jobs have no production write credentials. Production observations enter datasets only through explicit authorization, tenant isolation, redaction and retention controls. Failures and corrections are evidence, not automatically trusted training labels.

## Environment contract

| Field | Required behavior |
| --- | --- |
| Identity | Environment/version, schema version, content digest and owner. |
| Task and state | Task specification, immutable initial-state snapshot, dataset/split ID, seed and reset procedure. |
| Observation | Agent-visible information only; hidden answers and verifier state cannot enter prompts. |
| Actions | Permitted tool schemas and versions, simulated responses, scoped permissions and policy constraints. |
| Step | Validate an action, update isolated state, return observation and recorded outcome. |
| Termination | Explicit success/failure, time/token/tool budgets and truncation reason. |
| Verification | Versioned deterministic checks, rubric, judge configuration and expert-review requirements. |
| Replay | Candidate/dependency versions, action/response trace, seeds, model identifiers, usage and cost. Seeds alone do not guarantee identical hosted-model outputs. |

Start with reset, step, verify and export-trajectory interfaces owned by contracts. Persist environment and dataset digests so a result can be traced to exact inputs. Replayed recorded responses provide repeatable regression tests; separate live integration tests establish real service compatibility.

## First candidate environment

A research-report scenario uses synthetic or explicitly approved documents, a question, search/read tools and report output. Include supported, conflicting, missing and access-denied evidence plus tool timeouts. Check citation resolution, evidence support, required report fields, unauthorized access and bounded tool use. Measure task completion, expert-assessed usefulness, latency and cost against a fixed baseline. Domain selection and thresholds remain P00/P09 decisions.

## Reward and promotion

Keep task success, evidence quality, cost and latency as separate reported dimensions. Use deterministic checks where ground truth is available; calibrate any model judge against expert-reviewed examples. A model judge's confidence is not ground truth. Fix reward and verifier versions before an experiment, and test for exploits such as citation stuffing, answer leakage and cheap incomplete answers.

Unauthorized disclosure, prohibited transmission and unapproved writes are hard gate failures; a high aggregate reward cannot offset them. Separate training, validation and held-out promotion sets by source/task families where needed to prevent near-duplicate leakage. Do not tune candidates repeatedly against the final held-out set.

Promotion requires comparison against the pinned baseline, predeclared thresholds and sample size, regression and policy checks, expert review where applicable, and an explicit control-plane approval bound to candidate, environment, dataset, dependency and result digests. Roll out gradually and retain the prior version for rollback. Training reward alone never authorizes publication.

## Ownership

| Repository | Responsibility |
| --- | --- |
| packages/contracts | Environment, episode, reward/result and candidate manifest schemas. |
| evaluations | Shared environment harness, simulation adapters, verifiers, independent held-out evaluation and reports. |
| services/execution | Candidate agent execution, isolation, budgets and trajectory events. |
| packages/agents and packages/skills | Versioned candidate definitions and approved packages. |
| packs/vertical/<domain> | Domain tasks, fixtures, tool simulations and expert-reviewed criteria. |
| services/control-plane | Dataset-use authorization, registry, publication gates and promotion/rollback decisions. |
| services/model-gateway | Approved inference routes and accounting for candidate and judge calls. |
| infrastructure | Isolated compute, storage, access policies and optional training resources. |
| services/learning (future, not created) | Training and optimization jobs, experiment lineage and candidate model artifacts if scope justifies a separate module. |

Evaluations remain independent of the optimizer: the candidate cannot alter the held-out verifier or its acceptance criteria. No new source repository or runtime dependency is selected by this proposal.

## Delivery gates

- P05-P06: establish deterministic environment fixtures, replayable trajectories and candidate comparisons alongside the evaluation runner. Test reset isolation, denied actions, tool failures and evaluator behavior.
- P09: implement one selected vertical environment with domain review, a fixed baseline and separated datasets. Demonstrate representative failure coverage before claiming improvement.
- P11 optional experiment: compare instruction/skill/workflow optimization with the baseline. Proceed to model RL only if simpler changes are insufficient and a trainable model, data authorization, compute budget and owner are confirmed.
- Model-training exit: held-out improvement and acceptable cost, no blocking regressions, expert acceptance, approved immutable release and tested rollback. No automatic production learning loop.

Open decisions: first domain/task, training rights and retention, reward rubric, judge calibration, dataset sizes, compute ceiling, model/interface and accountable learning owner. These are prerequisites for the relevant experiment, not invented defaults.

## Evaluation ownership

L09 owns held-out evaluation and records immutable evidence. L03 uses that evidence for publication and L04 applies data and access policy to candidate runs.
