# Decision 0007: product name NortPole

Date: 2026-11-14. Status: **accepted** by the product owner.

## Decision

The product is called **NortPole** (one word, capital N and P; the spelling is deliberate). It replaces the working name
NortPole everywhere people see the product: the web app, notifications, skill text, the README, documents and
screenshots.

## Why this name

The owner wanted "North" in the name and a name no one else uses. North+, NorthX, NorthWave, North AI and NorthPole were
set aside: "North" alone is Cohere's competing product, NorthWave and North AI are used by other software companies, and
NorthPole is IBM's AI chip. A web search found no company or product called NortPole. That is not a trademark search:
check the trademark registers (software, classes 9 and 42) and the `.com` and `.ai` domains before launch.

## Done and not yet done

- **Step 1 (done):** the visible name, renamed by script wherever "NortPole" stood alone; a migration updates the one
  stored text that named it (a built-in skill description). The dated review log and applied migrations keep the old
  name as history, and links to the GitHub repository keep its current name.
- **Step 2 (done, pull request 103):** code names: the Python package `nortpole`, the test folders, `NortPole*`
  identifiers, `NORTPOLE_*` settings, `NortPole_*.md` documents, the pack SDK module `nortpole_pack_sdk` and the API
  description `nortpole-api.json`.
- **Step 3 (done by the owner, 2026-11-15):** the remaining names, including stored and shared ones: database tables,
  constraints and indexes (`nortpole_*`), stored setting keys, the `chat_session.nortpolebot_flow` column, the sign-in
  token audience, browser storage keys, the Postgres user and database names, image names and the Kubernetes namespace
  and labels; the GitHub repository is now `VenkataAnilKumar/NortPole`. No deployment existed, so no migration renames
  old tables: a database created before this step must be recreated, or have its tables, constraints, indexes, the
  column and the setting keys renamed by hand (done once for the sandbox). The fallbacks for the previous setting names
  were removed, since nothing set them any more.

## Product icon (2026-11-16)

The owner chose the **North Star**: a four-point guiding star with a long north–south axis, on the same 24×24 grid as
the previous mark and in one colour, so it follows the theme. It replaces the six-line asterisk in the sidebar and home,
the favicon, the logo and logotype images (which still showed the previous name as pixels), and the Craft web-app
template icons; a home-screen icon and a GitHub social preview were added. Files and uses are listed in
[the brand assets](../assets/brand/README.md).

## Colours (2026-11-16)

The owner chose the cool **Polar** palette. Tokens live in `apps/workspace/lib/shared/tokens` and compile to CSS
variables (the Opal library bundles its own copy, so rebuild `lib/shared` then `lib/opal`).

| Role | Value | Token | Where |
|---|---|---|---|
| North Navy | `#1f2a44` | `theme-primary-05`, `theme-brand-05` | Primary buttons and the mark in light mode, the sign-in sky |
| Polar Gold | `#e8b04b` | `theme-accent-05` | Mark and primary buttons in dark mode, the Inbox count, the selected sidebar row's edge, focus |
| Gold ink | `#8a5a0b` | `theme-accent-text-05` | Gold used as text on light surfaces |
| Aurora Teal | `#2bb3a3` | `theme-progress-05` | Progress and success (reserved; not yet used in screens) |

The sign-in pages sit on the navy sky (stars and a faint glow) in both modes. Neutral greys are unchanged, and status
colours (errors, warnings) keep their own tokens.

