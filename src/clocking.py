import numpy as np
from collections import deque

class ClockPathEngine:
    def __init__(self, tech_file_data):
        # Constants for 3nm clock distribution
        self.ps_per_mm = 6.7         # Propagation delay on metal
        self.jitter_floor_fs = 150   # Intrinsic PLL RJ
        self.jitter_per_mm_fs = 50   # Additive jitter from supply noise
        self.deskew_step_fs = 150    # Resolution of one deskew leg

    def calculate_timing_budget(self, rate_gbps, distance_um, num_deskew_legs=64):
        """
        Calculates the horizontal eye closure (Jitter Tax).
        """
        ui_ps = 1000 / rate_gbps
        dist_mm = distance_um / 1000

        # 1. Total Random Jitter (Root-Sum-Square)
        # Combines PLL jitter + path-induced jitter
        path_jitter_fs = dist_mm * self.jitter_per_mm_fs
        total_rj_fs = np.sqrt(self.jitter_floor_fs**2 + path_jitter_fs**2)
        total_rj_ps = total_rj_fs / 1000

        # 2. Deterministic Skew / Quantization
        # The best we can align is +/- half a deskew step
        residual_skew_ps = (self.deskew_step_fs / 1000) / 2
        
        # 3. Path Matching Reach
        # Maximum skew the deskew legs can compensate for
        max_correction_ps = (self.deskew_step_fs * num_deskew_legs) / 1000
        prop_delay_ps = dist_mm * self.ps_per_mm
        
        is_reachable = max_correction_ps > prop_delay_ps

        # Total Timing Tax (Horizontal Eye Closure)
        # We assume a 7-sigma RJ for 1e-12 BER
        total_tax_ps = (7 * total_rj_ps) + residual_skew_ps
        margin_ui = (ui_ps - total_tax_ps) / ui_ps

        return {
            "ui_ps": round(ui_ps, 2),
            "total_rj_ps": round(total_rj_ps, 3),
            "residual_skew_ps": round(residual_skew_ps, 3),
            "total_tax_ps": round(total_tax_ps, 2),
            "margin_ui": round(margin_ui, 3),
            "within_deskew_range": is_reachable
        }

from collections import deque

class Behavioral_CDR:
    def __init__(self, ui_ps, latency_cycles=12, pi_resolution=64):
        self.ui = ui_ps
        self.latency = latency_cycles
        self.pi_step = 1.0 / pi_resolution  # PI resolution (e.g., 1/64th of a UI)
        
        # The 'Circular Buffer' simulating hardware pipeline delay
        self.vote_buffer = deque([0] * latency_cycles)
        
        self.current_phase_offset = 0.0
        self.phase_history = []

    def update_phase(self, incoming_phase_error):
        """
        Simulates the logic delay. The vote from 'now' isn't 
        applied to the PI until 'latency_cycles' later.
        """
        # 1. Bang-Bang Phase Detector (Early/Late)
        vote = np.sign(incoming_phase_error)
        
        # 2. Inject vote into the pipeline (the buffer)
        self.vote_buffer.append(vote)
        
        # 3. Retrieve the 'stale' vote from the front of the buffer
        applied_vote = self.vote_buffer.popleft()
        
        # 4. Update the Phase Interpolator (PI) position
        self.current_phase_offset += (applied_vote * self.pi_step)
        
        # 5. Record for Histogram Analysis
        self.phase_history.append(self.current_phase_offset)
        
        return self.current_phase_offset

    def calc_tracking(self, loop_bw_mhz, jitter_profile):
        """
        Calculates the residual jitter after the CDR attempts to track it.
        """
        s_jitter_mhz = jitter_profile['freq_mhz']
        s_jitter_ui = jitter_profile['amplitude_ui']
        
        # Simplified Tracking Gain: 20dB/decade slope
        tracking_gain = 1.0 / (1 + (s_jitter_mhz / loop_bw_mhz)**2)
        residual_jitter = s_jitter_ui * (1 - tracking_gain)
        
        return residual_jitter

    def optimize_cdr_bandwidth(self, jitter_profile):
        """
        Sweeps Loop BW from 5MHz to 50MHz to find the point where
        the Horizontal Margin is maximized.
        """
        results = {}
        for bw in np.linspace(5, 50, 10):
            # Calculate residual SJ after tracking
            residual_sj = self.calc_tracking(bw, jitter_profile)
            
            # Dither penalty is a heuristic for self-inflicted noise
            dither_penalty = bw * 0.002 # Penalty increases with BW
            
            # Total Jitter = Random Jitter (RJ) + Residual SJ + Dither
            # 0.12 is the RJ floor from the previous model
            total_jitter_ui = 0.12 + residual_sj + dither_penalty
            
            # Final margin is based on total jitter
            final_margin = 0.5 - (6 * total_jitter_ui) # Using 6-sigma for BER
            results[bw] = final_margin
            
        # Return the BW that gives the highest margin
        return max(results, key=results.get), max(results.values())
