import yaml

class TransmitterPowerEngine:
    def __init__(self, tech_file='config/tech_3nm.yaml'):
        with open(tech_file, 'r') as f:
            self.tech = yaml.safe_load(f)

    def calculate_tx_power(self, target_z0=85):
        """
        Calculates the power of the transmitter driver, scaling with impedance.
        Lower impedance requires more drive current, thus more power.
        """
        driver_legs = self.tech['equalization_legs']['main_driver_legs']
        # We assume the configured power-per-leg is for a 100-Ohm reference design
        pwr_per_leg_at_100_ohm = self.tech['equalization_legs']['tx_driver_pwr_per_leg_mw']
        
        # Driver power scales inversely with impedance (P = V^2 / R)
        impedance_scaling_factor = 100 / target_z0
        
        # Scale the power per leg based on the actual target impedance
        pwr_per_leg_actual = pwr_per_leg_at_100_ohm * impedance_scaling_factor
        
        tx_power = driver_legs * pwr_per_leg_actual
        
        return {
            "tx_power_mw": round(tx_power, 2)
        }
