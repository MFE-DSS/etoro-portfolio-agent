from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import datetime

@dataclass
class EngineInputs:
    timestamp_utc: str
    pmi_level: Optional[float]
    pmi_trend_3m: str
    labor_proxy: str
    labor_trend: str
    cpi_yoy: Optional[float]
    cpi_change_3m: str
    us2y_level: Optional[float]
    us2y_trend_2m: str
    risk_proxy: str
    risk_trend: str
    optional_context_flags: Dict[str, bool] = field(default_factory=dict)

class CoreMacroRegimeEngineV1:
    """
    Deterministic system evaluating a Pareto set of exactly 5 inputs to derive
    macro regime and asset allocation for the core portfolio.
    """

    def evaluate(self, inputs: EngineInputs) -> tuple[Dict[str, Any], List[str]]:
        # A) Growth score
        growth_signal = self._compute_growth_signal(inputs)
        
        # B) Inflation signal
        inflation_signal = self._compute_inflation_signal(inputs)
        
        # C) Conditions signal
        conditions_signal = self._compute_conditions_signal(inputs)
        
        # D) Risk stress
        risk_stress = self._compute_risk_stress(inputs)
        
        # Regime Decision
        regime_base = self._get_base_quadrant(growth_signal, inflation_signal)
        regime_overlay = self._get_recession_overlay(growth_signal, risk_stress)
        
        # Confidence Scoring
        confidence = self._compute_confidence(inputs, growth_signal, inflation_signal, risk_stress)
        
        # Core Bucket Size
        core_bucket_pct = self._get_core_bucket_size(confidence)
        
        # Core Allocation
        allocation = self._get_core_allocation(regime_base, regime_overlay, risk_stress, inputs.optional_context_flags)
        
        # Risk Controls
        risk_controls = self._get_risk_controls(confidence)
        
        # Monitoring
        monitoring = self._get_monitoring_list()
        
        # Rationale builder
        rationale = self._build_rationale(inputs, growth_signal, inflation_signal, conditions_signal, risk_stress, regime_base, regime_overlay, confidence)
        
        output = {
            "timestamp_utc": inputs.timestamp_utc,
            "regime_base": regime_base,
            "regime_overlay": regime_overlay,
            "confidence": confidence,
            "signals": {
                "growth_signal": growth_signal,
                "inflation_signal": inflation_signal,
                "conditions_signal": conditions_signal,
                "risk_stress": risk_stress
            },
            "core_bucket_percent_of_total": core_bucket_pct,
            "core_allocation_percent_of_core": allocation,
            "risk_controls": risk_controls,
            "monitoring_next_2_weeks": monitoring
        }
        
        return output, rationale

    def _compute_growth_signal(self, inputs: EngineInputs) -> str:
        # growth_signal = "up" if (pmi_level >= 50 AND pmi_trend_3m == "up") OR (pmi_trend_3m=="up" AND labor_trend=="down")
        # growth_signal = "down" if (pmi_level < 50) OR (pmi_trend_3m=="down" AND labor_trend=="up")
        # else "mixed"
        p_lvl = inputs.pmi_level if inputs.pmi_level is not None else 50.0  # fallback
        p_up = inputs.pmi_trend_3m == "up"
        p_dn = inputs.pmi_trend_3m == "down"
        l_up = inputs.labor_trend == "up"  # labor stress up = bad for growth
        l_dn = inputs.labor_trend == "down" # labor stress down = good for growth

        if (p_lvl >= 50 and p_up) or (p_up and l_dn):
            return "up"
        if (p_lvl < 50) or (p_dn and l_up):
            return "down"
        return "mixed"

    def _compute_inflation_signal(self, inputs: EngineInputs) -> str:
        if inputs.cpi_change_3m == "up":
            return "up"
        if inputs.cpi_change_3m == "down":
            return "down"
        return "mixed"

    def _compute_conditions_signal(self, inputs: EngineInputs) -> str:
        if inputs.us2y_trend_2m == "up":
            return "tightening"
        if inputs.us2y_trend_2m == "down":
            return "easing"
        return "neutral"

    def _compute_risk_stress(self, inputs: EngineInputs) -> bool:
        if inputs.risk_trend == "up":
            return True
        if inputs.optional_context_flags.get("energy_supply_shock", False) or \
           inputs.optional_context_flags.get("major_geopolitical_escalation", False):
            return True
        return False

    def _get_base_quadrant(self, g: str, i: str) -> str:
        if g == "up" and i == "down":
            return "Goldilocks"
        if g == "up" and i == "up":
            return "Reflation"
        if g == "down" and i == "up":
            return "Stagflation"
        if g == "down" and i == "down":
            return "Disinflation"
        return "Transition"

    def _get_recession_overlay(self, g: str, r_stress: bool) -> str:
        if g == "down" and r_stress:
            return "Recession-risk"
        return "None"

    def _compute_confidence(self, inputs: EngineInputs, g: str, i: str, r_stress: bool) -> int:
        score = 80
        if g == "mixed": score -= 15
        if i == "mixed": score -= 15
        
        has_na = any(t == "na" for t in [
            inputs.pmi_trend_3m, inputs.labor_trend, inputs.cpi_change_3m,
            inputs.us2y_trend_2m, inputs.risk_trend
        ])
        if has_na: score -= 10
        if r_stress: score -= 10
        
        if not has_na and g != "mixed" and i != "mixed":
            score += 5
            
        return max(0, min(100, score))

    def _get_core_bucket_size(self, confidence: int) -> int:
        if confidence >= 75: return 80
        if confidence >= 55: return 70
        return 60

    def _get_core_allocation(self, base: str, overlay: str, r_stress: bool, flags: dict) -> List[Dict[str, int]]:
        agg_w = {}

        # Default Templates
        if base == "Goldilocks":
            agg_w = {
                "Global Equities - Quality": 60,
                "Global Equities - Value/Cyclicals": 25,
                "Broad Commodities": 5,
                "Cash-like / T-bills": 10
            }
        elif base == "Reflation":
            agg_w = {
                "Global Equities - Quality": 40,
                "Global Equities - Value/Cyclicals": 30,
                "Broad Commodities": 10,
                "Energy Tilt": 10,
                "Cash-like / T-bills": 10
            }
        elif base == "Stagflation":
            agg_w = {
                "Defensive Equities": 40,
                "Broad Commodities": 15,
                "Energy Tilt": 10,
                "Gold": 10,
                "Cash-like / T-bills": 25
            }
        elif base == "Disinflation":
            agg_w = {
                "Global Equities - Quality": 35,
                "Defensive Equities": 25,
                "Duration (Bonds)": 20,
                "Cash-like / T-bills": 20
            }
        else: # Transition
            agg_w = {
                "Global Equities - Quality": 40,
                "Defensive Equities": 20,
                "Cash-like / T-bills": 40
            }

        # Apply Recession-Risk Overlay
        if overlay == "Recession-risk":
            # De-risk
            new_w = {
                "Defensive Equities": 35,
                "Cash-like / T-bills": 45,
                "Global Equities - Quality": 15
            }
            if flags.get("energy_supply_shock", False):
                new_w["Energy Tilt"] = 5
                new_w["Cash-like / T-bills"] -= 5
            else:
                new_w["Duration (Bonds)"] = 5
                new_w["Cash-like / T-bills"] -= 5
            agg_w = new_w
            
        # Ensure Duration is omitted if Risk Stress is high AND it wasn't a recession overlay ignoring duration
        if r_stress and "Duration (Bonds)" in agg_w and overlay != "Recession-risk":
             val = agg_w.pop("Duration (Bonds)")
             agg_w["Cash-like / T-bills"] = agg_w.get("Cash-like / T-bills", 0) + val

        # Normalize to 100
        total = sum(agg_w.values())
        if total == 0:
            agg_w = {"Cash-like / T-bills": 100}
        else:
            # simple normalization, put rounding remainder in Cash
            allocated = 0
            res = []
            for k, w in agg_w.items():
                pct = int(round(w / total * 100))
                res.append({"asset": k, "weight": pct})
                allocated += pct
            
            diff = 100 - allocated
            if diff != 0:
                for i, r in enumerate(res):
                    if r["asset"] == "Cash-like / T-bills":
                        res[i]["weight"] += diff
                        break
                else:
                    res[0]["weight"] += diff
            return res
            
        return [{"asset": k, "weight": w} for k, w in agg_w.items() if w > 0]

    def _get_risk_controls(self, conf: int) -> Dict[str, Any]:
        return {
            "rebalance_frequency": "twice-monthly" if conf < 55 else "monthly",
            "drawdown_trigger_pct": 5,
            "de_risk_pct_points": 10
        }

    def _get_monitoring_list(self) -> List[Dict[str, str]]:
        return [
            {"metric": "PMI/ISM", "watch": "3M trend persistence and cross-over of 50 barrier."},
            {"metric": "Labor proxy", "watch": "Inflection in claims or NFP trend indicating late-cycle labor cooling."},
            {"metric": "Risk proxy", "watch": "Spike in VIX or widening of HY OAS signaling liquidity/stress events."}
        ]

    def _build_rationale(self, inputs: EngineInputs, g: str, i: str, c: str, r: bool, base: str, ovly: str, conf: int) -> List[str]:
        bullets = []
        
        # Growth
        g_reason = f"Growth signal is {g.upper()} driven by PMI trend '{inputs.pmi_trend_3m}' " \
                   f"(level {inputs.pmi_level}) and {inputs.labor_proxy} trend '{inputs.labor_trend}'."
        bullets.append(g_reason)
        
        # Inflation
        i_reason = f"Inflation signal is {i.upper()} driven by CPI 3M trend '{inputs.cpi_change_3m}' " \
                   f"(level {inputs.cpi_yoy}%)."
        bullets.append(i_reason)
        
        # Conditions / Risk
        r_reason = f"Financial conditions proxy (US 2Y) is {c.upper()}."
        bullets.append(r_reason)
        
        if r:
            flags_str = ", ".join([k for k, v in inputs.optional_context_flags.items() if v])
            s = f"Risk stress is HIGH (proxy: {inputs.risk_proxy} trend '{inputs.risk_trend}')"
            if flags_str:
                s += f" supplemented by flags: {flags_str}."
            bullets.append(s)
        else:
            bullets.append(f"Risk stress is constrained (proxy: {inputs.risk_proxy} trend '{inputs.risk_trend}').")
            
        # Regime Decision
        reg_reason = f"Base quadrant mapped to {base} based on Growth/Inflation mix."
        if ovly != "None":
            reg_reason += f" Applied overlay: {ovly} due to elevated risk stress paired with poor growth."
        bullets.append(reg_reason)
        
        # Sizing
        size_reason = f"Confidence score {conf}/100 supports a CORE bucket size of {self._get_core_bucket_size(conf)}%."
        bullets.append(size_reason)
        
        return bullets
