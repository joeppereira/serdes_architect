import numpy as np
import sys
import matplotlib.pyplot as plt
import argparse
import yaml

sys.path.insert(0, './')

from src.physics import MultiRatePhysicsEngine
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

# --- Analysis Functions ---

def run_baseline_analysis(params, rate_gbps=128, channel_path='data/channel_400g.s4p'):
    print(f"\n{'='*50}")
    print("  SERDES ARCHITECT: BASELINE ANALYSIS (128G)")
    print(f"{ '='*50}\n")
    
    # 1. Initialize Engines
    phy_engine = MultiRatePhysicsEngine(channel_path, tech_file='config/tech_3nm.yaml', params_file='config/parameters.yaml')
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
    sbr_tx, sbr_channel, sbr_ctle, sbr_dfe, ui_time = phy_engine.get_sbr(rate_gbps)
    
    # 3. Run FFE Optimization
    ffe_results = ffe_optimizer.solve_ffe_taps(sbr_dfe)
    
    # Calculate DFE Power
    dfe_power = ppa_engine.calculate_ppa(rate_gbps, num_taps=4, latency_cycles=params['cdr']['speculative_latency_cycles'])['power_mw'] # Simplified power calc for DFE

    # 3. Calculate Final Margins
    # First, calculate the jitter from the CDR model
    jitter_profile = {'freq_mhz': 100, 'amplitude_ui': 0.05}
    loop_bw_mhz = 20
    total_jitter_ui = cdr.calculate_residual_jitter(jitter_profile, loop_bw_mhz)
    vertical_jitter_tax = cdr.calculate_vertical_jitter_tax(sbr_dfe, total_jitter_ui)
    
    # Then, pass the results to the unified margin calculation
    v_margin_post_dfe = params['ppa_table_data'][-2]['vertical_margin_mv']
    final_v_margin, final_h_margin = calculate_final_margins(v_margin_post_dfe, vertical_jitter_tax, total_jitter_ui, params['cdr']['ber_sigma'])

    # --- PPA Table (Waterfall Format) ---
    print("\n--- PPA & Yield Table (Waterfall) ---")
    print(f"{ 'Architecture Stage':<25} | { 'Vertical Margin (mV)':<20} | { 'Horizontal Margin (UI)':<25} | { 'Power (mW)':<15}")
    print(f"{'-'*25} | {'-'*20} | {'-'*25} | {'-'*15}")
    
    ppa_table_data = params['ppa_table_data']
    total_power = 0

    for row in ppa_table_data[:-1]:
        print(f"{row['stage_name']:<25} | {row['vertical_margin_mv']:<20.2f} | {'N/A':<25} | {row['power_mw']:<15.2f}")
        total_power += row['power_mw']
    
    cdr_power = ppa_engine.calculate_cdr_power(params['cdr']['speculative_latency_cycles'])
    total_power += cdr_power
    print(f"{ ' - Jitter Tax (from CDR)':<25} | {-vertical_jitter_tax:<20.2f} | {'N/A':<25} | {cdr_power:<15.2f} (Unroll Tax)")
    
    print(f"{'-'*25} | {'-'*20} | {'-'*25} | {'-'*15}")
    print(f"{'Final Net Margin':<25} | {final_v_margin:<20.2f} | {final_h_margin:<25.3f} | {total_power:<15.2f}")
    
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
    stages_data = [sbr_tx, sbr_channel, sbr_ctle, sbr_dfe]
    viz_engine.plot_multistage_analysis(stages_data)
    
    print(f"\n{'='*50}")


def run_global_sensitivity_sweep(params):
    print(f"\n{'='*50}")
    print("  GLOBAL SENSITIVITY SWEEP (128G)")
    print(f"{ '='*50}\n")
    
    baseline_v_margin = params['global_sweep_parameters']['baseline_v_margin']
    baseline_nyquist_loss = params['global_sweep_parameters']['baseline_nyquist_loss']
    loss_sensitivity_factor = params['global_sweep_parameters']['loss_sensitivity_factor']
    pass_threshold_mv = params['global_sweep_parameters']['pass_threshold_mv']
    
    losses = params['global_sweep_parameters']['losses']
    results = []
    for loss in losses:
        current_v_margin = baseline_v_margin - (loss - baseline_nyquist_loss) * loss_sensitivity_factor
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


def run_monte_carlo_analysis(params, iterations=500):
    print(f"\n{'='*50}")
    print(f"  SERDES MONTE CARLO YIELD ANALYSIS ({iterations} iterations)")
    print(f"{ '='*50}\n")
    
    # 1. Initialize Engine
    mc_engine = SerDesMonteCarlo(iterations=iterations, params_file='config/parameters.yaml')
    
    # 2. Define Base Parameters for the Monte Carlo Simulation
    base_params = {
        'latency': params['monte_carlo']['base_latency'],
        'bw': params['monte_carlo']['base_bw'],
    }
    
    # 3. Run the Yield Analysis
    # The new run_yield_analysis no longer takes params and calculate_final_margins as arguments.
    margin_results = mc_engine.run_yield_analysis(base_params)
    
    # 4. Calculate Final Statistics
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
    parser.add_argument('--baseline', action='store_true', help="Run baseline analysis (Virtual Oscilloscope). (Default if no other argument is given)")
    
    args = parser.parse_args()

    with open('config/parameters.yaml', 'r') as f:
        params = yaml.safe_load(f)

    if args.sweep:
        run_global_sensitivity_sweep(params)
    elif args.monte_carlo:
        run_monte_carlo_analysis(params)
    elif args.baseline:
        run_baseline_analysis(params)
    else:
        print("No specific analysis selected. Running Baseline Analysis by default.")
        run_baseline_analysis(params)

if __name__ == "__main__":
    main()
