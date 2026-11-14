import type { Metadata, Route } from "next";
import Link from "next/link";

// In-product help. Help links across the workspace (connector setup, the About page, error pages) point
// here as /help/<topic>; the page gives the essentials and where a deployment's own guides live.
const TOPICS: { title: string; body: string; href?: Route; link?: string }[] = [
  {
    title: "Ask and run workflows",
    body: "Ask a question in New, or pick a workflow under Workflows. Review the plan, check the cited draft, then approve one exact version before it is exported or sent.",
    href: "/app/workflows",
    link: "Open Workflows",
  },
  {
    title: "Your Inbox",
    body: "To approve holds plans and approvals waiting for you, To review holds drafts that are ready, and Updates holds decisions on your requests.",
    href: "/app/inbox",
    link: "Open Inbox",
  },
  {
    title: "Knowledge and sources",
    body: "Answers only use documents you are allowed to open in the source system. Use Sources, then Discover, to ask for a connector, skill or tool that is not switched on yet.",
    href: "/app/sources/discover",
    link: "Open Discover",
  },
  {
    title: "For administrators",
    body: "Connectors, route policy and redaction, approvals, retention, the audit log and scheduling are in the admin console. Setup and operating guides ship with your deployment.",
    href: "/admin/overview",
    link: "Open the admin console",
  },
];

export const metadata: Metadata = { title: "Help · NortPole" };

export default function HelpPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <h1 className="text-xl font-semibold text-text-05">NortPole help</h1>
        <p className="text-sm text-text-03">
          The essentials of using NortPole. For anything specific to your
          organisation, such as which sources are connected or who approves
          requests, ask your administrator.
        </p>
      </header>
      <ul className="flex flex-col gap-3">
        {TOPICS.map((topic) => (
          <li
            key={topic.title}
            className="flex flex-col gap-1 rounded-12 border border-border-01 p-4"
          >
            <h2 className="text-base font-semibold text-text-05">
              {topic.title}
            </h2>
            <p className="text-sm text-text-03">{topic.body}</p>
            {topic.href && (
              <Link
                href={topic.href}
                className="mt-1 inline-flex min-h-11 items-center text-sm font-medium text-text-05 underline"
              >
                {topic.link}
              </Link>
            )}
          </li>
        ))}
      </ul>
    </main>
  );
}
