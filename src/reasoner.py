import numpy as np

class PAM4MarginReasoner:
    def __init__(self, data_rate_gbps):
        self.ui_ps = 1000 / data_rate_gbps

    def evaluate_triple_eye(self, v_main_mv, isi_mv, noise_mv, ffe_results):
        """
        Calculates the margin for Top, Mid, and Bot eyes separately.
        """
        # Distribute the optimized V_main across 3 eyes
        # Ideal vertical eye height for PAM4 = V_pp / 3
        v_eye_ideal = ffe_results['v_main_optimized_mv'] / 3
        
        # Net Eye Margin = Ideal - (Residual ISI + Noise)
        # Note: We use the residual ISI from the FFE optimizer
        net_margin = v_eye_ideal - (ffe_results['residual_isi_estimate_mv'] + noise_mv)
        
        # Linearity check: If non-linearity is high, Mid eye suffers most
        eye_results = {
            "top_eye_mv": round(net_margin, 2),
            "mid_eye_mv": round(net_margin * 0.9, 2), # Heuristic for non-linearity
            "bot_eye_mv": round(net_margin, 2)
        }
        
        status = "PASS" if eye_results["mid_eye_mv"] > 15 else "FAIL"
        
        return eye_results, status

    def generate_ffe_advice(self, current_isi_mv):
        if current_isi_mv > 40:
            return "ADVICE: Heavy ISI detected. FFE C1 tap must be > 0.15 to maintain PAM4 eye linearity."
        return "System equalization is balanced."