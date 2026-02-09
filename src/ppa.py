import yaml

class SiliconCostEngine:
    def __init__(self, tech_file='config/tech_3nm.yaml', params_file='config/parameters.yaml'):
        with open(tech_file, 'r') as f:
            self.tech = yaml.safe_load(f)
        
        # Load behavioral model parameters
        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)

    def calculate_ppa(self, rate_gbps, num_taps, latency_cycles=12):
        # Calculate power for different blocks
        # DFE Power: Scales with number of taps and per-tap power factor
        dfe_pwr = num_taps * self.params['equalizer_parameters']['dfe_tap_pwr_mw_factor']
        
        # AFE Power: Sum of CTLE, VGA, and ADC power factors
        afe_pwr = (self.params['equalizer_parameters']['ctle']['ctle_power_per_stage_mw_factor'] * 3) + \
                   self.params['equalizer_parameters']['vga_power_mw_factor'] + \
                   self.params['equalizer_parameters']['adc_7bit_power_mw_factor']
        
        # CDR Power: Calculated based on latency, includes "unroll tax"
        cdr_pwr = self.calculate_cdr_power(latency_cycles)
        
        # PLL Power: Base power for the Phase-Locked Loop
        pll_pwr = self.params['clocking_parameters']['pll_base_power_mw_factor']
        
        # Total Power: Sum of all components
        total_pwr = dfe_pwr + afe_pwr + pll_pwr + cdr_pwr
        
        # Total Area: Simplified heuristic based on DFE taps and a fixed base area
        total_area = (num_taps * self.params['equalizer_parameters']['dfe_tap_area_um2']) + 1500
        
        return {
            "power_mw": round(total_pwr, 2),
            "energy_pj_bit": round(total_pwr / rate_gbps, 3),
            "area_um2": round(total_area, 2)
        }

    def calculate_cdr_power(self, latency_cycles):
        """
        Calculates the power of the CDR based on latency.
        Lower latency (more unrolling) costs more power due to increased logic.
        """
        # Heuristic: CDR power is inversely proportional to latency, relative to a baseline.
        # This models the "unroll tax" where faster CDR (lower latency) implies more hardware.
        
        baseline_latency = self.params['cdr']['baseline_latency_cycles']
        baseline_cdr_power = self.params['cdr']['cdr_power_mw_factor']
        
        # Unroll Tax Factor: How much power increases as we reduce latency from the baseline
        unroll_tax_factor = baseline_latency / latency_cycles
        
        cdr_power = baseline_cdr_power * unroll_tax_factor
        return cdr_power
