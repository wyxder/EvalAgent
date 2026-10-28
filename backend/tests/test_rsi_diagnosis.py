"""Diagnosis must stay train-only and never leak holdout rows."""

import asyncio
from types import SimpleNamespace

from app.core.rsi_diagnosis import diagnose_failures
from app.core.rsi_policy import RowScore


def _loop():
    return SimpleNamespace(
        id=1,
        name="loop",
        dataset_id=1,
        scenario_id=1,
        llm_config_id=1,
        proposer_llm_config_id=None,
        objective_metric="faithfulness",
        objective_mode="reference_pass_rate",
    )


def _snapshot():
    return {
        "metrics": [
            {
                "id": 1,
                "pass_threshold": 0.7,
                "metric_definition": {
                    "id": 1,
                    "name": "faithfulness",
                    "display_name": "忠实度",
                    "metric_type": "numeric",
                    "config": {},
                },
            }
        ]
    }


def _rows():
    rows = []
    for row_id in range(1, 7):
        score = 0.4 if row_id <= 4 else 0.9
        rows.append(
            RowScore(
                row_id=row_id,
                row_index=row_id,
                is_pass=score >= 0.7,
                scores={"faithfulness": score},
                reasons={"faithfulness": "low" if score < 0.7 else "ok"},
            )
        )
    return rows


def test_diagnosis_fallback_only_counts_train_rows():
    result = asyncio.run(
        diagnose_failures(
            None,
            _loop(),
            _rows(),
            {"faithfulness": {"mean": 0.4}},
            _snapshot(),
            train_row_ids={1, 2, 3, 4},
            reference_thresholds={"faithfulness": 0.7},
            llm_config=None,
        )
    )

    assert result["fallback"] is True
    assert result["train_rows"] == 4
    assert result["failed_rows"] == 4
    assert set(result["sample_row_ids"]) == {1, 2, 3, 4}
    # Row 5/6 are the disabled-holdout rows and never enter the diagnosis.
    for cluster in result["clusters"]:
        assert 5 not in cluster["evidence_row_ids"]
        assert 6 not in cluster["evidence_row_ids"]


def test_llm_clusters_filter_holdout_evidence(monkeypatch):
    async def fake_call(*args, **kwargs):
        return (
            {
                "summary": "LLM 归因",
                "clusters": [
                    {
                        "label": "失败簇",
                        "root_cause_type": "prompt_ambiguity",
                        "affected_metric": "faithfulness",
                        "evidence_row_ids": [1, 2, 5, 6],
                        "suggested_lever": "prompt_override",
                        "severity": "high",
                    }
                ],
            },
            {"llm_calls": 1, "prompt_tokens": 10, "completion_tokens": 5},
        )

    monkeypatch.setattr("app.core.rsi_diagnosis.call_json_llm", fake_call)
    result = asyncio.run(
        diagnose_failures(
            None,
            _loop(),
            _rows(),
            {"faithfulness": {"mean": 0.4}},
            _snapshot(),
            train_row_ids={1, 2, 3, 4},
            reference_thresholds={"faithfulness": 0.7},
            llm_config=SimpleNamespace(api_key="test"),
        )
    )

    assert result["fallback"] is False
    assert result["clusters"][0]["evidence_row_ids"] == [1, 2]
    assert result["llm_usage"]["llm_calls"] == 1
