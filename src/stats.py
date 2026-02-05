import numpy as np

class SerDesMonteCarlo:
    def __init__(self, iterations=500):
        self.iterations = iterations

    def run_yield_analysis(self, base_params):
        results = []
        for _ in range(self.iterations):
            # Apply 3-sigma variation to key behavioral "knobs"
            varied_params = {
                "latency": int(np.random.normal(base_params['latency'], 1)), # Logic speed variance
                "dfe_tap_err": np.random.normal(0, 2.0), # Summer offset in mV
                "cdr_bandwidth": np.random.normal(base_params['bw'], 1.0), # PLL variation
                "isi_measured": np.random.normal(56.96, 5.0) # Channel/Package variance
            }
            
            # Execute the behavioral model with these 'corrupted' values
            margin = self.simulate_iteration(varied_params)
            results.append(margin)
            
        return np.array(results)

    def simulate_iteration(self, p):
        # Behavioral logic: Net Margin = (Ideal - ISI) + DFE_Recovery - CDR_Tax
        # Logic matches our main app's hybrid EQ equations
        # This is a simplified behavioral model of the link budget
        ideal_v_opening = 133 # Ideal Vpp/3
        dfe_recovery = p['isi_measured'] * 0.85 + p['dfe_tap_err'] # 85% efficiency
        cdr_tax = p['latency'] * 1.5 # 1.5mV loss per ps of latency
        
        net_margin = (ideal_v_opening - p['isi_measured']) + dfe_recovery - cdr_tax
        return net_margin
