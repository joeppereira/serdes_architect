import numpy as np
import sys
import matplotlib.pyplot as plt
sys.path.insert(0, './')
from src.clocking import Behavioral_CDR
from src.ppa import SiliconCostEngine

def run_cdr_optimization_sweep(rate_gbps=128):
    print(f"\n{'='*50}")
    print(f"  CDR BANDWIDTH OPTIMIZATION ({rate_gbps}Gbps)")
    print(f"{'='*50}\n")
    
    # 1. Initialize Engines
    # We don't need a specific CDR instance yet, just the class methods
    cdr_model = Behavioral_CDR(ui_ps=(1000/rate_gbps))
    ppa_engine = SiliconCostEngine()

    # 2. Define Jitter Profile to be Optimized Against
    jitter_profile = {'freq_mhz': 100, 'amplitude_ui': 0.3}
    
    # 3. Run the Bandwidth Optimization
    optimal_bw, best_margin = cdr_model.optimize_cdr_bandwidth(jitter_profile)
    print(f"Optimal CDR Loop Bandwidth found: {optimal_bw:.2f} MHz (yielding {best_margin:.3f} UI Margin)\n")
    
    # --- PPA & Horizontal Margin Trade-off Table ---
    print("--- CDR Architecture PPA Impact ---")
    print(f"{'CDR Strategy':<25} | {'Latency (Cycles)':<20} | {'Horizontal Margin (UI)':<25} | {'Power Tax (mW)':<15}")
    print(f"{'-'*25} | {'-'*20} | {'-'*25} | {'-'*15}")
    
    # Define CDR Strategies to compare
    cdr_strategies = [
        {'name': 'Standard Loop', 'latency': 12},
        {'name': 'Predictive PI', 'latency': 4},
        {'name': 'Speculative / Unrolled', 'latency': 1},
    ]

    for strategy in cdr_strategies:
        # Calculate Power Tax for this latency
        power_tax = ppa_engine.calculate_cdr_power(strategy['latency'])
        
        # Calculate Horizontal Margin using the optimal bandwidth
        # This is a simplified model where we assume the optimized margin is affected by latency
        # A more complex model would re-calculate the margin for each latency
        latency_penalty = strategy['latency'] * 0.01 # Heuristic: 1% margin loss per cycle of latency
        final_horiz_margin = best_margin - latency_penalty
        
        print(f"{strategy['name']:<25} | {strategy['latency']:<20} | {final_horiz_margin:<25.3f} | {power_tax:<15.2f}")

    print(f"\nARCHITECT'S VERDICT: By optimizing the CDR loop bandwidth to {optimal_bw:.2f} MHz, we can achieve a robust timing margin. The table clearly shows the trade-off: reducing latency to 1 cycle ('Speculative' mode) provides the best horizontal margin ({best_margin:.3f} UI before latency penalty), but at the highest power cost. This allows the architect to make an informed decision based on the project's specific PPA goals.")

if __name__ == "__main__":
    try:
        run_cdr_optimization_sweep()
    except Exception as e:
        print(f"An error occurred: {e}")
