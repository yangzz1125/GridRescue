# Wave 8 — Carbon-SOC skeptical review and 10-day go/no-go experiment

**Review date:** 2026-08-22  
**Scope:** code and research notes in this repository. This is a model-accounting review, not a field-MRV or third-party assurance opinion.

## Bottom line

**Do not present Carbon-SOC as a measured carbon-reduction mechanism yet.** It is potentially useful as a *dispatch explanation and decision-policy experiment*, but the current production code has no source-resolved Carbon-SOC ledger and has two comparison loopholes that can manufacture a favourable result: (1) the battery starts with energy whose origin is unrecorded, and (2) the 24-hour solve has no terminal-SOC reconciliation. The current hourly `grid_carbon_kg_per_kwh` is a synthetic, shaped decision signal—not a published real-time marginal emission factor.

The smallest defensible result in ten days is therefore:

> Under one frozen synthetic scenario, service contract, topology/restoration plan, resource fleet, and factor snapshot, compare a service-only dispatch (A), a resilience-reserve dispatch (B), and a reserve-plus-Carbon-SOC-window dispatch (C). Report **modelled operational-inventory differences** only after all variants pass the same service, physical, initial-state, and terminal-state gates. Treat the hourly factor as a **synthetic dispatch proxy**; do not describe it as marginal grid emissions.

A `GO` requires the P0 controls below and all pre-registered tests. Otherwise the outcome is `NO-GO` for carbon claims; the project may still show the visual SOC/resilience prototype as exploratory.

---

## 1. What the repository currently does

| Evidence | Observed implementation fact | Skeptical implication |
|---|---|---|
| `src/gridrescue/dispatch.py:288-293` | One SOC state is initialized as `initial_soc * storage_energy`; update is `SOC[t+1] = SOC[t] + η·charge - discharge/η`. | There is no source bucket or carbon mass attached to stored energy. With `η=0.94`, modeled round-trip energy recovery is `η² = 0.8836`, but the losses are not separately exported or attributed. |
| `dispatch.py:346-354, 415-436` | The optimization carbon term is grid import × hourly factor + diesel generation × 0.72. | Battery charge/discharge changes emissions only indirectly through grid/diesel dispatch. That is valid for an operational inventory, but it is not Carbon-SOC accounting. |
| `dispatch.py:468-497` | Aggregate SOC is the sum of node SOCs and node output publishes only the **end-of-hour** SOC. | Aggregate SOC hides island/component ownership; end state alone makes an audit vulnerable to off-by-one initial/withdrawal errors. |
| `carbon.py:39-49` | Operational total is grid + diesel + crew. It additionally calculates `avoided_grid_equivalent_kg = curtailment × 0.5366`. | This field is a double-counting hazard if exposed as a benefit alongside lower grid/diesel inventory; avoided curtailment is an energy-utilization KPI, not automatically avoided emissions. |
| `scenarios.py:81-89` | Grid factor is `0.5366 × scenario multiplier × evening-shaped synthetic curve`. | The time series is a scenario assumption. It cannot support a claim about actual hourly average, locational, consequential, or marginal emissions. |
| `mrv.py:47-112` | Factor registry calls factors `synthetic-demo`, `engineering_prior`, source class `E`, uncertainty 20%. | Correct label for a competition model. Any UI/report language that upgrades it to real measured carbon would be misleading. |
| `mrv.py:350-385` | Existing claim gate compares the carbon-resilient strategy to the EENS strategy, allowing up to 8% additional normal EENS for its “controlled tradeoff” path. | That is not a same-service carbon comparison. Carbon-SOC A/B/C must use one frozen explicit service contract rather than this existing strategy comparison. |

The research notes already identify most of the right guardrails (`carbon_mrv_plan.md`, `wave7_carbon_soc_code.md`). The gap is implementation evidence and a deliberately adversarial experiment that proves those controls bind.

---

## 2. Accounting model that is defensible enough for the experiment

Use `Δt = 1 h` for the MVP and keep the **operational inventory** separate from the **storage provenance ledger**.

### 2.1 Operational inventory — count the physical source once

For variant `r` and hour `t`:

```text
I(r) = Σ_t [ G(r,t) · EF_grid,inventory(t)
           + D(r,t) · EF_diesel
           + V(r,t) · EF_vehicle ] · Δt
```

- `G` is positive import at the accounting boundary only; do not net export against it in the MVP.
- `D` is diesel electric output only if `EF_diesel` is explicitly an output-based factor; otherwise calculate fuel first.
- `V` is only the plan-dependent incremental vehicle activity. A common scenario-wide crew trip is either included in every variant and cancels in `ΔI`, or excluded from every variant—never counted as a Carbon-SOC effect.
- Battery charge is already embodied in `G`, `D`, or on-site-PV supply at charge time. Battery discharge creates no second negative inventory entry.

For a valid paired comparison:

```text
ΔI(C,A) = I(A) - I(C)
```

is reportable only if all service and state gates in Section 5 pass. It is a **modelled inventory difference**, not a tradable avoided-emissions quantity.

### 2.2 Carbon-SOC provenance ledger — explain stored energy without re-counting inventory

For each storage asset `b`, maintain five energy buckets `S_b,o,t` where:

```text
origin o ∈ {initial_unknown, grid_proxy, on_site_pv_unclaimed, diesel, loss}
S_b,t = Σ_o S_b,o,t
```

Use explicit one-way efficiencies `η_ch` and `η_dis`; retain the current `η` as both only for the MVP if needed, but name that assumption visibly.

```text
S_b,o,t+1 = S_b,o,t
            + η_ch · C_b,o,t
            - W_b,o,t

Σ_o W_b,o,t = W_b,t
D_b,t = η_dis · W_b,t
0 ≤ W_b,o,t ≤ S_b,o,t
```

`C_b,o,t` is AC-side charging energy assigned to exactly one origin. `W` is internal energy withdrawn. The unreturned fraction from charge/discharge is an energy loss, not a source of carbon credit.

For a proportional-mix MVP, set:

```text
W_b,o,t = W_b,t · S_b,o,t / max(S_b,t, ε)
```

For a FIFO implementation, retain individual lots. **Pick one allocation rule and freeze it before A/B/C runs; do not choose the rule after seeing results.** Proportional mix is the smaller, more stable MVP.

A descriptive stored-energy intensity is:

```text
CI_store(b,t) = [Σ_o S_b,o,t · EF_origin,o] / S_b,t,       if S_b,t > ε
```

It explains provenance only. Do **not** calculate a second inventory adjustment `D_b,t × CI_store`; charge-time physical emissions are already in `I(r)`.

### 2.3 Initial state and terminal reconciliation

Initial stored energy is a real economic/physical resource and a comparison confounder. Record it explicitly:

```text
S_b,initial_unknown,0 = initial_soc_b · Emax_b
S_b,o≠initial_unknown,0 = 0
```

For the 10-day experiment, use a conservative default:

```text
EF_initial_unknown = EF_grid,inventory(0)
```

and run a three-case sensitivity, not an opportunistic single assumption:

1. `initial_unknown = 0` only as a **provenance visualisation** bound, never as a reduction claim;
2. `initial_unknown = EF_grid(0)` as the primary conservative assumption;
3. `initial_unknown = max_t EF_grid(t), EF_diesel` as a high-carbon stress case.

To prevent end-of-horizon extraction masquerading as a benefit, impose one of the following **before** comparing variants:

```text
Terminal energy neutrality:    |S_b,T - S_b,0| ≤ ε_E     for every b
```

or, if resilience requires a closing reserve:

```text
Terminal reserve equivalence:  S_b,T ≥ R_b,T and
                               E_close(A) = E_close(B) = E_close(C)
```

The first is simpler and recommended for the MVP. If terminal equality makes an incident scenario infeasible, flag the experiment infeasible; do not relax it only for C.

---

## 3. Conceptual traps and required countermeasures

### P0 — blocks a Carbon-SOC comparison or carbon-performance claim

| Trap | Failure mode | Required control |
|---|---|---|
| **Initial-SOC free lunch** | C can discharge pre-existing energy and look cleaner even though its historical source is unknown. | Origin-tag initial energy; hold the exact initial SOC vector and bucket policy constant; run the three initial-carbon sensitivity cases. |
| **Terminal-horizon gaming** | The objective can empty storage at hour 23/24, avoiding grid/diesel inside the window while pushing replenishment beyond the measured window. | Per-asset terminal neutrality (recommended) or identical, pre-specified terminal reserve/value for A/B/C. Publish `SOC_start`, `SOC_end`, and terminal residual. |
| **Double counting battery benefit** | Charge emissions are counted in grid/diesel inventory and discharge is separately called “avoided/grid-equivalent carbon.” | Inventory only at source; Carbon-SOC is descriptive provenance; `battery_avoided_kg` must not exist as an additive total. |
| **Curtailment credit double count** | Curtailment reduction × grid factor is added to inventory difference, despite the same PV energy already reducing grid/diesel. | Keep curtailment as kWh KPI; exclude `avoided_grid_equivalent_kg` from total, comparison, UI score, and claim language. |
| **Different service contracts** | One variant supplies less normal or critical load, so lower energy use is mislabelled carbon performance. | Freeze the same explicit `ServiceContract`, care-task set, restoration plan, fault state, factor snapshot, and resource capacities. Require equality/tolerance for priority service and a disclosed normal-load bound. |
| **Synthetic factor rebranded as marginal** | A hand-shaped evening profile is treated as evidence of actual dispatch emissions. | Call it `EF_grid_proxy`; use it only for policy selection in the synthetic test. Report inventory under the same declared synthetic factor; do not claim real marginal savings. |
| **Topology pooling** | Aggregate SOC allows stored energy on one island to be implicitly credited to a different electrically isolated component. | Maintain origin buckets at `(hour, node, component)`; run all reserve/target logic component-wise and preserve split/merge lineage. |

### P1 — required before a credible prototype demo

| Trap | Failure mode | Required control |
|---|---|---|
| **Losses hidden in a single efficiency** | `η=0.94` on both sides means 11.64% round-trip loss, but charge and discharge loss locations/provenance are not visible. | Export AC charge, internal stored increment, internal withdrawal, AC discharge, charge loss, discharge loss; assert energy conservation each hour. |
| **Grid average vs marginal factor confusion** | Average inventory factors answer attributional accounting; marginal/consequential factors answer a dispatch-impact question. They are not interchangeable. | Maintain separate fields: `EF_grid_inventory` and `EF_grid_decision_proxy`. The 10-day run may set them equal only with label `synthetic proxy; not marginal`. |
| **Factor/fuel basis mismatch** | Diesel `kg/kWh` may be assumed at an unrealistically fixed load; grid factor may be CO2 while a report says CO2e. | Freeze unit/gas basis (`kgCO2` in the current dataset), factor version, time basis, and diesel load assumption. No `CO2e` wording without CH4/N2O coverage. |
| **Simultaneous charge/discharge degeneracy** | Convex formulation can allow artificial cycling unless objective penalties happen to suppress it. | Add an audit assertion: `min(charge, discharge) ≤ ε` each asset/hour. If violated, exclude the run or add a documented anti-simultaneity formulation. |
| **Policy not separable from plan changes** | C might benefit from a different repair/switch plan rather than Carbon-SOC. | Freeze `RestorationPlan`, P/Q feedback seed/parameters, capacity assumptions, and component map inputs. Only dispatch policy differs. |
| **Choice after seeing results** | Horizon, quantile, target weight, or reserve becomes tuned to make C win. | Pre-register parameters and permitted sensitivity grid; publish all tested cases, including no-benefit and infeasible cases. |

### P2 — needed for any real-world or external-comparison claim

| Gap | Why it matters | Required future evidence |
|---|---|---|
| Actual interval meter data and BESS telemetry | Scenario dispatch may not match real charge source, losses, SOC calibration, or outages. | Timestamped meter/SCADA/BMS data with calibration, quality flags, and missing-data treatment. |
| Auditable environmental-attribute ownership | On-site PV may carry sold/retired certificates or contractual claims elsewhere. | Attribute registry with ownership, vintage, status, retirement evidence, and single-claim rule. |
| Published/validated marginal signal | A dispatch policy that claims consequential avoided emissions needs a valid marginal methodology. | Geography/time-resolved marginal model or operator-approved methodology, versioned inputs, uncertainty evaluation. |
| Counterfactual/contract comparability | A field comparison needs a credible baseline and no changed service/resources. | Pre-specified baseline, matched events, service metrics, measured resource availability, and independent review. |

---

## 4. Smallest defensible A/B/C experiment

### 4.1 Pre-register one objective

**Question:** With all physical service and accounting conditions equal, does a source-traceable Carbon-SOC window policy change modeled operational inventory relative to a service-only or reserve-only dispatch?

Do not test “does storage reduce emissions?” The answer depends on the charged energy, losses, counterfactual supply, and the chosen accounting boundary.

### 4.2 Freeze inputs and comparison boundary

Use one named 24-hour scenario, preferably `flood_v08` because it already has physical/care artifacts, and lock:

```text
scenario ID + seed + demand/PV series + all outages + repair completion times
restoration/switch plan + P/Q feedback configuration + component-map refresh rule
BESS locations/capacity/power/min SOC/η_ch/η_dis + diesel/PV/grid capacities
ServiceContract and all CareTask requirements
factor snapshot + unit/gas basis + decision-factor label
initial SOC vector + initial provenance policy + terminal-SOC rule
solver/version + policy parameters + run manifest hash
```

No variant may receive different PV, diesel capacity, grid capacity, crew route, repair timing, or task service requirement.

### 4.3 Variants

| Variant | Dispatch addition | What it isolates |
|---|---|---|
| **A — service-only** | Existing spatial `min_carbon` dispatch under the frozen service contract **plus the terminal-SOC rule**. No Carbon-SOC reserve or target. | Current carbon objective under fair state-of-charge closure. |
| **B — reserve-only** | A + hard component-level resilience reserve `R[t,node]`. No carbon target and no use of the hourly factor beyond the common inventory calculation. | Reliability value/cost of preserving operational SOC. |
| **C — Carbon-SOC-window** | B + source-bucket ledger and a *soft* target `T[t,node]` only for pre-registered positive-window conditions. | Incremental value of the Carbon-SOC policy, distinct from reserve protection. |

The **same terminal rule is mandatory in A, B, and C**. Without it, a lower C inventory can simply be an ending-energy withdrawal.

### 4.4 Reserve and target definitions

Let `c(t,n)` be the node’s electrical component. First compute a component reserve independent of carbon:

```text
Dcrit[k,c] = max(0, critical_demand[k,c]
                - firm_grid[k,c]
                - firm_diesel[k,c]
                - firm_pv[k,c])

Rcomp[t,c] = min(Emax[c], Emin[c] + Σ_{k=t}^{t+Hr-1} Dcrit[k,c] / η_dis)
```

Allocate component reserve among its storage assets using usable-energy share and publish that allocation. If `Rcomp > Emax`, tag `reserve_infeasible`; do not clip and call the candidate successful.

For C, keep the carbon target soft and disable it when evidence is weak:

```text
shift_gain[t,k,c] = η_ch · η_dis · EF_replace_proxy[k,c]
                    - EF_grid_decision_proxy[t]

Tcomp[t,c] = clip(Rcomp[t,c] + Eopp[t,c], Rcomp[t,c], Emax[c])
```

`Eopp` includes only future slots with (a) a replaceable grid/diesel load, (b) a positive `shift_gain` exceeding a frozen margin, and (c) an intact/available component. If factors are flat, source status is unknown, or no replacement load exists, force `T = R`; C must reduce to B.

### 4.5 Minimum outputs

One hourly row per `(variant, hour, storage node)`:

```text
soc_start_kwh, soc_end_kwh, charge_ac_kwh, charge_loss_kwh,
withdraw_internal_kwh, discharge_ac_kwh, discharge_loss_kwh,
origin_initial_unknown_kwh, origin_grid_proxy_kwh,
origin_pv_unclaimed_kwh, origin_diesel_kwh,
reserve_kwh, target_kwh, component_key,
EF_grid_inventory, EF_grid_decision_proxy, EF_replace_proxy,
window_flag, reason_code, reserve_feasible
```

One run summary per variant:

```text
critical/essential/normal unserved kWh; CareTask completion;
P/Q feasibility; grid/diesel/vehicle inventory; curtailment kWh;
SOC0 and SOCT by asset; accounting/energy assertion results;
comparison_eligible; factor-quality label; all failure reasons.
```

---

## 5. Pre-registered test cases and pass/fail conditions

### P0 test cases

| ID | Fixture / perturbation | Required assertion | Failure meaning |
|---|---|---|---|
| P0-1 Same-service gate | Artificially cap A/B/C with identical contract and task requirements; run P/Q feedback. | All three have identical contract hash; care tasks complete; critical/essential EENS within `ε=1e-3 kWh`; physical feasible every hour. | No comparative carbon result. |
| P0-2 Initial-state sensitivity | Same run under the three `initial_unknown` intensity assumptions. | Report the range; C-vs-A operational `ΔI` must not be labelled as a Carbon-SOC benefit that depends on selecting the zero-carbon initial bound. | Initial energy is a hidden subsidy. |
| P0-3 Terminal flush | Construct low-factor early hours/high-factor late hours and allow A/C to freely finish empty once. Re-run with terminal equality. | Comparison is eligible only in terminal-equality run. Publish both as diagnostic vs claim-eligible. | End-horizon gaming. |
| P0-4 Double-count trap | One PV-charged battery kWh later displaces one grid kWh; set curtailment decrease nonzero. | `I` changes only through physical grid/diesel/vehicle flows; `curtailment × EF` is not added to `ΔI`; no battery negative-emission row. | Same benefit is credited twice. |
| P0-5 Flat factors | Set all `EF_grid_decision_proxy[t]` equal and keep replacement availability unchanged. | `T=R`; C dispatch and inventory equal B within solver tolerance; no precharge/window reason code. | Policy manufactures a false carbon signal. |
| P0-6 Component split | Two simultaneous islands, one high-factor/replacement opportunity and one not. | No SOC/provenance/target crosses components; only eligible component receives C target. | Aggregate SOC is illegally pooled. |

### P1 test cases

| ID | Fixture / perturbation | Required assertion |
|---|---|---|
| P1-1 Energy/loss conservation | Charge then discharge a single store with known `η_ch`, `η_dis`. | `SOC_end = SOC_start + η_ch·C - W`; `D = η_dis·W`; source buckets sum to SOC; all loss terms nonnegative. |
| P1-2 Source conservation | Charge grid, PV, and diesel in separate hours, then discharge. | Per-origin buckets remain nonnegative; charged origin energy less losses equals remaining+withdrawn internal energy under selected allocation rule. |
| P1-3 Factor label flip | Use a flat inventory factor but a different synthetic decision proxy, then reverse proxy ordering. | Inventory accounting uses inventory field only; C’s actions change only with declared decision proxy; reports show both fields and never call either marginal without evidence. |
| P1-4 No simultaneous cycling | Evaluate all storage-hours in A/B/C. | `min(charge_ac_kwh, discharge_ac_kwh) ≤ 1e-5` per asset/hour. |
| P1-5 Reserve infeasible | Demand a future critical deficit greater than component usable BESS energy. | Candidate exports `reserve_infeasible=True`, fails eligibility, and remains visible in failure output. |
| P1-6 Plan invariance | Hash plan/topology/factor/service inputs per variant. | Hashes match A/B/C except `variant` and Carbon-SOC policy fields. |

### P2 pilot acceptance tests (not part of the 10-day claim)

- Compare BMS SOC and interval meter energy over at least one controlled charge/discharge event; define tolerated error before collection.
- Demonstrate source/attribute status for each PV kWh counted as `on_site_pv_unclaimed`.
- Validate any marginal factor method on historical dispatch data and publish its uncertainty and geography/time applicability.
- Conduct a preregistered matched-event or replay baseline; do not infer field carbon benefit from an unmatched outage.

---

## 6. Go/no-go rubric

### GO — limited model claim allowed

All items must be true:

1. P0-1 through P0-6 pass; no one-off override or manually edited output.
2. P1-1 through P1-6 pass; all assertion results and failures export with the run.
3. A/B/C share the same frozen service contract, state vector at `t=0`, terminal condition, restoration plan, factor snapshot, and physical feedback loop.
4. All variants are `comparison_eligible`; infeasible variants are reported, not dropped.
5. The C effect is stable in the preregistered factor and efficiency sensitivity cases: sign remains non-negative for the claimed inventory improvement, or the claim reports the full sign-changing interval.
6. UI/report state `synthetic model`, `kgCO2` (not `kgCO2` with the current factor registry), and `decision proxy; not marginal emission factor`.

### CONDITIONAL GO — demo only, no performance conclusion

- The source ledger and P0 accounting tests pass, but C has no consistent incremental benefit over B, or a result is sensitive to a realistic factor/efficiency perturbation.
- Show a Carbon-SOC provenance visualisation and explain it as an accounting/dispatch-research feature. Do not headline a carbon improvement percentage.

### NO-GO — no Carbon-SOC carbon-comparison output

Any one of the following is sufficient:

- terminal SOC differs across A/B/C without a pre-specified closing-value adjustment;
- initial SOC origin is missing or changed by variant;
- any inventory adds curtailment, battery discharge, or exported energy as an additional avoided-emissions credit;
- comparison variants fail common service/P/Q/care gates;
- factor source is called marginal, real-time, green, or measured when it is the repository’s synthetic profile;
- source-bucket or energy-conservation assertions fail;
- C’s advantage disappears when the hidden policy parameter or factor assumption is normalized.

---

## 7. Ten-day minimal execution sequence

| Day | Deliverable | Exit criterion |
|---:|---|---|
| 1 | Freeze experiment card: scenario, plan, contract, factor snapshot, SOC0, terminal rule, parameters, sensitivity grid. | Manifest hashes exist before implementation. |
| 2 | Implement/export source-bucket ledger as an isolated module; no change to existing inventory totals. | P1-1 and P1-2 green on toy fixtures. |
| 3 | Export per-node `soc_start`/`soc_end`, AC/internal energy and loss fields. | Node/hour energy reconciliation file produced. |
| 4 | Add terminal-SOC equality and independent component reserve `R`. | P0-3 and P1-5 green. |
| 5 | Implement A/B independent runner with frozen contract/plan and eligibility gates. | P0-1 and P1-6 green. |
| 6 | Add C soft window target and reason codes; force flat-factor fallback `T=R`. | P0-5 green. |
| 7 | Add component split lineage and factor-label fields. | P0-6 and P1-3 green. |
| 8 | Run full A/B/C plus initial-state, η, and factor sensitivity grid. | Results table retains every pass/fail/infeasible case. |
| 9 | Red-team outputs: double-count test, wording audit, reproducibility rerun from manifest. | P0-2/P0-4 green; output hashes reproduce. |
| 10 | Freeze evidence bundle, Go/Conditional/No-Go decision, chart captions, and one-page method card. | Only approved wording appears in dashboard/PPT. |

The deliberately small scope avoids rebuilding the entire dispatch system: keep the existing P/Q feedback and CareTask validation; add an opt-in, isolated comparison runner and artifacts. Do not add A/B/C to the default strategy list until this passes.

---

## 8. Claim wording library

### Allowed now (provided the specific cited gates pass)

- **Inventory only:** “For this fixed synthetic 24-hour restoration scenario, GridRescue estimates operational emissions from modeled grid imports, diesel output, and stated vehicle activity using a versioned synthetic factor set.”
- **A/B/C result:** “With the same modeled service contract, restoration plan, initial/terminal SOC rule, and physical-feasibility checks, the Carbon-SOC-window variant produced a modeled operational-inventory difference of `X kgCO2` versus A. The hourly factor is a synthetic dispatch proxy, not a measured marginal emission factor.”
- **Carbon-SOC meaning:** “Carbon-SOC records the modeled origin mix and attributed intensity of stored energy; it does not create a second avoided-emissions credit when that energy is discharged.”
- **No benefit case:** “Under a flat or uncertain factor signal, the Carbon-SOC-window policy collapses to reserve-only and is not presented as a carbon-shifting benefit.”

### Use only after P2 evidence exists

- “The policy reduced grid-related emissions in a real operating system.”
- “The policy follows a marginal-emissions signal.”
- “On-site PV stored energy is zero-carbon for reporting.”
- “The result is externally verified, creditable, or suitable for carbon-asset issuance.”

### Delete or replace

| Do not say | Replace with |
|---|---|
| “Battery discharge is zero carbon.” | “Discharge transfers previously stored energy; its provenance is disclosed separately from source-time inventory.” |
| “Avoided curtailment equals avoided carbon.” | “Avoided curtailment is reported in kWh; any inventory difference arises through modeled source displacement.” |
| “Our hourly grid factor is marginal.” | “The scenario uses a synthetic hourly decision proxy.” |
| “C reduces carbon at the same service.” | “C shows a modelled operational-inventory difference after explicit same-service and terminal-state gates.” |
| “Carbon-SOC proves green storage.” | “Carbon-SOC is an auditable provenance ledger within the declared model boundary.” |

---

## 9. Reviewer decision

**Current status: NO-GO for Carbon-SOC carbon-performance claims.** The idea is promising as a constrained dispatch/provenance experiment, but implementation is not present in `src/`, current SOC is source-blind, terminal energy is open, and the only time-varying factor is synthetic. 

**Recommended next decision:** approve the 10-day isolated A/B/C experiment only if Day 1 pre-registration adopts the P0 controls. If the flat-factor or terminal-neutrality tests erase C’s apparent advantage, keep Carbon-SOC as an honest SOC provenance/resilience visualisation and do not force a carbon claim.
