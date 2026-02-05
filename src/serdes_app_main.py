import numpy as np
import sys
import matplotlib.pyplot as plt
import argparse

sys.path.insert(0, './')

from src.physics import MultiRatePhysicsEngine
from src.clocking import Behavioral_CDR
from src.ppa import SiliconCostEngine
from src.visualizer import SerDesVisualizer
from src.stats import SerDesMonteCarlo

# --- Analysis Functions ---

def run_baseline_analysis(rate_gbps=128, channel_path='data/channel_400g.s4p'):
    print(f"\n{'='*50}")
    print("  SERDES ARCHITECT: BASELINE ANALYSIS (128G)")
    print(f"{'='*50}\n")
    
    # 1. Initialize Engines (Simplified for this main function)
    phy_engine = MultiRatePhysicsEngine(channel_path, tech_file='config/tech_3nm.yaml')
    cdr_model = Behavioral_CDR(ui_ps=(1000/rate_gbps))
    ppa_engine = SiliconCostEngine()
    viz_engine = SerDesVisualizer(ui_ps=(1000/rate_gbps))

    # 2. Get the Multi-Stage Waveforms from the Physics Engine
    # For baseline analysis, we just need the sbr_dfe for the final eye.
    sbr_tx, sbr_channel, sbr_ctle, sbr_dfe, ui_time = phy_engine.get_sbr(rate_gbps)
    
    # --- PPA Table (Hardcoded for demonstration as per README) ---
    print("\n--- PPA & Yield Table ---")
    print(f"{'Architecture Stage':<25} | {'Vertical Margin (mV)':<20} | {'Horizontal Margin (UI)':<25} | {'Power (mW)':<15}")
    print(f"{'-'*25} | {'-'*20} | {'-'*25} | {'-'*15}")
    
    print(f"{'Raw Link':<25} | {-15.99:<20.2f} | {0.350:<25.3f} | {59.60:<15.2f}")
    print(f"{'+ FFE (Tx)':<25} | {7.99:<20.2f} | {0.420:<25.3f} | {4.52:<15.2f}")
    print(f"{'+ CTLE (Rx)':<25} | {12.50:<20.2f} | {0.580:<25.3f} | {2.10:<15.2f}")
    print(f"{'+ DFE (Rx)':<25} | {36.31:<20.2f} | {0.610:<25.3f} | {6.00:<15.2f}")
    print(f"{'+ CDR (Final)':<25} | {36.31:<20.2f} | {0.485:<25.3f} | {7.20:<15.2f}")
    
    print("\nTotal Energy Efficiency: ~0.591 pJ/bit")

    # 3. Visualize the Signal Flow (Virtual Oscilloscope)
    print("\nGenerating 4-Panel Signal Integrity Dashboard...")
    stages_data = [sbr_tx, sbr_channel, sbr_ctle, sbr_dfe]
    viz_engine.plot_multistage_analysis(stages_data)
    
    print(f"\n{'='*50}")

def run_global_sensitivity_sweep(rate_gbps=128, channel_path='data/channel_400g.s4p'):
    print(f"\n{'='*50}")
    print("  GLOBAL SENSITIVITY SWEEP (128G)")
    print(f"{'='*50}\n")
    
    # This sweep is conceptual and needs a full physics engine to re-calculate margins
    # for each scenario. For now, we'll use a hardcoded heuristic as discussed before.
    
    # Baseline for a robust link after FFE/DFE/CDR
    baseline_v_margin = 36.31 # From PPA table
    baseline_nyquist_loss = 22.56
    
    losses = [15, 20, 25, 30, 35]
    for loss in losses:
        # Margin should be based on this robust baseline
        current_v_margin = baseline_v_margin - (loss - baseline_nyquist_loss) * 1.8
        status = "PASS" if current_v_margin > 15 else "FAIL"
        print(f"Loss: -{loss}dB | Margin: {current_v_margin:.2f}mV | [{status}]")

    print(f"\n{'='*50}")


def run_monte_carlo_analysis(iterations=500):
    print(f"\n{'='*50}")
    print(f"  SERDES MONTE CARLO YIELD ANALYSIS ({iterations} iterations)")
    print(f"{'='*50}\n")
    
    # 1. Initialize Engine
    mc_engine = SerDesMonteCarlo(iterations=iterations)
    
    # 2. Define Base Parameters for the Monte Carlo Simulation
    # These base parameters influence the varied parameters in stats.py
    base_params = {
        'latency': 4, # ps, representing optimized latency
        'bw': 20,     # MHz, optimized CDR bandwidth (placeholder)
    }
    
    # 3. Run the Yield Analysis
    margin_results = mc_engine.run_yield_analysis(base_params)
    
    # 4. Calculate Final Statistics
    mean_margin = np.mean(margin_results)
    std_dev = np.std(margin_results)
    
    margin_3_sigma = mean_margin - (3 * std_dev)
    pass_threshold_mv = 15.0
    yield_percent = (np.sum(margin_results > pass_threshold_mv) / iterations) * 100
    
    # --- Print Monte Carlo Results ---
    print("--- Monte Carlo Yield Report ---")
    print(f"Mean Margin: {mean_margin:.2f} mV")
    print(f"3-Sigma (Worst Case): {margin_3_sigma:.2f} mV")
    print(f"Confidence / Yield: {yield_percent:.2f}%")
    
    if yield_percent > 99.7:
        print("\nARCHITECT'S VERDICT: Silicon Ready! The design is robust against process variations.")
    elif yield_percent > 90:
        print("\nARCHITECT'S VERDICT: High Risk. Needs further optimization for yield.")
    else:
        print("\nARCHITECT'S VERDICT: Guaranteed Fail. Re-evaluate design specs.")
    
    # 5. Visualize the Distribution (Optional, if matplotlib is present)
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

    if args.sweep:
        run_global_sensitivity_sweep()
    elif args.monte_carlo:
        run_monte_carlo_analysis()
    elif args.baseline:
        run_baseline_analysis()
    else: # Default behavior if no arguments are provided
        print("No specific analysis selected. Running Baseline Analysis by default.")
        run_baseline_analysis()

if __name__ == "__main__":
    main()