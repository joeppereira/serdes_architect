import sys
import os
import json
import yaml
import numpy as np

# Ensure src is in path
sys.path.insert(0, os.getcwd())

from src.itf_parser import ITFParser
from src.lib_parser import LibertyParser
from src.thermal import ThermalAuditor
from src.physics import SerdesPhysicsEngine
from src.timing import TimingAuditor

def execute_signoff():
    print("📋 Initializing 128G SerDes Sign-off Report...")
    
    # 1. Load Parsers
    itf = ITFParser("data/technology/process_3nm.itf")
    lib = LibertyParser("data/technology/liberty_3nm.lib")
    
    # 2. Load Optimized Config
    config_path = "config/best_config.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    
    # 3. Get the Thermal Prediction (Worst Case)
    auditor = ThermalAuditor(itf, lib)
    # Pass config to auditor to capture 'dfe_tap1_mv' penalty
    worst_rpt = auditor.generate_distribution_report(temp_c=125, config=config)
    
    # 4. Calculate Actual Operating Tj with Heat Spreading
    # Base Package Rth is 0.42 C/mW for a 10um2 compact layout.
    # Increasing area improves spreading resistance.
    base_area = 10.0
    actual_area = config.get('equalizer_parameters', {}).get('dfe_tap_area_um2', 10.0)
    
    # Simple spreading model: Rth scales with 1/sqrt(Area)
    spreading_factor = np.sqrt(actual_area / base_area)
    package_rth = 0.42 / spreading_factor
    
    # --- THERMAL CONVERGENCE LOOP ---
    # Leakage depends on Temp, and Temp depends on Power (Leakage).
    # We iterate to find the steady-state operating point.
    current_tj = 100.0 # Start with a pessimistic guess
    print(f"🔥 Thermal Audit (Converging...):")
    print(f"   Physical Layout: {actual_area} um2 (Spreading Factor: {spreading_factor:.2f}x)")
    print(f"   Effective Rth: {package_rth:.3f} C/mW")
    
    for i in range(5):
        worst_rpt = auditor.generate_distribution_report(temp_c=current_tj, config=config)
        total_mw = worst_rpt['summary']['total_power_mw']
        
        new_tj = 25.0 + (total_mw * package_rth)
        delta = abs(new_tj - current_tj)
        print(f"   Iter {i+1}: Power={total_mw:.1f}mW -> Tj={new_tj:.1f}C (Delta={delta:.1f}C)")
        
        if delta < 0.5:
            current_tj = new_tj
            break
        current_tj = new_tj

    thermal_delta_c = current_tj - 25.0
    actual_tj = current_tj
    
    print(f"   ✅ Converged Operating Tj: {actual_tj:.1f} C")

    # 5. TIMING AUDIT (New Speed Check)
    timing_auditor = TimingAuditor(config)
    timing_res = timing_auditor.check_timing(data_rate_gbps=128)
    print(f"⏱️  Timing Audit:")
    print(f"    UI Time: {timing_res['ui_ps']} ps")
    print(f"    Critical Path: {timing_res['t_dead_zone_ps']} ps (Slicer+Latch)")
    print(f"    Jitter Budget: {timing_res['t_jitter_ps']} ps")
    print(f"    Timing Margin: {timing_res['margin_ps']} ps ({timing_res['verdict']})")

    # 6. FEEDBACK LOOP: Run Physics with Actual Tj
    physics_engine = SerdesPhysicsEngine(
        touchstone_path='data/channel_400g.s4p',
        tech_file='config/tech_3nm.yaml',
        params_file=config_path
    )
    
    # Pass dfe_tap1_mv if needed, though physics engine primarily uses 'dfe_taps' array.
    # The 'tax' is applied via temperature_c.
    # We use 128Gbps as standard for this project.
    final_results, _ = physics_engine.get_full_waterfall(data_rate_gbps=128, temperature_c=actual_tj)
    
    # Extract Stage 6 (Final) metrics
    final_stage = final_results[6]

    # 7. Final Verdict Logic
    # Must pass ALL: Power (<70mW), Taxed Margins (>0.48 UI), AND Timing (>0 ps)
    is_passing = (
        total_mw < 70.0 and 
        final_stage['horiz_ui'] >= 0.48 and
        final_stage['vert_mv'] >= 36.0 and
        timing_res['verdict'] == 'PASS'
    )
    
    verdict = "PASS" if is_passing else "FAIL"

    report = {
        "design_id": "PCIe7_3nm_128G_v1",
        "verdict": verdict,
        "metrics": {
            "eye_height_mv": round(final_stage['vert_mv'], 2),
            "eye_width_ui": round(final_stage['horiz_ui'], 3),
            "tj_c": round(actual_tj, 1),
            "timing_margin_ps": timing_res['margin_ps']
        },
        "power_mw": round(total_mw, 2),
        "thermal_delta_c": round(thermal_delta_c, 2),
        "timing": timing_res,
        "typical_report": auditor.generate_distribution_report(temp_c=25, config=config),
        "worst_case_report": worst_rpt
    }
    
    with open("reports/signoff_report.json", "w") as f:
        json.dump(report, f, indent=4)
        
    print(f"✅ Sign-off Complete. Verdict: {verdict}")
    if not is_passing:
        reasons = []
        if total_mw >= 70: reasons.append(f"Power {total_mw:.1f} > 70mW")
        if final_stage['horiz_ui'] < 0.48: reasons.append(f"Horiz {final_stage['horiz_ui']:.3f} < 0.48 UI")
        if final_stage['vert_mv'] < 36.0: reasons.append(f"Vert {final_stage['vert_mv']:.1f} < 36.0 mV")
        if timing_res['verdict'] == 'FAIL': reasons.append(f"Timing Margin {timing_res['margin_ps']} ps < 0")
        
        print(f"❌ Reason: {', '.join(reasons)}")


if __name__ == "__main__":
    execute_signoff()
