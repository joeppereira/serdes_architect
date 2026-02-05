import numpy as np

class ContributionDiagnostic:
    def __init__(self, ideal_sbr, measured_waveform, ui_time):
        self.ideal_sbr = ideal_sbr
        self.measured = measured_waveform
        self.ui = ui_time

    def detect_contributions(self):
        # 1. Detect ISI Contribution
        # Find the peak of the SBR to locate the main cursor
        cursor_idx = np.argmax(self.measured)
        samples_per_ui = 64 # Should be consistent with physics.py

        # Create indices for sampling at UI intervals around the main cursor
        # We'll look at a window of +/- 20 UI for ISI
        num_isi_taps = 20
        pre_cursor_indices = range(cursor_idx - num_isi_taps * samples_per_ui, cursor_idx, samples_per_ui)
        post_cursor_indices = range(cursor_idx + samples_per_ui, cursor_idx + num_isi_taps * samples_per_ui, samples_per_ui)
        
        # Ensure indices are within the bounds of the array
        pre_cursor_indices = [i for i in pre_cursor_indices if i >= 0]
        post_cursor_indices = [i for i in post_cursor_indices if i < len(self.measured)]
        
        pre_cursor_isi = np.sum(np.abs(self.measured[pre_cursor_indices]))
        post_cursor_isi = np.sum(np.abs(self.measured[post_cursor_indices]))
        
        isi_impact = pre_cursor_isi + post_cursor_isi
        
        # 2. Detect Jitter Contribution (The Horizontal-to-Vertical Tax)
        # Uses the "Slope Method": Eye Closure = Jitter_rms * dV/dt
        # We find the steepest part of the SBR to get dV/dt
        slope = (np.max(self.measured) - self.measured[np.argmax(self.measured)-5]) / (5 * (self.ui/64))
        measured_rj = self.calculate_rms_jitter(self.measured)
        jitter_tax = slope * measured_rj
        
        # 3. Detect Noise/Cross-talk
        # Measured at the center of the UI where the slope is zero (i.e., the peak)
        # This is another heuristic; it assumes noise at the peak is representative.
        center_noise = np.std(self.measured[np.argmax(self.measured)-32:np.argmax(self.measured)+32])
        
        return {
            "ISI_Contribution_mV": round(isi_impact * 1000, 2),
            "Jitter_Tax_mV": round(jitter_tax * 1000, 2),
            "Crosstalk_Noise_mV": round(center_noise * 1000, 2)
        }

    def calculate_rms_jitter(self, waveform):
        # Simplified TIE (Time Interval Error) logic
        # Real-world: Extract threshold crossings and compare to ideal clock
        # This is a placeholder as we don't have a clock signal to compare against.
        return 0.15 * self.ui # Returns 15% UI as a placeholder
