import numpy as np
import yaml
from collections import deque

class ClockPathEngine:
    def __init__(self, tech_file_data, params_file='config/parameters.yaml'):
        # Load behavioral model parameters
        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)

        # Constants for 3nm clock distribution
        self.ps_per_mm = self.params['clock_path_parameters']['ps_per_mm']
        self.jitter_floor_fs = tech_file_data['clocking']['pll_rj_rms_fs'] # Use from tech_file as before
        self.jitter_per_mm_fs = self.params['clock_path_parameters']['jitter_per_mm_fs']
        self.deskew_step_fs = self.params['clock_path_parameters']['deskew_step_fs']

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
    def __init__(self, ui_ps, latency_cycles, pi_resolution, params_file='config/parameters.yaml'):
        # Load behavioral model parameters
        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)

        self.ui = ui_ps
        self.latency = latency_cycles
        self.pi_step = 1.0 / pi_resolution
        
        # The 'Circular Buffer' simulating hardware pipeline delay
        self.vote_buffer = deque([0] * self.latency)
        
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

    def calculate_vertical_jitter_tax(self, sbr_dfe, residual_jitter_rms_ui):
        """
        Calculates the vertical margin loss due to Jitter-to-Voltage conversion.
        """
        # 1. Convert residual jitter from UI to ps
        residual_jitter_rms_ps = residual_jitter_rms_ui * self.ui
        
        # 2. Calculate dV/dt (slew rate) of the final eye
        sbr_derivative = np.gradient(sbr_dfe)
        dv_dt_v_per_sample = np.max(np.abs(sbr_derivative))
        dt_ps = self.ui / 64
        dv_dt_mv_per_ps = (dv_dt_v_per_sample * 1000) / dt_ps
        
        # 3. Calculate the Jitter Tax
        vertical_margin_loss_mv = residual_jitter_rms_ps * dv_dt_mv_per_ps
        
        return round(vertical_margin_loss_mv, 2)
        
    def calculate_residual_jitter(self, jitter_profile, loop_bw_mhz):
        """
        Calculates the residual jitter after the CDR attempts to track it.
        """
        s_jitter_mhz = jitter_profile['freq_mhz']
        s_jitter_ui = jitter_profile['amplitude_ui']
        
        # Simplified Tracking Gain (Jitter Transfer Function)
        # This is a high-pass filter: CDR tracks out low-freq jitter.
        tracking_gain = (s_jitter_mhz / loop_bw_mhz)**2 / (1 + (s_jitter_mhz / loop_bw_mhz)**2)
        residual_sj = s_jitter_ui * tracking_gain

        # Total Jitter = Random Jitter (RJ) + Residual SJ
        rj_floor_ui = self.params['cdr']['rj_floor_ui']
        total_jitter_ui = np.sqrt(rj_floor_ui**2 + residual_sj**2)
        
        return total_jitter_ui
