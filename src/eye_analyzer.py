import numpy as np

class EyeAnalyzer:
    def __init__(self, samples_per_ui):
        self.samples_per_ui = samples_per_ui

    def generate_prbs_response(self, impulse_response, prbs_order=7, num_uis=1000):
        """
        Generates a PRBS-like PAM4 waveform by convolving with the impulse response
        and then folds it into an eye diagram.
        """
        # 1. Generate a long PRBS-like PAM4 sequence
        # PAM4 levels: -1.5, -0.5, 0.5, 1.5 (assuming peak normalized to 1.5)
        pam4_levels = np.array([-1.5, -0.5, 0.5, 1.5]) # PAM4 levels as per standard, for peak normalized to 1.5
        
        # The number of PRBS symbols needed depends on the length of the impulse response
        # to ensure the convolution has settled.
        min_prbs_symbols = int(np.ceil(len(impulse_response) / self.samples_per_ui)) + 10 # Add some buffer
        num_prbs_symbols = max(num_uis, min_prbs_symbols)
        prbs_symbols = np.random.choice(pam4_levels, size=num_prbs_symbols)
        
        # 2. Upsample the PRBS sequence
        upsampled_prbs = np.zeros(num_prbs_symbols * self.samples_per_ui)
        for i, symbol in enumerate(prbs_symbols):
            upsampled_prbs[i * self.samples_per_ui] = symbol
        
        # 3. Convolve the upsampled PRBS sequence with the impulse_response
        # Use 'full' mode and then trim to get the stable part.
        convolved_waveform = np.convolve(upsampled_prbs, impulse_response, mode='full')
        
        # The convolution output length is len(upsampled_prbs) + len(impulse_response) - 1.
        # We need to extract the stable part for the eye diagram.
        # Let's consider the waveform after the impulse response has fully influenced the signal.
        # This typically means starting the eye capture after `len(impulse_response)` samples.
        
        # The eye is typically viewed over 2 UI.
        eye_length_samples = 2 * self.samples_per_ui
        
        # To get a stable eye, skip the initial transient due to convolution.
        # Start index is roughly where the impulse response has "settled".
        # A common heuristic is to skip a few UI or the length of the impulse response.
        # Let's skip len(impulse_response) samples from the beginning of the convolved waveform.
        start_for_folding = len(impulse_response) -1 # The effective start of data
        
        # Ensure we have enough data for at least one full eye (2 UI) after the start.
        if (len(convolved_waveform) - start_for_folding) < eye_length_samples:
            return np.array([]) # Not enough data for an eye

        # Extract the relevant part of the waveform
        waveform_to_fold = convolved_waveform[start_for_folding:]
        
        # 4. Fold the resulting waveform into 2 UI segments to form the eye.
        num_eyes = len(waveform_to_fold) // eye_length_samples
        folded_eye = np.zeros((num_eyes, eye_length_samples))
        
        for i in range(num_eyes):
            folded_eye[i, :] = waveform_to_fold[i * eye_length_samples : (i + 1) * eye_length_samples]
            
        return folded_eye

    def get_eye_metrics(self, impulse_response, ui_time):
        """
        Analyzes the folded eye diagram to extract vertical margin, horizontal margin, and RLM.
        """
        folded_eye = self.generate_prbs_response(impulse_response)
        
        if folded_eye.size == 0:
            return {"vert_mv": 0.0, "horiz_ui": 0.0, "rlm": 0.0}

        # --- Vertical Margin (Eye Height) ---
        # Find the optimal sampling point for vertical margin.
        # This is typically the point where the eye is most open vertically.
        # Iterate over all possible sampling points within one UI.
        
        max_v_margin_units = -float('inf')
        
        # Assume scale factor for mV. The input PAM4 levels to generate_prbs_response are [-3, -1, 1, 3].
        # So a difference of 2 units between adjacent levels.
        # The prompt values are in mV. We need a conversion.
        # Let's assume `1 unit` in `folded_eye` (after convolution with symbols) represents a certain mV.
        # The total swing of PAM4 symbols is 6 units (-3 to 3).
        # If we assume an ideal PAM4 peak-to-peak swing of 300mV, then 1 unit = 50mV.
        mV_per_unit = 100.0 # Adjusted scale factor. 1 unit of folded_eye = 100mV

        for i_sample in range(self.samples_per_ui * 2): # Iterate through all samples in the 2-UI window
            samples_at_time_i = folded_eye[:, i_sample]
            
            if len(samples_at_time_i) == 0:
                continue

            # For PAM4, decision thresholds are at -1.0, 0.0, 1.0 (for symbols -1.5, -0.5, 0.5, 1.5)
            
            # Calculate vertical openings for each threshold
            v_openings_at_sp = []

            # Threshold -1.0
            samples_above_neg1 = samples_at_time_i[samples_at_time_i > -1.0]
            samples_below_neg1 = samples_at_time_i[samples_at_time_i < -1.0]
            if len(samples_above_neg1) > 0 and len(samples_below_neg1) > 0:
                v_openings_at_sp.append(np.min(samples_above_neg1) - np.max(samples_below_neg1))
            
            # Threshold 0.0
            samples_above_0 = samples_at_time_i[samples_at_time_i > 0.0]
            samples_below_0 = samples_at_time_i[samples_at_time_i < 0.0]
            if len(samples_above_0) > 0 and len(samples_below_0) > 0:
                v_openings_at_sp.append(np.min(samples_above_0) - np.max(samples_below_0))
            
            # Threshold 1.0
            samples_above_1 = samples_at_time_i[samples_at_time_i > 1.0]
            samples_below_1 = samples_at_time_i[samples_at_time_i < 1.0]
            if len(samples_above_1) > 0 and len(samples_below_1) > 0:
                v_openings_at_sp.append(np.min(samples_above_1) - np.max(samples_below_1))
            
            if len(v_openings_at_sp) > 0:
                current_v_margin_units = np.min(v_openings_at_sp)
                if current_v_margin_units > max_v_margin_units:
                    max_v_margin_units = current_v_margin_units
        
        vert_mv = max_v_margin_units * mV_per_unit # Convert to mV

        # --- Horizontal Margin (Eye Width) ---
        # Find the optimal sampling point for horizontal margin.
        # This is typically where the eye is most open horizontally, usually around the decision thresholds.
        
        # Find the times when the eye crosses the decision thresholds.
        # For simplicity, let's just use the middle decision threshold (0.0).
        # We need to find the crossing points for each trace.
        
        min_h_margin_units = float('inf')
        
        # Iterate through traces in the folded eye
        for trace in folded_eye:
            # Find zero crossings for this trace within the 2 UI window
            # A simple way: look for sign changes.
            # Convert to binary: 1 if > threshold, 0 if < threshold.
            # Then find 0->1 and 1->0 transitions.
            
            # Let's consider crossing the 0 threshold.
            zero_crossings = np.where(np.diff(np.sign(trace - 0.0)))[0]
            
            # We expect 2 crossings within the main UI for an open eye.
            # The indices are sample indices.
            if len(zero_crossings) >= 2:
                # The horizontal width is the time difference between these crossings.
                # Taking the first and last as a simplification.
                h_width_samples = zero_crossings[-1] - zero_crossings[0]
                h_width_ui = h_width_samples / self.samples_per_ui
                
                if h_width_ui < min_h_margin_units:
                    min_h_margin_units = h_width_ui
        
        if min_h_margin_units == float('inf'): # Eye completely closed horizontally
            horiz_ui = 0.0
        else:
            horiz_ui = min_h_margin_units

        # --- RLM (Relative Level Margin) ---
        # RLM is a more complex metric. For a behavioral model, we can simplify.
        # It relates to BER and noise margin.
        # For now, let's use a heuristic: RLM is proportional to vertical margin and inversely proportional to jitter.
        # For now, RLM remains a placeholder or a simple derivation if vert_mv and horiz_ui are available.
        rlm = vert_mv * horiz_ui / (ui_time * 1e12) # A very rough heuristic, needs calibration

        return {
            "vert_mv": vert_mv,
            "horiz_ui": horiz_ui,
            "rlm": rlm
        }
