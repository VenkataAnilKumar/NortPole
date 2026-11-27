# NortPole Inbox and Projects

## Product research

| Platform | Relevant product behavior | NortPole application |
| --- | --- | --- |
| Glean | Agent Inbox surfaces tool requests that require a decision. Projects gather chats, files and instructions and can be shared with view or edit access. Connected content follows its existing permissions. [Agent Inbox](https://docs.glean.com/tools/human-in-the-loop-experience-for-tools) · [Projects](https://docs.glean.com/user-guide/knowledge/projects/how-projects-work) | Give each pending decision one entry point. Keep a project private by default and preserve source access when adding collaboration. |
| Cohere North | North combines agents, workflows and enterprise content. Automations monitor events and produce updates. [Automations](https://cohere.com/north/automations) | Link updates from Inbox to the workflow run that produced them. |
| Hebbia | Projects organize ongoing work and let users publish findings from private workspaces. [Projects](https://www.hebbia.com/blog/introducing-projects) | Keep project context private and let users deliberately share completed outputs through Knowledge. |
| WRITER | Notifications cover events that can be addressed from the workspace. Projects group agent chats and their context. [Notifications](https://support.writer.com/articles/5075784499-managing-your-notifications) · [Projects](https://support.writer.com/articles/1970650387-organizing-writer-agent-with-projects) | Keep pending work and status updates easy to scan. Make the effect of project context visible when moving a chat. |
| Microsoft Power Automate | Reviewers can approve or reject workflow requests in the approvals center. [Approvals](https://learn.microsoft.com/en-us/power-automate/approve-reject-requests) | Store a receipt for a workflow decision and direct the reviewer back to its source. |

## Requirements

1. **Inbox.** Show each pending workflow plan or draft once in To approve or To review. Show operational updates such as failures separately. Open the exact run, task, or result when the notification carries its identifier. Keep workflow decisions in history with the reviewed version and exclude them from active counts.
2. **Projects.** Keep chats, files, instructions and saved outputs in a private workspace. Before moving a chat, show the destination, the context future turns can use, and the effect on access. Cancelling a move leaves the chat in place. Cancelling Create project and move also leaves the project list intact.
3. **Access.** Check ownership at the service boundary. Block project mutations for deleted and incognito chats. Preserve a moved chat’s agent and existing link permissions. Sharing a finished output continues through Add to Knowledge and its audience confirmation.
4. **Packs.** Apply the same Inbox and project rules to common workflows and domain packs. Agents remain a later feature area.

## Design and architecture

Inbox keeps To approve, To review, and Updates. Workflow history is available from Updates. Its items show when a plan or draft became available or when the owner made a decision. Pending workflow rows come from the existing waiting-task endpoint. Workflow completion notices with a linked draft go to history. Standalone completions, failures and actionable result reviews stay in the active feeds. A known run ID opens the selected entry in Workflows → Runs. A workflow decision receipt opens the task and records the reviewed version. The task view shows the current state.

The task service already checks the owner, current state, and version in a conditional update. It writes a private receipt in the same transaction when a plan or draft is accepted, approved, returned for editing, or cancelled from review. Recording the receipt in that transaction gives one receipt for one successful decision. Existing notification storage supports the new type without a schema migration. Older ready notices can appear in history. Decision receipts begin with this change.

**Projects** opens a searchable project list with **New Project**. Open a card to enter the project workspace, where members can find its chats, files, instructions, and outputs. Owners can delete a project from the list after confirmation.

Projects use one move confirmation for the chat header, the chat menu in Recents, and the project chat list. The move updates the project association. Future replies can use the destination’s files and instructions through the existing chat pipeline. The backend checks the destination project and uses a conditional update for the owner’s eligible chat. Create project and move writes both changes in one transaction. Project outputs continue to use the owner-scoped store. Add to Knowledge uses the existing destination check to confirm the sharing audience.

## Issues fixed

| Issue | Change |
| --- | --- |
| A scheduled plan or draft could show as both a waiting task and an update, inflating the active badge. | Workflow ready notices move to history. The task supplies the active row and count. |
| A decision disappeared from Inbox after the owner acted, and some links routed through the schedule list. | A private versioned receipt remains in Inbox. Run updates open the selected run directly. |
| Move confirmation applied only to custom agents and described the wrong effect. | Every move into a project shows the destination, context and access impact. |
| Cancelling a move into a new project could leave an empty project. A failed move could still navigate there. | Creation starts at confirmation. A failed move rolls back creation. Navigation follows a successful move. |
| Direct move and remove requests could change project associations on hidden chats. | The write excludes incognito, deleted, child and other users’ chats. |

## Tests and review

- **Backend.** 30 PostgreSQL integration tests passed, covering notification privacy, filtering and pagination, scheduled plan and draft decisions, a stale approval retry, project permissions, atomic create-and-move, and saved output access and Knowledge contribution.
- **Workspace.** The full workspace TypeScript check and 29 focused Jest tests passed. The tests cover Inbox counts and links, project provider behavior, and translation catalog parity.
- **Chromium.** With seeded records and the live API, the browser showed one pending plan, accepted it, displayed the decision receipt, and opened the exact failed run. It cancelled a project move, moved a chat into an existing project, and created a project and moved a chat into it in one request. PostgreSQL confirmed the recorded decision and both moves, and confirmed that cancelling created no project.

## Shared Projects

Projects start private. The project owner can add active workspace accounts by email, change their role, and remove access. Grants apply to the signed-in workspace account. Shared projects appear in the member’s **Projects** list.

| Capability | Owner | Editor | Viewer |
| --- | --- | --- | --- |
| Open the project, instructions, files, saved outputs, and chat transcripts | Yes | Yes | Yes |
| Rename the project, update instructions, manage file associations, and save outputs | Yes | Yes | |
| Start a project chat or move an eligible chat you own into the project | Yes | Yes | |
| Manage membership or delete the project | Yes | | |

People with project access can open read-only transcripts of one another’s chats. The transcript shows the conversation text from the current branch. Tool traces and chat-only attachments stay with the original chat. Project files can be downloaded from a project-scoped link. Files that exist only in a personal file list and documents from connected Knowledge retain their own access rules. The sharing dialog explains that project chat transcripts can include quoted material.

When a member loses Editor access, the chats they started return to their personal chat history in the same transaction as the membership change. Project files and saved outputs contributed while editing stay in the project. The owner can see this behavior before confirming the role change or removal. Existing public chat links must be turned off before adding members. A shared project uses project-scoped links for its chats.

The tenant migration adds a project membership table keyed by project and user. Project operations resolve the role at the API boundary. Membership changes and project writes that depend on the role serialize on the project row. The transcript and download endpoints check the current member, the project association, and the item’s privacy state on every request. Downloads use private, non-cacheable responses. Individual chat mutations continue to use the chat owner check. Member access grants leave Knowledge’s underlying document permissions in place.

Additional Inbox history can cover other decision families once their own records support it. Agents follow the Inbox and Projects work.

### Shared Projects verification

The membership migration applied to the local workspace. The workspace TypeScript check, 17 focused frontend tests, and 68 backend tests passed. Backend coverage includes owner-only grants, viewer and editor permissions, personal file boundaries, public chat link restrictions, role downgrades, and project access after removal.

In Chromium, an owner added two workspace accounts and removed the viewer. The viewer opened a read-only transcript and a saved output preview. The live API served the linked file and then denied the removed account’s project, transcript, file, and saved output requests. The editor’s output edit succeeded, while attempts to delete the project or list its members were denied.
