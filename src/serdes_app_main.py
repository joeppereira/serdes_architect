import numpy as np
import sys
import matplotlib.pyplot as plt
import argparse
import yaml

sys.path.insert(0, './')

from src.physics import SerdesPhysicsEngine
from src.clocking import Behavioral_CDR
from src.ppa import SiliconCostEngine
from src.optimizer import FFE_Optimizer
from src.visualizer import SerDesVisualizer
from src.stats import SerDesMonteCarlo

# --- Main Calculation Function ---

def calculate_final_margins(v_margin_post_dfe, vertical_jitter_tax, total_jitter_ui, ber_sigma):
    """
    Calculates the final vertical and horizontal margins based on post-DFE vertical margin
    and CDR-derived jitter metrics.
    """
    final_h_margin = 0.5 - (ber_sigma * total_jitter_ui)
    final_v_margin = v_margin_post_dfe - vertical_jitter_tax
    
    return final_v_margin, final_h_margin

def _format_output_contract(waterfall_results, final_v_margin, final_h_margin, total_power, params, config_id="default_run", tx_ffe_taps=None, channel_loss_db=None, cdr_mode="speculative", ambient_temp_c=25.0):
    
    # Extract impulse responses, we don't include them in the contract output directly.
    # Convert stage results to a more compact dictionary format for the contract.
    contract_stages = {}
    for stage_idx, stage_data in waterfall_results.items():
        contract_stages[stage_idx] = {
            "vert_mv": stage_data["vert_mv"],
            "horiz_ui": stage_data["horiz_ui"],
            "rlm": stage_data["rlm"],
            "power_mw": stage_data["power_mw"],
            "temp_c": stage_data["temp_c"]
        }

    # Default tx_ffe_taps if not provided (should be passed from phy_engine)
    if tx_ffe_taps is None:
        tx_ffe_taps = params['equalizer_parameters']['tx_ffe']['default_preset']
    
    # Default channel_loss_db if not provided (should be calculated from phy_engine)
    if channel_loss_db is None:
        # Placeholder for actual calculation, perhaps from phy_engine.get_nyquist_loss()
        channel_loss_db = -36.0 # Placeholder
    else:
        channel_loss_db = float(channel_loss_db) # Ensure native float
        
    yield_pass = bool(final_h_margin > params['simulation']['pass_threshold_mv_horizontal_ui'] and 
                  final_v_margin > params['simulation']['pass_threshold_mv'])

    simulation_result = {
        "config_id": config_id,
        "ffe_taps": tx_ffe_taps,
        "channel_loss_db": channel_loss_db,
        "cdr_mode": cdr_mode,
        "ambient_temp_c": ambient_temp_c,
        "stages": contract_stages,
        "ber_estimate": 1e-12, # Placeholder, will be calculated later
        "eye_height_mv": final_v_margin,
        "eye_width_ui": final_h_margin,
        "total_power_mw": total_power, # Need to pass this to the function
        "max_junction_temp_c": 25.0, # Placeholder
        "yield_pass": yield_pass,
        "runtime_sec": 0.0 # Placeholder
    }
    return simulation_result

# --- Analysis Functions ---

def run_baseline_analysis(params, rate_gbps=128, channel_path='data/channel_400g.s4p', quiet=False, config_id="default_run"):
    print(f"\n{'='*50}")
    print(f"  SERDES ARCHITECT: BASELINE ANALYSIS (128G) [Config: {config_id}]")
    print(f"{ '='*50}\n")
    
    # 1. Initialize Engines
    phy_engine = SerdesPhysicsEngine(channel_path, tech_file='config/tech_3nm.yaml', params_file='config/parameters.yaml')
    ffe_optimizer = FFE_Optimizer(params_file='config/parameters.yaml')
    cdr = Behavioral_CDR(
        ui_ps=(1000/rate_gbps), 
        latency_cycles=params['cdr']['speculative_latency_cycles'],
        pi_resolution=params['cdr']['pi_resolution'],
        params_file='config/parameters.yaml'
    )
    ppa_engine = SiliconCostEngine(params_file='config/parameters.yaml')
    viz_engine = SerDesVisualizer(ui_ps=(1000/rate_gbps))

    # 2. Get the Multi-Stage Waveforms
    waterfall_results, ui_time = phy_engine.get_full_waterfall(rate_gbps)
    
    # 3. Run FFE Optimization
    ffe_results = ffe_optimizer.solve_ffe_taps(waterfall_results[5]['impulse_response'])
    
    # 4. Calculate Final Margins
    jitter_profile = {'freq_mhz': 100, 'amplitude_ui': 0.05}
    loop_bw_mhz = 20
    total_jitter_ui = cdr.calculate_residual_jitter(jitter_profile, loop_bw_mhz)
    vertical_jitter_tax = cdr.calculate_vertical_jitter_tax(waterfall_results[5]['impulse_response'], total_jitter_ui)
    
    v_margin_post_dfe = params['ppa_table_data'][3]['vertical_margin_mv']
    final_v_margin, final_h_margin = calculate_final_margins(v_margin_post_dfe, vertical_jitter_tax, total_jitter_ui, params['cdr']['ber_sigma'])

    # Calculate total power (regardless of quiet mode)
    total_power = 0.0
    for stage_idx in sorted(waterfall_results.keys()):
        total_power += waterfall_results[stage_idx]["power_mw"]
    cdr_power = ppa_engine.calculate_cdr_power(params['cdr']['speculative_latency_cycles'])
    total_power += cdr_power

    if not quiet:
        # --- PPA Table (Waterfall Format) ---
        print("\n--- PPA & Yield Table (Waterfall) ---")
        print(f"{'Architecture Stage':<28} | {'Vertical Margin (mV)':<20} | {'Horizontal Margin (UI)':<25} | {'Power (mW)':<15} | {'Temp (°C)':<15}")
        print(f"{'-'*28} | {'-'*20} | {'-'*25} | {'-'*15} | {'-'*15}")
        
        for stage_idx in sorted(waterfall_results.keys()):
            stage_data = waterfall_results[stage_idx]
            description = stage_data["description"]
            vert_mv = stage_data["vert_mv"]
            horiz_ui = stage_data["horiz_ui"]
            power_mw = stage_data["power_mw"]
            temp_c = stage_data["temp_c"]

            print(f"{description:<28} | {vert_mv:<20.2f} | {horiz_ui:<25.3f} | {power_mw:<15.2f} | {temp_c:<15.2f}")
        
        print(f"{'- Jitter Tax (from CDR)':<28} | {-vertical_jitter_tax:<20.2f} | {'N/A':<25} | {cdr_power:<15.2f} | {'N/A':<15} (Unroll Tax)")
        
        print(f"{'-'*28} | {'-'*20} | {'-'*25} | {'-'*15} | {'-'*15}")
        print(f"{'Final Net Margin':<28} | {final_v_margin:<20.2f} | {final_h_margin:<25.3f} | {total_power:<15.2f} | {'N/A':<15}")
        
        print(f"\n--- CDR Report ---")
        print(f"  - CDR Loop Bandwidth:      {loop_bw_mhz} MHz")
        print(f"  - Input Jitter Freq:       {jitter_profile['freq_mhz']} MHz")
        print(f"  - Input Jitter Amplitude:  {jitter_profile['amplitude_ui']:.3f} UI")
        print(f"  - RJ Floor:                {params['cdr']['rj_floor_ui']:.3f} UI")
        print(f"  - Total Residual Jitter:   {total_jitter_ui:.3f} UI")
        print(f"  - Final Horizontal Margin: {final_h_margin:.3f} UI")
        print(f"    (Equation: 0.5 - ({params['cdr']['ber_sigma']} * {total_jitter_ui:.3f}))")
        
        print(f"\nFFE Taps: {ffe_results['taps']}")
        print(f"Total Energy Efficiency: {total_power / rate_gbps:.3f} pJ/bit")

        # 5. Visualize the Signal Flow
        print("\nGenerating 4-Panel Signal Integrity Dashboard...")
        
        # Extract impulse responses for visualization
        # We need to map the 7 stages to the 4 panels the visualizer expects.
        # This will be a temporary mapping for now.
        # Stages are: 0:Raw TX, 1:TX FFE, 2:Channel, 3:CTLE, 4:RX FFE, 5:DFE, 6:Final
        # Let's pick a representative subset for the 4-panel view.
        
        # Original: sbr_tx, sbr_channel, sbr_ctle, sbr_dfe
        # Mapping to new stages:
        # sbr_tx -> waterfall_results[0]['impulse_response'] (Raw TX)
        # sbr_channel -> waterfall_results[2]['impulse_response'] (Post-Channel)
        # sbr_ctle -> waterfall_results[3]['impulse_response'] (Post-Analog CTLE)
        # sbr_dfe -> waterfall_results[5]['impulse_response'] (Post-1-tap DFE)
        
        stages_data_for_viz = [
            waterfall_results[0]['impulse_response'],
            waterfall_results[2]['impulse_response'],
            waterfall_results[3]['impulse_response'],
            waterfall_results[5]['impulse_response']
        ]
        viz_engine.plot_multistage_analysis(stages_data_for_viz)
        
        print(f"\n{'='*50}")

    # 6. Format Output Contract
    # For now, derive cdr_mode from the parameter used for CDR instantiation.
    # This might need to be refined if CDR has dynamic modes.
    # For now, we assume if speculative_latency_cycles is used, then cdr_mode is "speculative".
    cdr_mode_str = "speculative" # Default for now based on current setup.

    simulation_result = _format_output_contract(
        waterfall_results=waterfall_results,
        final_v_margin=final_v_margin,
        final_h_margin=final_h_margin,
        total_power=total_power,
        params=params,
        config_id=config_id,
        tx_ffe_taps=phy_engine.tx_ffe_taps, # Already a list from parameters.yaml
        channel_loss_db=phy_engine.get_nyquist_loss(rate_gbps),
        cdr_mode=cdr_mode_str,
        ambient_temp_c=params['global_sweep_parameters']['ambient_temp_c']
    )
    return simulation_result, waterfall_results

def run_global_sensitivity_sweep(final_v_margin_from_baseline, params):
    print(f"\n{'='*50}")
    print("  GLOBAL SENSITIVITY SWEEP (128G)")
    print(f"{ '='*50}\n")
    
    baseline_nyquist_loss = params['global_sweep_parameters']['baseline_nyquist_loss']
    loss_sensitivity_factor = params['global_sweep_parameters']['loss_sensitivity_factor']
    pass_threshold_mv = params['global_sweep_parameters']['pass_threshold_mv']
    
    losses = params['global_sweep_parameters']['losses']
    results = []
    for loss in losses:
        current_v_margin = final_v_margin_from_baseline - (loss - baseline_nyquist_loss) * loss_sensitivity_factor
        status = "PASS" if current_v_margin > pass_threshold_mv else "FAIL"
        results.append((loss, current_v_margin, 0, status))
        print(f"Loss: -{loss}dB | Margin: {current_v_margin:.2f}mV | [{status}]")

    if results:
        passing_results = [r for r in results if r[3] == "PASS"]
        if passing_results:
            max_loss_pass = max(passing_results, key=lambda item: item[0])[0]
            summary = f"The link maintains a passing margin up to a channel loss of -{max_loss_pass}dB."
        else:
            summary = "The link fails at all tested channel losses."
        print(f"\nSWEEP SUMMARY: {summary}")

    print(f"\n{'='*50}")


def run_monte_carlo_analysis(params, sbr_dfe, ui_time, iterations=500):
    print(f"\n{'='*50}")
    print(f"  SERDES MONTE CARLO YIELD ANALYSIS ({iterations} iterations)")
    print(f"{ '='*50}\n")
    
    mc_engine = SerDesMonteCarlo(iterations=iterations, params_file='config/parameters.yaml')
    
    # Construct base_params expected by SerDesMonteCarlo
    base_params_for_mc = {
        "latency": params['monte_carlo']['base_latency'],
        "bw": params['monte_carlo']['base_bw']
    }
    
    margin_results = mc_engine.run_yield_analysis(base_params_for_mc)
    
    mean_margin = np.mean(margin_results)
    std_dev = np.std(margin_results)
    
    margin_3_sigma = mean_margin - (3 * std_dev)
    pass_threshold_mv = params['simulation']['pass_threshold_mv']
    yield_percent = (np.sum(margin_results > pass_threshold_mv) / iterations) * 100
    
    print("--- Monte Carlo Yield Report ---")
    print(f"Mean Margin: {mean_margin:.2f} mV")
    print(f"3-Sigma (Worst Case): {margin_3_sigma:.2f} mV")
    print(f"Confidence / Yield: {yield_percent:.2f}%")
    
    if yield_percent > 99.7:
        verdict = f"Silicon Ready! The design is robust against process variations, with a 3-sigma worst-case margin of {margin_3_sigma:.2f} mV and a yield of {yield_percent:.2f}%."
    elif yield_percent > 90:
        verdict = f"High Risk. While the mean margin is good ({mean_margin:.2f} mV), the 3-sigma tail ({margin_3_sigma:.2f} mV) dips below the pass threshold. Yield may be impacted."
    else:
        verdict = f"Guaranteed Fail. The design is not robust, with a 3-sigma margin of {margin_3_sigma:.2f} mV. Significant yield loss is expected. Re-evaluate circuit specs."
    print(f"\nARCHITECT'S VERDICT: {verdict}")
    
    plt.figure(figsize=(10, 6))
    plt.hist(margin_results, bins=50, density=True, alpha=0.7, label='Margin Distribution')
    plt.axvline(mean_margin, color='red', linestyle='--', label=f'Mean: {mean_margin:.2f} mV')
    plt.axvline(margin_3_sigma, color='orange', linestyle='--', label=f'3-Sigma: {margin_3_sigma:.2f} mV')
    plt.axvline(pass_threshold_mv, color='green', linestyle='--', label=f'Pass Threshold: {pass_threshold_mv:.2f} mV')
    plt.title("Monte Carlo Simulation: Vertical Margin Distribution")
    plt.xlabel("Vertical Margin (mV)")
    plt.ylabel("Probability Density")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show(block=True)
    
    print(f"\n{'='*50}")

# --- Main Entry Point ---
def main():
    parser = argparse.ArgumentParser(description="SerDes Architect Suite for 128G PAM4 links.")
    parser.add_argument('--sweep', action='store_true', help="Run global sensitivity sweep.")
    parser.add_argument('--monte-carlo', action='store_true', help="Generate Monte Carlo yield report.")
    parser.add_argument('--all', action='store_true', help="Run all analyses (baseline, sweep, and Monte Carlo).")
    parser.add_argument('--config-id', type=str, default="default_run", help="Unique ID for the simulation run.")
    
    args = parser.parse_args()

    with open('config/parameters.yaml', 'r') as f:
        params = yaml.safe_load(f)

    # Always run baseline analysis to get the core simulation_result
    # The quiet flag is managed internally by run_baseline_analysis
    simulation_result, waterfall_results = run_baseline_analysis(params, config_id=args.config_id)

    # If the request is only for baseline, we can print the contract and exit here.
    import json
    import os
    
    # Save simulation result to file
    output_dir = "simulation_result"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_file = os.path.join(output_dir, f"{args.config_id}.json")
    with open(output_file, "w") as f:
        json.dump(simulation_result, f, indent=2)
    print(f"\nSimulation result saved to {output_file}")

    if not (args.sweep or args.monte_carlo):
        print("\n--- Phase 1 Output Contract ---")
        print(json.dumps(simulation_result, indent=2))
        return

    # Extract necessary values for subsequent analysis functions
    final_v_margin = simulation_result["eye_height_mv"]
    final_h_margin = simulation_result["eye_width_ui"]
    # waterfall_results from simulation_result are already structured with "stages" key.
    # We need the impulse response from stage 5 for Monte Carlo.
    sbr_dfe_impulse = waterfall_results[5]['impulse_response']
    
    # ui_time is not directly in the contract, but it's used by Monte Carlo.
    # We need to ensure ui_time is derived consistently.
    # For now, let's derive it from the params data rate.
    # This assumes rate_gbps is 128. If it changes, this needs to be dynamically derived.
    rate_gbps = 128 # This should eventually come from params or simulation_result
    ui_time = 1e-12 * (1000 / rate_gbps) # Recalculate for Monte Carlo

    if args.sweep or args.all:
        run_global_sensitivity_sweep(final_v_margin, params)

    if args.monte_carlo or args.all:
        # run_monte_carlo_analysis expects `sbr_dfe` which is an impulse response.
        run_monte_carlo_analysis(params, sbr_dfe_impulse, ui_time)

if __name__ == "__main__":
    main()
