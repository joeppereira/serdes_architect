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
        Calculates the power of the CDR based on latency, using a two-component model.
        Lower latency (more unrolling) increases P_parallel power, but reduces P_pipeline power.
        """
        p_per_flop = self.params['cdr']['cdr_p_per_flop_mw']
        p_base_unroll = self.params['cdr']['cdr_p_base_unroll_mw']
        baseline_latency = self.params['cdr']['cdr_baseline_latency_cycles']

        # P_pipeline: Power from pipeline registers (decreases with latency)
        # Assuming fixed stages for now, proportional to latency
        p_pipeline = latency_cycles * p_per_flop

        # P_parallel: Power from parallel paths (increases as latency decreases)
        # Models the unroll tax: more parallel paths for lower latency
        unroll_tax_factor = baseline_latency / latency_cycles
        p_parallel = p_base_unroll * unroll_tax_factor
        
        cdr_power = p_pipeline + p_parallel
        return cdr_power
