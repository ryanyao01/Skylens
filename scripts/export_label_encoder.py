"""Export models/label_encoder.pkl to models/label_encoder.json.

Run after retraining, whenever label_encoder.pkl is regenerated:

    python scripts/export_label_encoder.py

The API reads the JSON so that scikit-learn is not a runtime dependency and so
that loading never trips sklearn's InconsistentVersionWarning. Requires the
`offline` extra (scikit-learn).
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PICKLE_PATH = PROJECT_ROOT / "models" / "label_encoder.pkl"
JSON_PATH = PROJECT_ROOT / "models" / "label_encoder.json"


def main() -> int:
    with open(PICKLE_PATH, "rb") as f:
        encoder = pickle.load(f)

    classes = [str(c) for c in encoder.classes_]
    mapping = {code: index for index, code in enumerate(classes)}

    # A LabelEncoder is a sorted-class lookup; assert the dict is equivalent
    # before we let the API depend on it.
    for code in classes:
        expected = int(encoder.transform([code])[0])
        if mapping[code] != expected:
            print(f"MISMATCH for {code}: {mapping[code]} != {expected}", file=sys.stderr)
            return 1

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, sort_keys=True)

    print(f"wrote {JSON_PATH} ({len(mapping)} classes, verified against pickle)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
