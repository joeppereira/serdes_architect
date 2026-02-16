import math

class TimingAuditor:
    def __init__(self, config):
        """
        Analyzes timing closure for the SerDes Analog Front End (AFE) and Digital Logic.
        """
        self.config = config
        self.tech_node = config.get('technology', {}).get('node', '3nm_FinFET')
        self.threshold = config.get('technology', {}).get('device_threshold', 'SVT')
        self.v_pp = config.get('equalizer_parameters', {}).get('v_pp_mv', 420.0)
        
    def check_timing(self, data_rate_gbps=128):
        """
        Checks if the design can close timing at the target data rate
        given the technology selection (HVT/SVT) and voltage swing.
        """
        ui_ps = 1000.0 / data_rate_gbps
        
        # --- 1. Slicer Latch Constant (Intrinsic Speed) ---
        # 3nm FinFET SVT Setup+Hold time approximation for high-speed CML latch
        # Baseline: 2.5 ps at nominal conditions
        t_setup_hold_base = 2.5
        
        # --- 2. Threshold Voltage Penalty (HVT vs SVT) ---
        # HVT devices have higher Vt, reducing drive current (Ids).
        # Delay is roughly proportional to C * Vdd / Ids.
        # HVT penalty is typically 30-40% delay increase.
        if self.threshold == 'HVT':
            k_vt = 1.35 # 35% slower
            print(f"    ⚠️  HVT Penalty: Slicer is {k_vt}x slower")
        else:
            k_vt = 1.0
            
        # --- 3. Voltage Swing / Slew Rate Penalty ---
        # Lower Vpp means lower signal slope (dV/dt).
        # Slower transition = Uncertainty in sampling point (AM-to-PM conversion).
        # We model this as an effective increase in required setup time (jitter).
        # Reference Vpp = 420 mV.
        ref_vpp = 420.0
        # If Vpp drops, delay increases linearly-ish with the ratio (inverse slew)
        k_slew = max(1.0, ref_vpp / self.v_pp)
        if k_slew > 1.0:
            print(f"    ⚠️  Low Vpp Penalty: Slew rate degraded by {k_slew:.2f}x")
            
        # --- 4. Total Critical Path Consumption ---
        # The time "lost" to the latch physics and signal integrity
        # This is the "Dead Zone" in the eye where we cannot sample.
        t_dead_zone = t_setup_hold_base * k_vt * k_slew
        
        # --- 5. Jitter Budget (Random + Deterministic) ---
        # We assume a fixed Jitter floor from the PLL/Clock (e.g., 0.15 UI)
        # This is independent of the Slicer speed, but subtracts from the timing margin.
        jitter_ui = 0.15
        t_jitter = jitter_ui * ui_ps
        
        # --- 6. Final Timing Margin ---
        total_time_consumed = t_dead_zone + t_jitter
        timing_margin_ps = ui_ps - total_time_consumed
        
        is_passing = timing_margin_ps > 0
        
        return {
            "verdict": "PASS" if is_passing else "FAIL",
            "ui_ps": round(ui_ps, 2),
            "t_dead_zone_ps": round(t_dead_zone, 2),
            "t_jitter_ps": round(t_jitter, 2),
            "margin_ps": round(timing_margin_ps, 2),
            "max_freq_ghz": round(1000.0 / total_time_consumed, 2)
        }
