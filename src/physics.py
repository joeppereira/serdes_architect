import numpy as np
import skrf as rf
import yaml
from scipy.fft import irfft, rfftfreq

class MultiRatePhysicsEngine:
    def __init__(self, touchstone_path, tech_file='config/tech_3nm.yaml', samples_per_ui=64):
        with open(tech_file, 'r') as f:
            self.tech = yaml.safe_load(f)
        
        self.target_z0 = self.tech['impedance_matching']['target_z0']
        self.rx_term_z = self.tech['impedance_matching']['rx_term_z']
        
        self.network = rf.Network(touchstone_path)
        # Convert 4-port single-ended to differential with the target impedance
        # First, we set the single-ended impedance of each port.
        self.network.z0 = self.target_z0 / 2
        # Then, we convert to mixed-mode. The resulting differential impedance will be 2 * z0.
        self.network.se2gmm(p=2) # This modifies self.network in place
        self.samples_per_ui = samples_per_ui
        
    def get_sbr(self, data_rate_gbps):
        """
        Generates SBR for multiple stages of the SerDes link.
        Returns: sbr_tx, sbr_channel, sbr_ctle, sbr_dfe, ui_time
        """
        ui_time = 1e-12 * (1000 / data_rate_gbps)
        dt = ui_time / self.samples_per_ui
        n_fft = 2**16
        freqs = rfftfreq(n_fft, d=dt)

        # --- Stage 1: Tx Output (Ideal Pulse) ---
        pulse = np.ones(self.samples_per_ui)
        sbr_tx = np.zeros(n_fft)
        sbr_tx[:self.samples_per_ui] = pulse
        
        # --- Stage 2: Rx Input (Post-Channel) ---
        new_net = self.network.interpolate(rf.Frequency.from_f(freqs, unit='hz'), kind='linear', fill_value='extrapolate')
        sdd21 = new_net.s[:, 1, 0]
        bw_limit = 0.75 * (data_rate_gbps * 1e9)
        h_driver = 1 / (1 + (1j * freqs / bw_limit)**4)
        impulse_channel = irfft(sdd21 * h_driver, n=n_fft)
        sbr_channel = np.convolve(impulse_channel, pulse, mode='full') / self.samples_per_ui
        sbr_channel = sbr_channel[:n_fft] # Truncate to match other stages

        # --- Stage 3: Post-CTLE ---
        # The user's description is slightly ambiguous. The CTLE is in the freq domain.
        # So, we should apply it to the frequency response, not the time-domain sbr.
        h_ctle = self.apply_ctle_freq_domain(freqs, data_rate_gbps)
        impulse_ctle = irfft(sdd21 * h_driver * h_ctle, n=n_fft)
        sbr_ctle = np.convolve(impulse_ctle, pulse, mode='full') / self.samples_per_ui
        sbr_ctle = sbr_ctle[:n_fft]

        # --- Stage 4: Post-DFE & CDR (Reflection Tax) ---
        gamma_rx = (self.rx_term_z - self.target_z0) / (self.rx_term_z + self.target_z0)
        reflection_pulse = np.roll(sbr_ctle, self.samples_per_ui * 2) * gamma_rx
        sbr_dfe = sbr_ctle + reflection_pulse
        
        return sbr_tx, sbr_channel, sbr_ctle, sbr_dfe, ui_time

    def apply_ctle_freq_domain(self, freqs, data_rate_gbps):
        """Generates the CTLE transfer function H(s)."""
        f_nyquist = (data_rate_gbps / 2) * 1e9
        w_z = 2 * np.pi * (f_nyquist / 4)
        w_p1 = 2 * np.pi * (f_nyquist * 1.5)
        w_p2 = 2 * np.pi * (f_nyquist * 2.0)
        s = 1j * 2 * np.pi * freqs
        h_ctle = (s + w_z) / ((s + w_p1) * (s + w_p2))
        h_ctle /= (w_z / (w_p1 * w_p2))
        return h_ctle
        
    def get_nyquist_loss(self, rate_gbps):
        """Reasoning helper: Quick check on channel difficulty."""
        f_nyquist = (rate_gbps / 2) * 1e9
        loss_db = self.network.s_db[np.argmin(np.abs(self.network.f - f_nyquist)), 1, 0]
        if loss_db == -np.inf:
            # If loss is infinite (S-parameter is 0), return a large finite loss
            return -100.0
        return loss_db
