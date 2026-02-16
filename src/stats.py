import numpy as np
import yaml

class SerDesMonteCarlo:
    def __init__(self, iterations=500, params_file='config/parameters.yaml'):
        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)
        self.iterations = iterations

    def run_yield_analysis(self, base_params):
        results = []
        for _ in range(self.iterations):
            varied_params = {
                "latency": int(np.random.normal(base_params['latency'], self.params['monte_carlo']['parameters']['latency_sigma_ps'])),
                "dfe_tap_err": np.random.normal(0, self.params['monte_carlo']['parameters']['dfe_tap_err_sigma_mv']),
                "cdr_bandwidth": np.random.normal(base_params['bw'], self.params['monte_carlo']['parameters']['cdr_bandwidth_sigma_mhz']),
                "isi_measured": np.random.normal(self.params['monte_carlo']['parameters']['isi_measured_mean'], self.params['monte_carlo']['parameters']['isi_measured_sigma_mv'])
            }
            margin = self.simulate_iteration(varied_params)
            results.append(margin)
        return np.array(results)

    def simulate_iteration(self, p):
        ideal_v_opening = self.params['behavioral_model']['ideal_v_opening']
        dfe_recovery = p['isi_measured'] * self.params['behavioral_model']['dfe_efficiency'] + p['dfe_tap_err']
        cdr_tax = p['latency'] * self.params['behavioral_model']['cdr_tax_per_ps']
        net_margin = (ideal_v_opening - p['isi_measured']) + dfe_recovery - cdr_tax
        return net_margin