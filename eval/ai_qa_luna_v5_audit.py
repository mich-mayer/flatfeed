from __future__ import annotations

import json
from pathlib import Path

from eval.ai_qa_luna_v4_audit import build_failure_audit, render_markdown
from eval.ai_qa_luna_v5_cycle import DEFAULT_LUNA_V5_DATASET_DIR, LUNA_V5_WBS_PHRASES
from eval.ai_qa_scorer import load_jsonl


RUN_DIR = Path(__file__).with_name("runs") / "luna-v5-calibration"


def main() -> None:
    audit = build_failure_audit(
        input_rows=load_jsonl(
            DEFAULT_LUNA_V5_DATASET_DIR / "calibration_model_inputs.jsonl"
        ),
        truth_rows=load_jsonl(
            DEFAULT_LUNA_V5_DATASET_DIR / "calibration_truth.jsonl"
        ),
        prediction_rows=load_jsonl(RUN_DIR / "predictions.jsonl"),
        wbs_phrases=LUNA_V5_WBS_PHRASES,
        cycle_label="Luna-v5",
    )
    json_path = RUN_DIR / "failure_audit.json"
    markdown_path = RUN_DIR / "failure_audit.md"
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(audit), encoding="utf-8")
    print(
        json.dumps(
            {"json": str(json_path), "markdown": str(markdown_path)},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
