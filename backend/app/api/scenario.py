from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.audit import record_audit
from app.core.database import get_db
from app.models.scenario import EvalScenario, ScenarioMetric
from app.models.metric_definition import MetricDefinition
from app.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioUpdate

router = APIRouter(prefix="/scenarios", tags=["Scenarios"])


def _scenario_snapshot(scenario: EvalScenario) -> dict:
    return {
        "name": scenario.name,
        "scene_type": scenario.scene_type,
        "sample_type": scenario.sample_type,
        "metrics": [
            {
                "metric_definition_id": item.metric_definition_id,
                "weight": item.weight,
                "pass_threshold": item.pass_threshold,
                "has_prompt_override": bool(item.prompt_override),
            }
            for item in (scenario.metrics or [])
        ],
    }


def _load_scenario_with_metrics(query):
    """Apply eager-loading of metrics and their metric_definition."""
    return query.options(
        joinedload(EvalScenario.metrics).joinedload(ScenarioMetric.metric_definition)
    )


def _validate_metric_definition(db: Session, metric_definition_id: int) -> MetricDefinition:
    metric_definition = (
        db.query(MetricDefinition)
        .filter(MetricDefinition.id == metric_definition_id)
        .first()
    )
    if not metric_definition:
        raise HTTPException(
            status_code=422,
            detail=f"MetricDefinition with id {metric_definition_id} not found",
        )
    return metric_definition


def _replace_scenario_metrics(
    db: Session, scenario: EvalScenario, metrics: list
) -> None:
    scenario.metrics.clear()
    db.flush()

    for metric_config in metrics:
        _validate_metric_definition(db, metric_config.metric_definition_id)
        db.add(
            ScenarioMetric(
                scenario_id=scenario.id,
                metric_definition_id=metric_config.metric_definition_id,
                weight=metric_config.weight,
                pass_threshold=metric_config.pass_threshold,
                prompt_override=(metric_config.prompt_override or "").strip() or None,
            )
        )


@router.get("/presets", response_model=List[ScenarioResponse])
def list_preset_scenarios(db: Session = Depends(get_db)):
    scenarios = (
        _load_scenario_with_metrics(db.query(EvalScenario))
        .filter(EvalScenario.is_preset == True)  # noqa: E712
        .all()
    )
    return scenarios


@router.get("", response_model=List[ScenarioResponse])
def list_scenarios(db: Session = Depends(get_db)):
    scenarios = _load_scenario_with_metrics(db.query(EvalScenario)).all()
    return scenarios


@router.post("", response_model=ScenarioResponse, status_code=201)
def create_scenario(payload: ScenarioCreate, db: Session = Depends(get_db)):
    scenario = EvalScenario(
        name=payload.name,
        description=payload.description,
        scene_type=payload.scene_type,
        sample_type=payload.sample_type,
        is_preset=False,
    )
    db.add(scenario)
    db.flush()  # get scenario.id

    _replace_scenario_metrics(db, scenario, payload.metrics)

    db.commit()

    # Reload with relationships
    scenario = (
        _load_scenario_with_metrics(
            db.query(EvalScenario).filter(EvalScenario.id == scenario.id)
        )
        .first()
    )
    record_audit(
        db,
        action="scenario.create",
        target_type="scenario",
        target_id=scenario.id,
        after_value=_scenario_snapshot(scenario),
    )
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: int, payload: ScenarioUpdate, db: Session = Depends(get_db)
):
    scenario = (
        _load_scenario_with_metrics(
            db.query(EvalScenario).filter(EvalScenario.id == scenario_id)
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.is_preset:
        raise HTTPException(
            status_code=400, detail="Cannot edit a preset scenario"
        )

    before_value = _scenario_snapshot(scenario)
    scenario.name = payload.name
    scenario.description = payload.description
    scenario.scene_type = payload.scene_type
    scenario.sample_type = payload.sample_type
    _replace_scenario_metrics(db, scenario, payload.metrics)
    db.commit()

    scenario = (
        _load_scenario_with_metrics(
            db.query(EvalScenario).filter(EvalScenario.id == scenario_id)
        )
        .first()
    )
    record_audit(
        db,
        action="scenario.update",
        target_type="scenario",
        target_id=scenario_id,
        before_value=before_value,
        after_value=_scenario_snapshot(scenario),
    )
    return scenario


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = (
        _load_scenario_with_metrics(
            db.query(EvalScenario).filter(EvalScenario.id == scenario_id)
        )
        .first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario


@router.delete("/{scenario_id}", status_code=204)
def delete_scenario(scenario_id: int, db: Session = Depends(get_db)):
    scenario = (
        db.query(EvalScenario).filter(EvalScenario.id == scenario_id).first()
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.is_preset:
        raise HTTPException(
            status_code=400, detail="Cannot delete a preset scenario"
        )
    before_value = _scenario_snapshot(scenario)
    db.delete(scenario)
    db.commit()
    record_audit(
        db,
        action="scenario.delete",
        target_type="scenario",
        target_id=scenario_id,
        before_value=before_value,
    )
    return None
