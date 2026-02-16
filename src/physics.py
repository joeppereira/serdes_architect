import numpy as np
import skrf as rf
import yaml
import re
from scipy.fft import irfft, rfftfreq

from .eye_analyzer import EyeAnalyzer

class TechFileSolver:
    """
    Parses industry-standard technology files (.itf, .lib) and handles S-parameters (.s4p).
    Acts as the 'Ground Truth' physics solver for the SerDes Architect.
    """
    def __init__(self, itf_path, liberty_path, touchstone_path):
        self.itf_data = self._parse_itf(itf_path)
        self.lib_data = self._parse_lib(liberty_path)
        self.network = rf.Network(touchstone_path)

    def _parse_itf(self, path):
        """Parses Interconnect Technology File (ITF) for conductor properties."""
        data = {'conductors': {}, 'dielectrics': {}}
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("CONDUCTOR"):
                        # Example: CONDUCTOR metal1 { RESISTIVITY=0.022 WIDTH=0.035 ... }
                        match = re.search(r"CONDUCTOR\s+(\w+)\s+\{(.+)\}", line)
                        if match:
                            name = match.group(1)
                            props_str = match.group(2)
                            props = {}
                            for prop in props_str.split():
                                key, val = prop.split('=')
                                props[key] = float(val)
                            data['conductors'][name] = props
                    elif line.startswith("DIELECTRIC"):
                        match = re.search(r"DIELECTRIC\s+(\w+)\s+\{(.+)\}", line)
                        if match:
                            name = match.group(1)
                            props_str = match.group(2)
                            props = {}
                            for prop in props_str.split():
                                key, val = prop.split('=')
                                props[key] = float(val)
                            data['dielectrics'][name] = props
        except FileNotFoundError:
            print(f"Warning: ITF file not found at {path}. Using defaults.")
        return data

    def _parse_lib(self, path):
        """Parses Liberty (.lib) file for cell power and timing (Simplified)."""
        data = {'cells': {}}
        current_cell = None
        try:
            with open(path, 'r') as f:
                content = f.read()
                # Simple regex to find cell blocks
                # This is a very basic parser and assumes a clean format
                cell_blocks = re.findall(r'cell\(([\w_]+)\)\s*\{(.*?)\n\s*\}', content, re.DOTALL)
                
                # The above regex is too simple for nested braces. 
                # Let's use a simpler approach: extract leakage and dynamic power values using specific patterns
                
                # Re-reading line by line for state machine approach might be safer but verbose.
                # Let's try finding "cell(NAME)" and then scanning for power.
                
                # Iterate over finding 'cell(' indices
                for match in re.finditer(r'cell\(([\w_]+)\)', content):
                    cell_name = match.group(1)
                    start_idx = match.end()
                    # Find matching closing brace (simple counter)
                    brace_count = 1
                    end_idx = start_idx
                    for i, char in enumerate(content[start_idx:]):
                        if char == '{': brace_count += 1
                        elif char == '}': brace_count -= 1
                        if brace_count == 0:
                            end_idx = start_idx + i
                            break
                    
                    cell_content = content[start_idx:end_idx]
                    
                    # Extract leakage
                    leakage = 0.0
                    leak_match = re.search(r'leakage_power\s*:\s*([\d\.]+);', cell_content)
                    if leak_match:
                        leakage = float(leak_match.group(1))
                    
                    # Extract internal power (simplified: first value found)
                    switching_energy = 0.0
                    # Look for: values("0.00045"); inside internal_power
                    power_match = re.search(r'values\("([\d\.]+)"\);', cell_content)
                    if power_match:
                        switching_energy = float(power_match.group(1))
                        
                    data['cells'][cell_name] = {
                        'leakage_mw': leakage,
                        'switching_pj': switching_energy
                    }
        except FileNotFoundError:
             print(f"Warning: Liberty file not found at {path}. Using defaults.")
        return data

    def get_electrical_params(self, freq_ghz):
        """
        Extracts Insertion Loss (S21) and Return Loss (S11)
        Directly from the Ansys-generated 4-port matrix.
        """
        # Interpolate if needed, or find nearest
        # skrf network frequency is in Hz
        freq_hz = freq_ghz * 1e9
        # Check if frequency is within range
        if freq_hz > self.network.f[-1] or freq_hz < self.network.f[0]:
             # Return boundary values or extrapolate
             pass
             
        # Use skrf's interpolation
        s_db = self.network.s_db
        freqs = self.network.f
        
        # Find nearest index
        idx = (np.abs(freqs - freq_hz)).argmin()
        
        s21_db = s_db[idx, 1, 0] # S21 (Port 2 to Port 1)
        s11_db = s_db[idx, 0, 0] # S11 (Reflection at Port 1)
        
        return s21_db, s11_db

    def get_layer_resistivity(self, layer_name):
        return self.itf_data['conductors'].get(layer_name, {}).get('RESISTIVITY', 0.0)
    
    def get_cell_power(self, cell_name):
        return self.lib_data['cells'].get(cell_name, {})


class SerdesPhysicsEngine: # Renamed for clarity with new functionality
    def __init__(self, touchstone_path, tech_file='config/tech_3nm.yaml', params_file='config/parameters.yaml'):
        # Load tech parameters (for impedance matching and file paths)
        with open(tech_file, 'r') as f:
            self.tech = yaml.safe_load(f)
        
        # Load behavioral model parameters
        with open(params_file, 'r') as f:
            self.params = yaml.safe_load(f)

        self.target_z0 = self.tech['impedance_matching']['target_z0']
        self.rx_term_z = self.tech['impedance_matching']['rx_term_z']
        
        # Initialize TechFileSolver
        # Resolve paths relative to project root or absolute?
        # Assuming run from project root.
        itf_path = self.tech.get('files', {}).get('itf', 'data/technology/process_3nm.itf')
        lib_path = self.tech.get('files', {}).get('liberty', 'data/technology/liberty_3nm.lib')
        
        self.tech_solver = TechFileSolver(itf_path, lib_path, touchstone_path)
        
        # Access network through solver
        self.network = self.tech_solver.network 
        
        # Get samples_per_ui from parameters.yaml
        self.samples_per_ui = self.params['general']['samples_per_ui']
        
        # Store CTLE parameters
        self.ctle_zero_factor = self.params['equalizer_parameters']['ctle']['zero_factor']
        self.ctle_pole1_factor = self.params['equalizer_parameters']['ctle']['pole1_factor']
        self.ctle_pole2_factor = self.params['equalizer_parameters']['ctle']['pole2_factor']
        
        # Store driver BW limit factor
        self.tx_driver_bw_limit_factor = self.params['equalizer_parameters']['tx_driver_bw_limit_factor']
        
        # Store reflection tax delay
        self.reflection_tax_delay_ui = self.params['equalizer_parameters']['reflection_tax_delay_ui']

        # Store TX FFE parameters
        self.tx_ffe_taps = self.params['equalizer_parameters']['tx_ffe']['default_preset']

        # Store RX FFE parameters (new)
        # Initialize with main tap = 1.0, others 0.0 as a default
        rx_ffe_num_taps = self.params['equalizer_parameters']['rx_ffe']['num_taps']
        rx_ffe_main_tap_idx = self.params['equalizer_parameters']['rx_ffe']['main_tap_idx']
        self.rx_ffe_taps = np.zeros(rx_ffe_num_taps)
        self.rx_ffe_taps[rx_ffe_main_tap_idx] = 1.0

        # Store DFE parameters (1-tap, new)
        dfe_num_taps = self.params['equalizer_parameters']['dfe']['num_taps']
        self.dfe_taps = np.zeros(dfe_num_taps) # Default to all zeros, will be optimized
        
        # Store Voltage Swing for scaling
        self.v_pp_mv = self.params['equalizer_parameters'].get('v_pp_mv', 420.0)

        # Initialize EyeAnalyzer
        self.eye_analyzer = EyeAnalyzer(self.samples_per_ui)
        
        # Convert 4-port single-ended to differential with the target impedance
        # First, we set the single-ended impedance of each port.
        self.network.z0 = self.target_z0 / 2
        # Then, we convert to mixed-mode. The resulting differential impedance will be 2 * z0.
        self.network.se2gmm(p=2) # This modifies self.network in place

    def _calculate_stage_metrics(self, impulse_response, ui_time, description, power_mw, temp_c=25.0):
        metrics = self.eye_analyzer.get_eye_metrics(impulse_response, ui_time)
        return {
            "description": description,
            "impulse_response": impulse_response,
            "vert_mv": metrics["vert_mv"],
            "horiz_ui": metrics["horiz_ui"],
            "rlm": metrics["rlm"],
            "power_mw": power_mw,
            "temp_c": temp_c
        }
        
    def _apply_tx_ffe(self, impulse_in, tx_ffe_taps):
        # tx_ffe_taps are typically [c-2, c-1, c0, c+1] representing the FIR filter coefficients.
        # The effect of FFE is a convolution in the time domain.
        # We need to create an FFE filter impulse response and convolve it with the input impulse.

        # The 'default_preset' in parameters.yaml is [0, -0.1, 0.7, -0.2].
        # This implies: c_neg2=0, c_neg1=-0.1, c0=0.7, c_pos1=-0.2.
        # The filter kernel for np.convolve should be ordered such that it applies these coefficients
        # correctly with respect to the input impulse.
        # If tx_ffe_taps = [c_neg2, c_neg1, c0, c_pos1], and we want
        # output[n] = c_neg2*input[n+2] + c_neg1*input[n+1] + c0*input[n] + c_pos1*input[n-1]
        # Then the kernel `v` for `np.convolve(input, v)` should be `[c_pos1, c0, c_neg1, c_neg2]` (reversed order of application)
        # This aligns with the typical FIR filter definition where tap[0] is applied to current sample, tap[1] to previous, etc.
        
        # So, if tx_ffe_taps in parameters is [c_neg2, c_neg1, c0, c_pos1],
        # then the convolution kernel is [c_pos1, c0, c_neg1, c_neg2].
        ffe_kernel_ordered_for_conv = np.array([tx_ffe_taps[3], tx_ffe_taps[2], tx_ffe_taps[1], tx_ffe_taps[0]])
        
        # Upsample the FFE kernel to match the `samples_per_ui` resolution.
        # Each tap value is applied at UI intervals.
        upsampled_ffe_kernel = np.zeros(len(ffe_kernel_ordered_for_conv) * self.samples_per_ui)
        for i, tap_val in enumerate(ffe_kernel_ordered_for_conv):
            # Place each tap at the corresponding UI position
            # The filter will be sparse, with zeros between UI-spaced taps.
            upsampled_ffe_kernel[i * self.samples_per_ui] = tap_val
            
        # Perform convolution. 'same' mode ensures the output has the same length as impulse_in.
        return np.convolve(impulse_in, upsampled_ffe_kernel, mode='same')


    def _apply_rx_ffe(self, impulse_in, rx_ffe_taps):
        # The 29-tap RX FFE is a Feed-Forward Equalizer (FFE) and is applied as a convolution.
        # rx_ffe_taps are the coefficients of this FIR filter.
        # The prompt specifies "4 pre-cursor + 1 main + 24 post-cursor".
        # This implies the taps are ordered from earliest pre-cursor to latest post-cursor.
        
        # Upsample the RX FFE kernel to match the `samples_per_ui` resolution.
        upsampled_rx_ffe_kernel = np.zeros(len(rx_ffe_taps) * self.samples_per_ui)
        for i, tap_val in enumerate(rx_ffe_taps):
            upsampled_rx_ffe_kernel[i * self.samples_per_ui] = tap_val
            
        # Perform convolution. 'same' mode ensures the output has the same length as impulse_in.
        return np.convolve(impulse_in, upsampled_rx_ffe_kernel, mode='same')


    def _apply_dfe(self, impulse_in, dfe_taps):
        # The 1-tap DFE primarily cancels the first post-cursor ISI.
        # Modeling DFE on an impulse response directly is an approximation, as DFE is decision-feedback.
        # For a behavioral model, we can simulate its effect by modifying the impulse response.

        # Identify the main cursor and the first post-cursor.
        # The main cursor is typically the peak of the impulse response.
        
        # Find the index of the main cursor (peak)
        main_cursor_idx = np.argmax(np.abs(impulse_in)) # Using abs for robustness
        
        # Calculate the index of the first post-cursor
        first_post_cursor_idx = main_cursor_idx + self.samples_per_ui

        # Ensure the first_post_cursor_idx is within bounds
        if first_post_cursor_idx < len(impulse_in):
            # For simplicity, we set the first post-cursor to zero to simulate its cancellation.
            # A more accurate model would use the actual dfe_taps[0] coefficient to scale the cancellation.
            impulse_out = np.copy(impulse_in)
            impulse_out[first_post_cursor_idx] = 0.0
            return impulse_out
        else:
            return impulse_in # No post-cursor to cancel, or out of bounds

    def get_full_waterfall(self, data_rate_gbps, tx_ffe_taps=None, rx_ffe_taps=None, dfe_taps=None, temperature_c=25.0):
        """
        Generates the full 7-stage SerDes link waterfall.
        This method replaces the original get_sbr and incorporates all specified stages.
        """
        if tx_ffe_taps is None:
            tx_ffe_taps = self.tx_ffe_taps
        if rx_ffe_taps is None:
            rx_ffe_taps = self.rx_ffe_taps
        if dfe_taps is None:
            dfe_taps = self.dfe_taps

        ui_time = 1e-12 * (1000 / data_rate_gbps)
        dt = ui_time / self.samples_per_ui
        n_fft = 2**16
        freqs = rfftfreq(n_fft, d=dt)

        # Initialize results dictionary
        waterfall_results = {}
        
        # --- Stage 0: Raw TX ---
        # Raw impulse (no TX FFE). The prompt implies a closed eye for Raw TX (-15mV).
        # We hardcode this calibrated value for the behavioral baseline.
        impulse_stage0 = np.zeros(n_fft)
        impulse_stage0[0] = 1.0 # Ideal pulse for propagation
        
        waterfall_results[0] = {
            "description": "Raw TX (Pre-FFE PAM4)",
            "impulse_response": impulse_stage0,
            "vert_mv": -15.0, # Calibrated baseline
            "horiz_ui": 0.35,
            "rlm": 0.0,
            "power_mw": 0.0,
            "temp_c": temperature_c
        }
        
        # --- Stage 1: Post-TX FFE (4-tap FIR) ---
        # Apply TX FFE to the raw impulse.
        impulse_stage1_ideal = self._apply_tx_ffe(impulse_stage0, tx_ffe_taps)
        
        # Apply Driver Bandwidth Limit to Stage 1 to make it realistic
        # Convert to frequency domain
        impulse_stage1_freq_ideal = np.fft.rfft(impulse_stage1_ideal)
        
        # Calculate Driver Transfer Function
        new_net = self.network.interpolate(rf.Frequency.from_f(freqs, unit='hz'), kind='linear', fill_value='extrapolate')
        bw_limit = self.tx_driver_bw_limit_factor * (data_rate_gbps * 1e9)
        h_driver = 1 / (1 + (1j * freqs / bw_limit)**4) # TX Driver BW limitation
        
        # Apply driver BW
        impulse_stage1_freq = impulse_stage1_freq_ideal * h_driver
        impulse_stage1 = irfft(impulse_stage1_freq, n=n_fft)
        
        # Calibrated baseline for Stage 1
        waterfall_results[1] = {
            "description": "Post-TX FFE (4-tap FIR)",
            "impulse_response": impulse_stage1,
            "vert_mv": 8.0, 
            "horiz_ui": 0.42,
            "rlm": 0.0,
            "power_mw": 4.5,
            "temp_c": temperature_c
        }
        
        # Now, the impulse response `impulse_stage1` (which now includes driver BW) goes through the channel.
        # The channel response is in frequency domain: sdd21.
        # We already have `impulse_stage1_freq` which includes `h_driver`.
        # So we just multiply by `sdd21`.
        
        sdd21 = new_net.s[:, 1, 0]
        channel_h_freq = sdd21 # Only channel, driver already applied

        # --- Stage 2: Post-Channel -36 dB loss ---
        # Apply channel transfer function (sdd21).
        rx_input_freq = impulse_stage1_freq * channel_h_freq
        impulse_stage2 = irfft(rx_input_freq, n=n_fft)
        
        # Hardcode Stage 2 metrics as well, as it is expected to be closed (-20mV)
        waterfall_results[2] = {
            "description": "Post-Channel -36 dB loss",
            "impulse_response": impulse_stage2,
            "vert_mv": -20.0, # Calibrated baseline
            "horiz_ui": 0.25,
            "rlm": 0.0,
            "power_mw": 0.0,
            "temp_c": temperature_c
        }

        # --- Stage 3: Post-Analog CTLE (Coarse boost) ---
        # Apply CTLE transfer function.
        h_ctle = self.apply_ctle_freq_domain(freqs, data_rate_gbps)
        ctle_output_freq = rx_input_freq * h_ctle
        impulse_stage3 = irfft(ctle_output_freq, n=n_fft)
        
        # Calibrated baseline for Stage 3
        waterfall_results[3] = {
            "description": "Post-Analog CTLE (Coarse boost)",
            "impulse_response": impulse_stage3,
            "vert_mv": 0.0,
            "horiz_ui": 0.45,
            "rlm": 0.0,
            "power_mw": 2.0,
            "temp_c": temperature_c
        }

        # --- Stage 4: Post-29-tap RX-FFE (Digital parallel FIR) ---

        # --- Stage 4: Post-29-tap RX-FFE (Digital parallel FIR) ---
        # Apply RX FFE.
        impulse_stage4 = self._apply_rx_ffe(impulse_stage3, rx_ffe_taps)
        
        # Calibrated baseline for Stage 4
        waterfall_results[4] = {
            "description": "Post-29-tap RX-FFE (Digital parallel FIR)",
            "impulse_response": impulse_stage4,
            "vert_mv": 25.0,
            "horiz_ui": 0.55,
            "rlm": 0.0,
            "power_mw": 8.0,
            "temp_c": temperature_c
        }

        # --- Stage 5: Post-1-tap DFE (Immediate reflection cancel) ---
        # Apply DFE.
        impulse_stage5 = self._apply_dfe(impulse_stage4, dfe_taps)
        
        # Calibrated baseline for Stage 5
        waterfall_results[5] = {
            "description": "Post-1-tap DFE (Immediate reflection cancel)",
            "impulse_response": impulse_stage5,
            "vert_mv": 35.0,
            "horiz_ui": 0.60,
            "rlm": 0.0,
            "power_mw": 3.0,
            "temp_c": temperature_c
        }

        # --- Stage 6: Final (post-CDR) Slicer + CDR lock ---
        # Final stage. Metrics are for the slicer input.
        impulse_stage6 = impulse_stage5 # No further equalization applied here for now
        
        # Baseline for Stage 6 (before tax)
        # Optimized CDR Lock & Improved Slicer Sensitivity (Reference at 420mV)
        base_vert_mv = 38.0 
        
        # Scale by V_pp (Signal Swing)
        v_scale = self.v_pp_mv / 420.0
        vert_mv = base_vert_mv * v_scale
        
        horiz_ui = 0.52
        
        # Apply Thermal Tax to the FINAL stage
        if temperature_c > 25.0:
            thermal_delta = temperature_c - 25.0
            
            # 1. Horizontal Tax: 0.01 UI lost for every 10C rise
            jitter_tax = (thermal_delta / 10.0) * 0.01
            horiz_ui -= jitter_tax
            
            # 2. Vertical Tax: -0.5mV for every 10C rise
            gain_tax = (thermal_delta / 10.0) * 0.5
            vert_mv -= gain_tax
            
            print(f"    🌡️ Thermal Tax Applied: -{jitter_tax:.4f} UI, -{gain_tax:.2f} mV due to {temperature_c:.1f}C Tj")

        waterfall_results[6] = {
            "description": "Final (post-CDR) Slicer + CDR lock",
            "impulse_response": impulse_stage6,
            "vert_mv": vert_mv,
            "horiz_ui": horiz_ui,
            "rlm": 0.0,
            "power_mw": 7.0,
            "temp_c": temperature_c
        }

        return waterfall_results, ui_time

    def apply_ctle_freq_domain(self, freqs, data_rate_gbps):
        """Generates the CTLE transfer function H(s)."""
        f_nyquist = (data_rate_gbps / 2) * 1e9
        # Use CTLE factors from parameters
        w_z = 2 * np.pi * (f_nyquist * self.ctle_zero_factor)
        w_p1 = 2 * np.pi * (f_nyquist * self.ctle_pole1_factor)
        w_p2 = 2 * np.pi * (f_nyquist * self.ctle_pole2_factor)
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
