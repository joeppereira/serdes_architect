import yaml

class SiliconCostEngine:
    def __init__(self, tech_file='config/tech_3nm.yaml'):
        with open(tech_file, 'r') as f:
            self.tech = yaml.safe_load(f)

    def calculate_ppa(self, rate_gbps, num_taps, latency_cycles=12):
        # Power scales with frequency and tap count
        dfe_pwr = num_taps * self.tech['equalization_legs']['dfe_tap_pwr_mw']
        afe_pwr = (self.tech['analog_front_end']['ctle_power_per_stage_mw'] * 3) + \
                   self.tech['analog_front_end']['vga_power_mw'] + \
                   self.tech['analog_front_end']['adc_7bit_power_mw']
        
        cdr_pwr = self.calculate_cdr_power(latency_cycles)
        
        total_pwr = dfe_pwr + afe_pwr + self.tech['clocking']['pll_base_power_mw'] + cdr_pwr
        total_area = (num_taps * self.tech['equalization_legs']['dfe_tap_area_um2']) + 1500
        
        return {
            "power_mw": round(total_pwr, 2),
            "energy_pj_bit": round(total_pwr / rate_gbps, 3),
            "area_um2": round(total_area, 2)
        }

    def calculate_cdr_power(self, latency_cycles):
        """
        Calculates the power of the CDR based on latency.
        Lower latency (more unrolling) costs more power.
        """
        # Heuristic: Power is inversely proportional to latency, relative to a baseline.
        # Let's assume a baseline latency of 24 cycles for the baseline CDR power.
        baseline_latency = 24
        baseline_cdr_power = self.tech['clocking']['cdr_power_mw']
        
        # Unroll Tax: Power increases as we reduce latency from the baseline
        unroll_tax_factor = baseline_latency / latency_cycles
        
        cdr_power = baseline_cdr_power * unroll_tax_factor
        return cdr_power
