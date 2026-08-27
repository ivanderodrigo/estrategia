from __future__ import annotations
from pathlib import Path
import json

def validate(root:Path):
    errors=[];req=["ecosystem_profiles.json","integrator_vendor_matrix.json","distributor_vendor_matrix.json","vendor_pair_intelligence.json","architectures.json","coverage_report.json","research_plan.json","relationship_verification_queue.json","deduplication_report.json","relationship_movement.json","targeted_evidence.json","last_run.json"]
    for n in req:
        p=root/"data/v33"/n
        if not p.exists():errors.append(f"Falta data/v33/{n}");continue
        try:json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:errors.append(f"JSON inválido {n}: {exc}")
    p=root/"data/v33/ecosystem_profiles.json"
    if p.exists():
        d=json.loads(p.read_text(encoding="utf-8"));profiles=d.get("profiles")
        if not isinstance(profiles,list):
            errors.append("ecosystem_profiles.json sin colección profiles aplanada")
            # Validate legacy-shaped rows too, so the provenance gate cannot be
            # bypassed merely by omitting the flattened collection.
            profiles=(d.get("integrators") or [])+(d.get("distributors") or [])
        keys=set()
        for x in profiles:
            if not x.get("name"):errors.append("Perfil sin name");continue
            k=(x.get("entity_type"),str(x.get("name")).strip().lower())
            if k in keys:errors.append(f"Perfil duplicado exacto: {x.get('entity_type')} {x.get('name')}")
            keys.add(k)
            if not isinstance(x.get("provenance"),dict):errors.append(f"{x.get('name')} sin provenance")
            if x.get("coverage_score") is None or x.get("coverage_target") is None or x.get("coverage_gap") is None:errors.append(f"{x.get('name')} sin métricas de cobertura objetivo")
            if x.get("entity_tier") not in {"T1","T2","T3"}:errors.append(f"{x.get('name')} sin tier válido")
            if x.get("strategic_importance_score") is None:errors.append(f"{x.get('name')} sin importancia estratégica")
            if not isinstance(x.get("operations"),list):errors.append(f"{x.get('name')} sin operaciones/ámbitos preservados")
            if not x.get("evidence_grade"):errors.append(f"{x.get('name')} sin evidence_grade")
    im=root/"data/v33/integrator_vendor_matrix.json"
    if im.exists():
        d=json.loads(im.read_text(encoding="utf-8"))
        for x in (d.get("rows") or [])[:250]:
            if x.get("priority_score") is None or x.get("relationship_intensity") is None:errors.append("Matriz integrador×fabricante sin prioridad/intensidad");break
    dm=root/"data/v33/distributor_vendor_matrix.json"
    if dm.exists():
        d=json.loads(dm.read_text(encoding="utf-8"))
        for x in (d.get("rows") or [])[:250]:
            if not x.get("status") or x.get("relationship_intensity") is None:errors.append("Matriz mayorista×fabricante sin status/intensidad");break
    te=root/"data/v33/targeted_evidence.json"
    if te.exists():
        d=json.loads(te.read_text(encoding="utf-8"));m=d.get("meta") or {}
        if m.get("cumulative_evidence") is None or m.get("new_evidence") is None:errors.append("targeted_evidence sin métricas acumulativas")
    dd=root/"data/v33/deduplication_report.json"
    if dd.exists():
        d=json.loads(dd.read_text(encoding="utf-8"));s=d.get("summary") or {}
        if s.get("input_rows") is None or s.get("canonical_companies") is None:errors.append("deduplication_report sin resumen trazable")
        if s.get("ambiguous_merges",0)!=0:errors.append("deduplication_report contiene fusiones ambiguas")
        if s.get("unresolved_name_scope_conflicts",0)!=0:errors.append("deduplication_report contiene conflictos nombre-ámbito sin resolver")
    cr=root/"data/v33/coverage_report.json"
    if cr.exists():
        d=json.loads(cr.read_text(encoding="utf-8"));s=d.get("summary") or {}
        if s.get("difference_between_averages") is None or s.get("average_knowledge_debt") is None:errors.append("coverage_report sin diferencia/deuda separadas")
    return errors
