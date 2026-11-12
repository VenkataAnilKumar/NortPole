"""How often the instruction flag fires on the hostile set (recall) and on benign passages (false alarms).
No model is called. PYTHONPATH=. python scripts/injection_flag_report.py"""

import json
from pathlib import Path

from evolvxsi.tasks.untrusted import looks_like_instructions

D = Path(__file__).parent
hostile = json.loads((D / "injection_cases.json").read_text())["cases"]
benign = json.loads((D / "injection_benign.json").read_text())["passages"]


def report() -> dict:
    caught = [c["id"] for c in hostile if looks_like_instructions(c["passage"])]
    alarms = [b for b in benign if looks_like_instructions(b)]
    return {"hostile": len(hostile), "caught": len(caught), "missed": [c["id"] for c in hostile if c["id"] not in caught],
            "benign": len(benign), "false_alarms": len(alarms), "alarm_texts": alarms}


if __name__ == "__main__":
    r = report()
    print(f"hostile caught {r['caught']}/{r['hostile']} | false alarms {r['false_alarms']}/{r['benign']}")
    print("missed:", r["missed"])
    for a in r["alarm_texts"]:
        print("  false alarm:", a[:90])
