import { useEffect, useId, useState, type FormEvent } from "react";
import { useTranslations } from "next-intl";
import { Button, InputCheckbox, InputTextArea, InputTypeIn, NativeSelect } from "@opal/components";
import { Section } from "@opal/layouts";
import type { ComposerSelection } from "@/app/app/types";
import { PilotDocumentPicker } from "@/sections/input/PilotDocumentPicker";

const thresholdComparisons = ["gt", "gte", "lt", "lte"] as const;
type ThresholdComparison = (typeof thresholdComparisons)[number];

interface Rule {
  questions: string[];
  action: string;
  conditions: Record<string, string>;
  answer_field: string;
  value: string;
  unit: string | null;
  threshold_comparison?: ThresholdComparison | null;
  excerpt: string;
  source: { document_id: string; chunk_id: number };
}

interface RuleView {
  id: string;
  source_title: string;
  rule: Rule | null;
}

interface RuleList {
  enabled: boolean;
  rules: RuleView[];
}

export default function PolicyRulesPanel({ id, name }: { id: number; name: string }) {
  const t = useTranslations("knowledge.policyRules");
  const [open, setOpen] = useState(false);
  return (
    <details className="rounded-lg border border-border-01 p-3" onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer font-semibold text-text-05">{t("title")}</summary>
      {open && <PolicyRulesEditor id={id} name={name} />}
    </details>
  );
}

function PolicyRulesEditor({ id, name }: { id: number; name: string }) {
  const t = useTranslations("knowledge.policyRules");
  const fieldId = useId();
  const endpoint = `/api/manage/admin/document-set/${id}/policy-rules`;
  const [data, setData] = useState<RuleList>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState<RuleView | "new" | null>(null);
  const [selection, setSelection] = useState<ComposerSelection[]>([]);
  const initial = editing && editing !== "new" ? editing.rule : null;

  useEffect(() => {
    const controller = new AbortController();
    void fetch(endpoint, { cache: "no-store", signal: controller.signal }).then(async (response) => {
      if (!response.ok) throw new Error();
      setData(await response.json());
    }).catch(() => {
      if (!controller.signal.aborted) setError(t("loadFailed"));
    });
    return () => controller.abort();
  }, [endpoint, attempt, t]);

  function edit(value: RuleView | "new" | null) {
    const rule = value && value !== "new" ? value.rule : null;
    setSelection(rule && value && value !== "new" ? [{
      kind: "search-result",
      id: rule.source.document_id,
      chunkId: rule.source.chunk_id,
      label: value.source_title,
    }] : []);
    setError("");
    setEditing(value);
  }

  async function mutate(
    method: "PATCH" | "POST" | "PUT" | "DELETE",
    suffix: string,
    body: Rule | { enabled: boolean } | undefined,
    apply: (response: Response) => Promise<void>,
  ) {
    setBusy(true);
    setError("");
    try {
      const response = await fetch(endpoint + suffix, {
        method,
        headers: { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) {
        const problem = await response.json().catch(() => null);
        throw new Error(typeof problem?.detail === "string" ? problem.detail : t("invalidRule"));
      }
      await apply(response);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t("saveFailed"));
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const source = selection[0];
    if (!source || source.kind !== "search-result" || source.chunkId == null) {
      setError(t("selectPassage"));
      return;
    }
    const form = new FormData(event.currentTarget);
    const get = (key: string) => String(form.get(key) ?? "").trim();
    const lines = (key: string) => get(key).split("\n").map((line) => line.trim()).filter(Boolean);
    const pairs = lines("conditions").map((line) => {
      const separator = line.indexOf("=");
      return separator < 0 ? ["", ""] : [line.slice(0, separator).trim(), line.slice(separator + 1).trim()];
    });
    const conditions = Object.fromEntries(pairs);
    if (pairs.some(([key, value]) => !key || !value) || Object.keys(conditions).length !== pairs.length) {
      setError(t("invalidConditions"));
      return;
    }
    const rule: Rule = {
      questions: lines("questions"), action: get("action"), conditions,
      answer_field: get("answer_field"), value: get("value"), unit: get("unit") || null,
      threshold_comparison: thresholdComparisons.find((item) => item === get("threshold_comparison")) ?? null,
      excerpt: get("excerpt"), source: { document_id: source.id, chunk_id: source.chunkId },
    };
    const ruleId = editing && editing !== "new" ? editing.id : null;
    void mutate(ruleId ? "PUT" : "POST", ruleId ? `/${ruleId}` : "", rule, async (response) => {
      const result: RuleView = await response.json();
      setData((current) => current && {
        ...current,
        rules: ruleId ? current.rules.map((item) => item.id === ruleId ? result : item) : [...current.rules, result],
      });
      edit(null);
    });
  }

  return (
    <Section className="mt-3 text-sm text-text-05" height="auto" alignItems="stretch" gap={3}>
      {error && <p role="alert" className="break-words">{error}</p>}
      {!data ? (
        error ? <Button size="sm" onClick={() => { setError(""); setAttempt(attempt + 1); }}>{t("retry")}</Button>
          : <p role="status">{t("loading")}</p>
      ) : (
        <>
          <Section flexDirection="row" justifyContent="start" gap={2} height="auto">
            <InputCheckbox id={fieldId + "-mode"} aria-label={t("mode")} checked={data.enabled} disabled={busy}
              onCheckedChange={(enabled) => {
                void mutate("PATCH", "", { enabled }, async () => {
                  setData((current) => current && { ...current, enabled });
                });
              }}
            />
            <label htmlFor={fieldId + "-mode"}>{t("mode")}</label>
          </Section>
          <p className="text-text-03">
            {t("description")}
          </p>
          {!data.rules.length && <p className="text-text-03">{t("empty")}</p>}
          {!!data.rules.length && <ul className="divide-y divide-border-01">
            {data.rules.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <div className="min-w-0 break-words">
                  <div className="font-medium">{item.rule?.questions[0] ?? t("sourceChanged")}</div>
                  <div className="text-text-03">{item.source_title}</div>
                </div>
                <Section flexDirection="row" width="fit" height="auto" gap={2}>
                  <Button size="sm" prominence="secondary" disabled={busy} onClick={() => edit(item)}>
                    {item.rule ? t("edit") : t("replace")}
                  </Button>
                  <Button size="sm" prominence="secondary" disabled={busy} onClick={() => {
                    void mutate("DELETE", `/${item.id}`, undefined, async () => {
                      setData((current) => current && { ...current, rules: current.rules.filter((rule) => rule.id !== item.id) });
                      if (editing === item) edit(null);
                    });
                  }}>{t("remove")}</Button>
                </Section>
              </li>
            ))}
          </ul>}
          {!editing ? <Button size="sm" prominence="secondary" disabled={busy} onClick={() => edit("new")}>{t("add")}</Button> : (
            <form key={editing === "new" ? "new" : editing.id} onSubmit={save}
              className="flex flex-col gap-3 border-t border-border-01 pt-3">
              <Section height="auto" alignItems="stretch" gap={1}>
                <label htmlFor={fieldId + "-comparison"}>{t("thresholdComparison")}</label>
                <NativeSelect id={fieldId + "-comparison"} name="threshold_comparison"
                  aria-describedby={fieldId + "-threshold-help"} defaultValue={initial?.threshold_comparison ?? ""}>
                  <option value="">{t("literalAnswer")}</option>
                  {thresholdComparisons.map((option) => <option key={option} value={option}>{t(option)}</option>)}
                </NativeSelect>
                <p id={fieldId + "-threshold-help"} className="text-text-03">
                  {t("thresholdHelp", { amount: "{amount}" })}
                </p>
              </Section>
              <Section height="auto" alignItems="stretch" gap={1}>
                <label htmlFor={fieldId + "-questions"}>{t("questions")}</label>
                <InputTextArea id={fieldId + "-questions"} name="questions" required rows={3}
                  defaultValue={initial?.questions.join("\n")} />
              </Section>
              <Section height="auto" alignItems="stretch" gap={1}>
                <label htmlFor={fieldId + "-action"}>{t("action")}</label>
                <InputTypeIn id={fieldId + "-action"} name="action" required maxLength={160} defaultValue={initial?.action} />
              </Section>
              <Section height="auto" alignItems="stretch" gap={1}>
                <label htmlFor={fieldId + "-conditions"}>{t("conditions")}</label>
                <InputTextArea id={fieldId + "-conditions"} name="conditions" rows={2}
                  defaultValue={Object.entries(initial?.conditions ?? {}).map(([key, value]) => `${key}=${value}`).join("\n")} />
              </Section>
              <Section height="auto" alignItems="stretch" gap={1}>
                <label htmlFor={fieldId + "-answer-field"}>{t("answerField")}</label>
                <InputTypeIn id={fieldId + "-answer-field"} name="answer_field" required maxLength={160} defaultValue={initial?.answer_field} />
              </Section>
              <Section flexDirection="row" height="auto" alignItems="stretch" gap={2} wrap>
                <Section className="min-w-32 flex-1" height="auto" alignItems="stretch" gap={1}>
                  <label htmlFor={fieldId + "-answer"}>{t("answer")}</label>
                  <InputTypeIn id={fieldId + "-answer"} name="value" required maxLength={160} defaultValue={initial?.value} />
                </Section>
                <Section className="min-w-32 flex-1" height="auto" alignItems="stretch" gap={1}>
                  <label htmlFor={fieldId + "-unit"}>{t("unit")}</label>
                  <InputTypeIn id={fieldId + "-unit"} name="unit" maxLength={160} defaultValue={initial?.unit ?? ""} />
                </Section>
              </Section>
              <PilotDocumentPicker libraries={[{ id, name }]} selected={selection} disabled={busy}
                onToggle={(item) => setSelection((current) => current[0]?.id === item.id ? [] : [item])} />
              {selection[0] && <p className="break-words text-text-03">{t("selected", { title: selection[0].label ?? "" })}</p>}
              <Section height="auto" alignItems="stretch" gap={1}>
                <label htmlFor={fieldId + "-excerpt"}>{t("excerpt")}</label>
                <InputTextArea id={fieldId + "-excerpt"} name="excerpt" required maxLength={800} rows={3}
                  defaultValue={initial?.excerpt} />
              </Section>
              <Section flexDirection="row" width="fit" height="auto" gap={2}>
                <Button type="submit" size="sm" disabled={busy}>{t("save")}</Button>
                <Button type="button" size="sm" prominence="secondary" disabled={busy} onClick={() => edit(null)}>{t("cancel")}</Button>
              </Section>
            </form>
          )}
        </>
      )}
    </Section>
  );
}
