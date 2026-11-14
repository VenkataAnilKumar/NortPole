# Decision 0007: product name NortPole

Date: 2026-11-14. Status: **accepted** by the product owner.

## Decision

The product is called **NortPole** (one word, capital N and P; the spelling is deliberate). It replaces the working name
EvolvXSI everywhere people see the product: the web app, notifications, skill text, the README, documents and
screenshots.

## Why this name

The owner wanted "North" in the name and a name no one else uses. North+, NorthX, NorthWave, North AI and NorthPole were
set aside: "North" alone is Cohere's competing product, NorthWave and North AI are used by other software companies, and
NorthPole is IBM's AI chip. A web search found no company or product called NortPole. That is not a trademark search:
check the trademark registers (software, classes 9 and 42) and the `.com` and `.ai` domains before launch.

## Done and not yet done

- **Step 1 (done):** the visible name, renamed by script wherever "EvolvXSI" stood alone; a migration updates the one
  stored text that named it (a built-in skill description). The dated review log and applied migrations keep the old
  name as history, and links to the GitHub repository keep its current name.
- **Step 2 (planned):** code names (the `evolvxsi` Python package, `EVOLVXSI_*` settings, classes such as
  `EvolvXSIError`, document file names) and the repository's own name. These change nothing people see and need a
  coordinated change of deployment settings, so they follow separately.
