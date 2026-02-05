import numpy as np

class FFE_Optimizer:
    def solve_ffe_taps(self, isi_error_mv, v_main_mv):
        """
        Calculates the Post-cursor (c1) weight needed to cancel ISI.
        Maintains the Peak-to-Peak constraint: |c0| + |c1| = 1.0
        """
        # The 'c1' tap works against the ISI
        # Heuristic: c1 = -ISI / (Total Swing)
        total_swing = v_main_mv + isi_error_mv
        c1 = -isi_error_mv / total_swing
        c0 = 1.0 - abs(c1)
        
        # Power Tax: We lose some main cursor height to open the eye
        v_main_optimized = v_main_mv * c0
        
        # Heuristic for residual ISI: what's left after c1 tries to cancel isi_error_mv
        residual_isi_estimate_mv = isi_error_mv * (1 - abs(c1))
        
        return {
            "c0": round(c0, 3),
            "c1": round(c1, 3),
            "v_main_optimized_mv": round(v_main_optimized, 2),
            "residual_isi_estimate_mv": round(residual_isi_estimate_mv, 2),
            "pwr_tax_mw": round(abs(c1) * 8.5, 2) # Typical 3nm DAC cost
        }

    def solve_hybrid_eq(self, total_isi_mv):
        # FFE C1 (Tx) focuses on the "First UI" of damage
        ffe_contribution = total_isi_mv * 0.35 # Tx handles 35%
        
        # DFE (Rx) handles the long-tail reflections (the remaining 65%)
        # This avoids "Boosting" the high-frequency crosstalk/noise
        dfe_contribution = total_isi_mv * 0.65 
        
        # Calculate the 'Efficiency Gain'
        # DFE is 1:1 margin recovery; FFE has a 0.8:1 tax on V_main
        recovered_margin = (dfe_contribution) + (ffe_contribution * 0.8)
        
        return round(recovered_margin, 2)