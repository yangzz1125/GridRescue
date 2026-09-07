# GridRescue Wave 8 — Resilience Equity: synthetic service-floor audit

**Scope:** design review only; no production code changed.  
**Decision:** include a **report-and-gate “Resilience Equity Passport”** in the 10-day MVP only if it stays synthetic, non-demographic, and post-solve. Defer new multi-group dispatch constraints and any real-world distributive-equity claim to future work.

## 1. Opportunity

GridRescue already goes beyond total EENS:

- CareTask encodes task-level minimum kW, window, deadline, continuity, dependency, voltage band, and an E-class synthetic data label.
- ServiceContract constrains hospital, other-essential, and normal EENS; task_requirements puts CareTask hourly power floors into dispatch.
- Pareto candidates are revalidated against task completion and physical feasibility; care failures are excluded from the recommended frontier.

One aggregation hole remains: other_essential_unserved_cap_kwh pools essential and critical service classes. A candidate can preserve their combined EENS cap while concentrating interruption in a smaller declared service class. Aggregate EENS also does not reveal whether each declared group received a sustained minimum restoration level.

The dimension should therefore be **functional service equity**, not demographic equity:

> A candidate reports how restoration is distributed across declared, synthetic service cohorts rather than being judged only by total EENS.

This enables a credible adverse demo: “a lower-carbon or lower-total-EENS candidate is blocked/flagged because it concentrates interruption in a life-safety or continuity cohort.”

## 2. Existing assets to build on

| Asset | Current behavior | Design implication |
|---|---|---|
| src/gridrescue/care.py | Four E-class synthetic CareTasks: two Tier-1 and two Tier-2; per-task power, voltage, duration, deadline, dependency and failure evidence. | Reuse task tiers and evaluations; add no person-level fields. |
| src/gridrescue/dispatch.py | ServiceContract holds hospital, other-essential, normal EENS caps and ServiceTaskRequirement floors. | MVP can audit finer cohorts without solver changes; future constraints fit the same contract. |
| src/gridrescue/restoration.py | node_frame derives hospital, essential, critical, normal from synthetic node type and critical level. | Use these existing functional classes; do not add demographic attributes. |
| src/gridrescue/pareto.py | Lexicographically anchors hospital then aggregated other-essential service; care failure blocks frontier eligibility. | Add a post-solve passport; preserve the existing care/physics gates. |
| tests/test_care.py | Covers overlapping tasks, schema validation and task voltage separate from grid feasibility. | Copy this evidence-first testing style. |

The present CareTask template is explicitly E-class synthetic. That boundary must remain visible in every equity artifact.

## 3. Minimal synthetic-data model

Add one versioned scenario-design file, e.g. data/resilience_equity_template_v1.json. It contains **service contracts, not people**: no addresses, income, race, disability, medical records, or inferred vulnerability score.

    {
      "schema_version": 1,
      "data_class": "E_synthetic_service_cohort_template",
      "purpose": "competition service-distribution audit; not a population-equity dataset",
      "cohorts": [
        {
          "cohort_id": "T1_LIFE_SAFETY",
          "label": "Tier-1 life-safety tasks",
          "evidence_source": "care_task_tier",
          "selector": {"tier": 1},
          "metric_family": "task",
          "contract_mode": "hard",
          "min_task_completion_rate": 1.0
        },
        {
          "cohort_id": "T2_CONTINUITY",
          "label": "Tier-2 continuity tasks",
          "evidence_source": "care_task_tier",
          "selector": {"tier": 2},
          "metric_family": "task",
          "contract_mode": "hard",
          "min_task_completion_rate": 1.0
        },
        {
          "cohort_id": "CRITICAL_SERVICE",
          "label": "Synthetic critical-service load",
          "evidence_source": "node_service_class",
          "selector": {"service_class": "critical"},
          "metric_family": "energy",
          "contract_mode": "monitor",
          "min_served_fraction": 0.99
        },
        {
          "cohort_id": "ESSENTIAL_SERVICE",
          "label": "Synthetic essential-service load",
          "evidence_source": "node_service_class",
          "selector": {"service_class": "essential"},
          "metric_family": "energy",
          "contract_mode": "monitor",
          "min_served_fraction": 0.99
        },
        {
          "cohort_id": "NORMAL_SERVICE",
          "label": "Synthetic general-service load",
          "evidence_source": "node_service_class",
          "selector": {"service_class": "normal"},
          "metric_family": "energy",
          "contract_mode": "disclose_only"
        }
      ],
      "policy": {
        "require_energy_partition": true,
        "task_failure_blocks_recommendation": true,
        "monitor_breach_blocks_recommendation": false,
        "data_missing_blocks_recommendation": true
      }
    }

### Why this model is deliberately narrow

1. **Service obligations, not people.** Critical/essential are current synthetic load classes, not proxies for protected traits.
2. **No double counting.** Energy cohorts must partition node_frame rows exactly once. Task cohorts are evaluated from evaluate_care_tasks and are never re-added as extra kW.
3. **Visible trade-off.** Tier-1/Tier-2 task status is hard; critical/essential split exposes pooling that aggregate other-essential EENS hides; normal service remains the explicit ε-relaxation axis.
4. **Reversible data boundary.** A real operator could replace this E-class template with reviewed asset/service contracts without changing the evaluator.

### Validation rules

- cohort_id unique; metric_family is task or energy.
- Every energy cohort selects at least one node_frame row and selections form an exact partition when require_energy_partition=true.
- Every task cohort selects at least one CareTask.
- Hard/monitor floors are in [0, 1]; disclose_only has no threshold.
- Definition SHA-256 covers all cohorts and policy; output/manifests carry it.
- Missing dispatch, power-flow, or task evidence becomes DATA_MISSING, never an implicit zero-load success.

## 4. Metrics

For cohort g, let D_g be required energy, S_g be served energy, and U_g=D_g-S_g. Current code is hourly; energy calculation must explicitly multiply by time_step_h before any sub-hour extension.

| Metric | Calculation | Purpose |
|---|---|---|
| Cohort demand | D_g | denominator and accounting check |
| Cohort EENS | U_g | transparent outage burden |
| Served fraction | q_g=S_g/D_g | compares groups of different size |
| Service-floor breach | q_g < q_g_min | machine-readable status |
| Worst declared cohort service | min(q_g) | avoids a good average hiding a severe small-cohort loss |
| Essential-class spread | abs(q_critical-q_essential) | flags concentration across currently pooled classes |
| Time below floor | sum of hourly floor failures × time_step_h | exposes transient deprivation |
| Task completion rate | completed tasks / declared tasks | Tier-level task service status |
| Tier-1/Tier-2 pass | all selected tasks complete | hard service evidence |
| Failure-code histogram | existing CareTask failure codes | explains cause without invented harm outcomes |

q_g is an operational service-distribution metric, not a welfare score or a human-harm estimate.

### Decision status

    equity_data_complete
    AND tier1_task_pass
    AND tier2_task_pass
    AND physical_pass
    AND existing_care_contract_pass
    = resilience_equity_hard_pass

For the MVP, critical/essential floor breaches are **amber monitoring findings**, not new solver constraints. The user interface can label the point NOT_PREFERRED_FOR_BALANCED_SERVICE, but must identify it as a synthetic policy outcome rather than a real-world equity verdict.

## 5. MVP reporting path

The smallest useful implementation is a pure post-solve evaluator:

    StrategyResult.dispatch.node_frame
      + FlowValidation.nodes
      + CareTask evaluation
      + ResilienceEquityTemplate
      -> resilience_equity_evaluation.csv
      -> resilience_equity_summary.json
      -> Pareto/report badges

Recommended evaluation columns:

    run_id, strategy, cohort_id, metric_family, data_class,
    demand_kwh, served_kwh, eens_kwh, served_fraction,
    minimum_hourly_served_fraction, hours_below_floor,
    task_count, completed_task_count, task_completion_rate,
    floor_or_completion_target, contract_mode, status,
    failure_reason_codes, definition_sha256

Recommended summary fields:

    equity_definition_sha256, equity_data_complete,
    tier1_task_pass, tier2_task_pass,
    critical_service_fraction, essential_service_fraction,
    essential_service_spread, normal_service_fraction,
    hard_pass, monitor_breach_count, data_boundary

### Pareto/report behavior

1. Preserve the present hospital → other-essential → normal lexicographic anchors and CareTask hard gate.
2. Evaluate the passport for every anchor and ε candidate.
3. Display hard-pass status beside physical_pass, care_contract_pass, contract_pass and frontier_eligible.
4. For MVP, do **not** silently change the optimizer or numeric frontier. Export:
   - frontier_eligible_existing;
   - resilience_equity_hard_pass;
   - resilience_equity_monitor_status;
   - a recommended-point filter requiring existing frontier eligibility plus hard pass.
5. A later governance decision may set monitor_breach_blocks_recommendation=true. That is an explicit policy switch, not an algorithmic fairness truth.

This avoids presenting a normative priority choice as a physics result.

## 6. Future optimization

After core evidence is frozen, extend ServiceContract with versioned cohort constraints:

    CohortServiceRequirement(
        cohort_id="CRITICAL_SERVICE",
        service_class="critical",
        max_unserved_kwh=critical_anchor_eens + tolerance,
    )

Recommended solve sequence:

    Tier-1 CareTask floors
    → Tier-2 CareTask floors
    → hospital EENS anchor
    → critical-class EENS anchor
    → essential-class EENS anchor
    → normal-service ε budget
    → carbon minimization

Use lexicographic anchors or explicit caps, not arbitrary large objective weights. This matches the current DispatchObjective/ServiceContract pattern.

Do not add demographic/geographic “vulnerability” weights in the MVP. That requires a governed dataset, transparent rationale, privacy review, stakeholder input and operational authority.

## 7. Visualization: Resilience Equity Passport

Use one compact decision panel.

1. **Service bars:** Tier-1 tasks, Tier-2 tasks, critical, essential and normal service, with percentage/floor/status.
2. **24-hour stripe:** rows for energy cohorts colored by hourly served fraction; task rows by hour_pass.
3. **Pareto scatter:** normal EENS vs operational carbon, with marker color/shape for existing eligibility, hard pass, amber monitoring breach and data missing.
4. **Reason card:** PASS / AMBER / BLOCKED and the source CareTask codes or cohort-floor breaches.
5. **Counterfactual toggle:** compare selected candidate to same-service anchor; always show total EENS, carbon, each cohort’s service fraction and normal-service concession together.

Avoid maps, demographic choropleths, “vulnerability scores,” or any language implying an actual community impact assessment.

## 8. Counterexample for the demo

Create a reproducible synthetic pair:

| Candidate | Critical-class EENS | Essential-class EENS | Combined other-essential EENS | Passport result |
|---|---:|---:|---:|---|
| Balanced | 5 kWh | 5 kWh | 10 kWh | monitor pass if both floors met |
| Concentrated | 10 kWh | 0 kWh | 10 kWh | amber: critical cohort breach / large spread |

The current aggregate other-essential cap sees equal combined EENS. The passport makes the concentrated burden visible without asserting anything about actual residents.

Add a second counterexample: total EENS improves but a Tier-1 CareTask fails its voltage/deadline test. Existing care logic should block it; the passport makes that reason visible alongside the attractive aggregate metric.

## 9. Tests / Definition of Done

| Priority | Test | Required assertion |
|---|---|---|
| P0 | Exact energy partition | Cohort demand/served/EENS sum to unique node-frame totals; no row belongs to zero or multiple energy cohorts. |
| P0 | Aggregate masking | Same combined other-essential EENS but unequal split; concentrated candidate is MONITOR_BREACH. |
| P0 | Care failure dominates | Lower EENS/carbon with failed Tier-1 task sets hard_pass=false. |
| P0 | Missing evidence | Deleted node-hour/task evidence yields DATA_MISSING, never green. |
| P0 | No double count | Overlapping CareTasks affect task status only; energy totals remain unchanged. |
| P0 | Schema validation | Duplicate IDs, empty selector, invalid floor, nonpartition, unknown selector fail fast. |
| P0 | Determinism/versioning | Same inputs give identical output/hash; changed floor/selector changes definition hash and run linkage. |
| P1 | Baseline compatibility | Passport disabled leaves current strategy/Pareto numerics unchanged. |
| P1 | Service-class split | critical and essential have independently reported EENS despite aggregate cap. |
| P1 | ε disclosure | Any normal-service concession is visible; it cannot appear as a no-cost carbon reduction. |
| P1 | Visual recomputability | Red/amber badge has corresponding exported reason code and can be recomputed from CSV evidence. |

## 10. Ethical and claim boundaries

### Permitted language

- “GridRescue audits whether a **synthetic declared service contract** distributes restoration across life-safety, continuity, critical, essential and normal-service cohorts rather than reporting only total EENS.”
- “The passport is a transparent service-floor and concentration diagnostic connected to task and physical evidence.”
- “The template can later be replaced by reviewed local service contracts.”

### Prohibited language

- “The model delivers social equity,” “protects vulnerable populations,” or “minimizes human harm.”
- Claims that IEEE-33 labels, CareTask values, or outcomes represent a real community, hospital, population group or medical standard.
- Claims that a green/amber status is a clinical, legal, regulatory or real deployment decision.

### Deployment governance later

Real deployment requires reviewed service taxonomy, emergency-management and operator governance, data minimization, documented decision authority, override/audit logs, and calibration against actual feeder/asset/continuity plans. Any demographic analysis is a separate governed research workstream.

## 11. 30-second competition statement

> “Total EENS can look good while one declared service cohort absorbs the outage. GridRescue already locks task-level life-safety service and validates it with power-flow evidence. The Resilience Equity Passport splits existing aggregated service classes, shows each cohort’s floor and time trace, and flags concentrated interruption. It uses no resident or demographic data. Candidates first pass service, physical and evidence gates; only then is their carbon record compared.”

## 12. Recommendation and effort

| Option | Value | Risk | Recommendation |
|---|---|---|---|
| Report-only passport, artifacts and one counterexample | High credibility gain; reuses current evidence; no solver risk | Needs strict synthetic/claim boundary | **MVP if it takes ≤1.5 engineer-days after P0 evidence work.** |
| New critical/essential lexicographic solver caps | Stronger optimization claim | Alters feasible set/frontier and test burden | **Future work**; only attempt after physical/MRV gates are frozen. |
| Demographic/geographic weights | Potentially relevant in real governance | No valid data; high ethical/privacy/claim risk | **Future research only.** |

**Final call:** ship the passport as an auditable synthetic reporting/gate layer, not a new fairness optimizer, in the 10-day MVP. It directly answers “who is left behind by total EENS?” while remaining inside the current IEEE-33 prototype’s evidence and ethical limits.

## Local evidence and reference boundary

- Reviewed implementation evidence: src/gridrescue/care.py, dispatch.py, restoration.py, pareto.py and tests/test_care.py.
- Reviewed internal design evidence: research_wave/wave3_hospital_tasks.md, research_wave/wave6_care_redteam.md, docs/competition_narrative.md and research_wave/wave8_judging_strategy.md.
- Background sources already identified by the project: World Health Organization, *Electricity in health-care facilities*; ASPR TRACIE, *Utility Failures in Health Care Toolkit*; and 42 CFR §482.15. They motivate continuity planning only; they are not parameter sources for this E-class synthetic template.
