import pandas as pd
import numpy as np

class PAM4ScopeParser:
    def __init__(self, csv_path):
        # Load raw scope data [Time, Voltage]
        self.df = pd.read_csv(csv_path)
        self.time = self.df.iloc[:, 0].values
        self.voltage = self.df.iloc[:, 1].values

    def normalize_levels(self):
        """
        Detects the 4 PAM4 levels (-3, -1, +1, +3) from the waveform histogram
        and centers the data.
        """
        # Create a histogram of voltages to find the 4 'peaks' (the levels)
        hist, bin_edges = np.histogram(self.voltage, bins=100)
        # Find the 4 highest peaks in the histogram
        # This is a heuristic and may need refinement for very noisy signals
        peak_indices_sorted_by_hist = np.argsort(hist)
        # We need to find peaks that are spread out, not just the highest bins next to each other
        # A simple way to do this is to take the 4 highest peaks, and then ensure they are distinct enough.
        # For now, let's just take the 4 highest, assuming they correspond to the PAM4 levels.
        potential_levels = []
        for idx in peak_indices_sorted_by_hist[::-1]: # Iterate from highest bin
            if bin_edges[idx] not in potential_levels: # Check for uniqueness
                potential_levels.append(bin_edges[idx])
            if len(potential_levels) == 4:
                break
        
        levels = np.sort(np.array(potential_levels))
        
        # Center the waveform based on the mean of the detected levels
        offset = np.mean(levels)
        self.voltage = self.voltage - offset
        
        return np.sort(levels - offset)

    def resample_to_ui(self, ui_ps, samples_per_ui=64):
        """Aligns scope data to the simulation grid."""
        # Normalize time to start at 0
        normalized_time = self.time - self.time[0]
        
        dt = (ui_ps * 1e-12) / samples_per_ui
        new_time = np.arange(normalized_time[0], normalized_time[-1], dt)
        
        # Ensure new_time does not exceed the original time range
        # np.interp requires new_time to be within the bounds of normalized_time
        new_time = new_time[new_time <= normalized_time[-1]]

        resampled_v = np.interp(new_time, normalized_time, self.voltage)
        return resampled_v