import numpy as np
import yaml

class FFE_Optimizer:
    def __init__(self, params_file='config/parameters.yaml'):
        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)
        
        self.ffe_params = self.params['equalizer_parameters']['ffe']
        self.num_taps = self.ffe_params['num_taps']
        self.tap_positions = self.ffe_params['tap_positions']
        self.coeff_ranges = self.ffe_params['coefficient_ranges']
        self.resolution = 2**self.ffe_params['resolution_bits']

    def solve_ffe_taps(self, initial_sbr, learning_rate=0.01, iterations=100):
        """
        Simulates an adaptive FFE to find optimal tap weights.
        Uses a simplified gradient descent to minimize residual ISI.
        """
        # Start with a default preset
        taps = np.array(self.ffe_params['default_preset'], dtype=float)
        
        # --- Simplified Gradient Descent ---
        for _ in range(iterations):
            # 1. Apply the FFE to the SBR
            # This is a convolution in the time domain
            equalized_sbr = np.convolve(initial_sbr, taps, mode='same')
            
            # 2. Calculate Residual ISI
            # This is a simplified error function for our gradient descent
            cursor_idx = np.argmax(equalized_sbr)
            isi_error = np.sum(np.abs(equalized_sbr[cursor_idx + self.resolution::self.resolution])) + \
                        np.sum(np.abs(equalized_sbr[:cursor_idx - self.resolution:self.resolution]))
            
            # 3. Calculate Gradient (Simplified)
            # The gradient tells us which direction to move the taps
            # to reduce the ISI error.
            gradient = np.zeros_like(taps)
            # For post-cursor taps, if ISI is positive, we need to make tap more negative.
            # We'll just model the first post-cursor for this simplified gradient.
            if len(taps) > 3: # Need at least 4 taps
                post_cursor_slice = equalized_sbr[cursor_idx + self.resolution: cursor_idx + 2*self.resolution]
                if post_cursor_slice.size > 0:
                    gradient[3] = np.mean(post_cursor_slice) * -1
            
            # 4. Update Taps
            taps += learning_rate * gradient
            
            # 5. Constrain Taps
            taps[0] = np.clip(taps[0], self.coeff_ranges['c_neg2'][0], self.coeff_ranges['c_neg2'][1])
            taps[1] = np.clip(taps[1], self.coeff_ranges['c_neg1'][0], self.coeff_ranges['c_neg1'][1])
            taps[2] = np.clip(taps[2], self.coeff_ranges['c0'][0], self.coeff_ranges['c0'][1])
            taps[3] = np.clip(taps[3], self.coeff_ranges['c_pos1'][0], self.coeff_ranges['c_pos1'][1])

        # Final calculations
        final_equalized_sbr = np.convolve(initial_sbr, taps, mode='same')
        v_main_optimized_mv = np.max(final_equalized_sbr) * 1000
        
        cursor_idx = np.argmax(final_equalized_sbr)
        pre_cursor_slice = final_equalized_sbr[:cursor_idx-self.resolution:self.resolution]
        post_cursor_slice = final_equalized_sbr[cursor_idx+self.resolution::self.resolution]

        pre_cursor_isi = np.sum(np.abs(pre_cursor_slice)) if pre_cursor_slice.size > 0 else 0
        post_cursor_isi = np.sum(np.abs(post_cursor_slice)) if post_cursor_slice.size > 0 else 0
        residual_isi_mv = (pre_cursor_isi + post_cursor_isi) * 1000
        
        # Power tax based on the non-main taps
        pwr_tax_mw = (np.sum(np.abs(taps)) - taps[2]) * self.params['ppa_cost']['ffe_power_mw']
        
        return {
            "taps": {f"c{pos}": round(val, 3) for pos, val in zip(self.tap_positions, taps)},
            "v_main_optimized_mv": round(v_main_optimized_mv, 2),
            "residual_isi_estimate_mv": round(residual_isi_mv, 2),
            "pwr_tax_mw": round(pwr_tax_mw, 2)
        }

