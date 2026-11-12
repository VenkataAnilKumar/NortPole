"""The licence screen: what it denies, what needs a recorded decision, what passes."""

import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1] / "licenses"
_spec = importlib.util.spec_from_file_location("check_licenses", HERE / "check_licenses.py")
cl = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(cl)  # type: ignore[union-attr]


def test_permissive_licences_pass() -> None:
    for lic in ["MIT", "MIT License", "Apache-2.0", "Apache Software License", "BSD-3-Clause", "BSD License", "ISC", "Python Software Foundation License", "(Apache-2.0 AND MIT)"]:
        assert cl.classify(lic) == "ok", lic


def test_strong_copyleft_and_use_restrictions_are_denied() -> None:
    for lic in ["AGPL-3.0", "GNU Affero General Public License v3", "SSPL-1.0", "Server Side Public License", "BUSL-1.1", "Business Source License 1.1",
                "Other/Proprietary License", "Commons Clause", "CC-BY-NC-4.0", "Elastic License 2.0"]:
        assert cl.classify(lic) == "deny", lic


def test_lgpl_gpl_mpl_and_unknown_need_a_human_decision() -> None:
    for lic in ["GNU Lesser General Public License v3 (LGPLv3)", "LGPL-2.1-or-later", "GNU General Public License v3", "MPL-2.0", "UNKNOWN", ""]:
        assert cl.classify(lic) == "review", lic


def test_a_dual_licence_with_a_permissive_choice_passes_but_not_when_only_copyleft_is_offered() -> None:
    assert cl.classify("MIT OR GPL-2.0-only") == "ok"
    assert cl.classify("Apache-2.0 OR LGPL-2.1-or-later") == "ok"
    assert cl.classify("GPL-2.0-only OR LGPL-2.1-or-later") == "review"


def test_a_reviewed_package_is_accepted_and_an_unreviewed_one_fails() -> None:
    pk = [{"name": "Some_Lib", "version": "1", "license": "LGPL-3.0"}, {"name": "other", "version": "2", "license": "LGPL-3.0"},
          {"name": "bad", "version": "3", "license": "AGPL-3.0"}, {"name": "fine", "version": "4", "license": "MIT"}]
    deny, unreviewed, accepted = cl.check(pk, {"some-lib": "reason"})
    assert [p["name"] for p in deny] == ["bad"] and [p["name"] for p in unreviewed] == ["other"] and [p["name"] for p in accepted] == ["Some_Lib"]


def test_every_recorded_decision_has_a_reason() -> None:
    d = json.loads((HERE / "reviewed.json").read_text())["packages"]
    assert d and all(len(v) > 20 for v in d.values())
