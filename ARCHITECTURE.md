# SerDes Architect AI: Architectural Overview

This document provides a detailed overview of the behavioral architecture of the SerDes Architect AI tool. It describes the role of each Python module and the key behavioral models and algorithms implemented.

## 1. Core Modules

### 1.1 `src/physics.py`: Physical Layer Modeling

*   **Role:** Simulates the physical behavior of the SerDes link, including the channel, driver, and linear equalization stages.
*   **Key Models:**
    *   **Channel Model:** Parses S-parameter (.s4p) files, performs mixed-mode conversion to differential signals, and interpolates channel response.
    *   **TX Driver:** Models a 4th-order Butterworth filter to represent the transmitter's bandwidth limit.
    *   **CTLE (Continuous-Time Linear Equalizer):** Implements a 2-pole, 1-zero transfer function in the frequency domain to compensate for channel loss.
    *   **Reflection Tax:** Models the impact of impedance mismatches at the receiver, creating secondary pulses in the Single-Bit Response (SBR).
*   **Key Parameters (from `config/parameters.yaml`):**
    *   `general.samples_per_ui`
    *   `equalizer_parameters.tx_driver_bw_limit_factor`
    *   `equalizer_parameters.reflection_tax_delay_ui`
    *   `equalizer_parameters.ctle` (zero_factor, pole1_factor, pole2_factor)

### 1.2 `src/optimizer.py`: FFE Optimization

*   **Role:** Implements the Feed-Forward Equalizer (FFE) optimization to minimize Inter-Symbol Interference (ISI).
*   **Key Models:**
    *   **4-Tap Adaptive FIR Filter:** Models a 4-tap FFE (C-2, C-1, C0, C+1) as commonly used in PCIe 7.0.
    *   **Iterative Adaptation:** Uses a simplified gradient descent algorithm to find optimal tap weights, constrained by defined ranges and resolution.
*   **Key Parameters (from `config/parameters.yaml`):**
    *   `equalizer_parameters.ffe` (num_taps, tap_positions, coefficient_ranges, resolution_bits, default_preset)

### 1.3 `src/clocking.py`: Clocking & CDR Modeling

*   **Role:** Models the timing aspects of the SerDes, including clock path impairments and Clock and Data Recovery (CDR) behavior.
*   **Key Models:**
    *   **Clock Path Engine:** Calculates jitter tax due to PLL noise, path jitter, and deskew.
    *   **Behavioral CDR:** Simulates a digital CDR's physical pipeline (phase detector, circular buffer latency, phase interpolator).
    *   **Jitter Transfer Function:** Models how the CDR tracks out sinusoidal jitter based on its loop bandwidth.
    *   **Jitter-to-Voltage Noise Conversion:** Calculates the vertical margin loss caused by residual timing jitter.
*   **Key Parameters (from `config/parameters.yaml`):**
    *   `clock_path_parameters` (ps_per_mm, jitter_per_mm_fs, deskew_step_fs)
    *   `cdr` (standard_latency_cycles, pi_resolution, rj_floor_ui, dither_penalty_factor, ber_sigma, cdr_p_per_flop_mw, cdr_p_base_unroll_mw, cdr_baseline_latency_cycles)

### 1.4 `src/ppa.py`: Power, Performance, Area (PPA) Estimation

*   **Role:** Estimates the power, performance, and area costs of the SerDes architecture.
*   **Key Models:**
    *   **Component-Based Power Model:** Calculates power for DFE, AFE (CTLE, VGA, ADC), PLL, and CDR.
    *   **CDR Power Model:** A two-component model (`P_pipeline` and `P_parallel`) that accounts for the power/latency trade-off (unroll tax) in CDRs.
*   **Key Parameters (from `config/parameters.yaml`):**
    *   `equalizer_parameters` (dfe_tap_pwr_mw_factor, vga_power_mw_factor, adc_7bit_power_mw_factor, dfe_tap_area_um2)
    *   `equalizer_parameters.ctle.ctle_power_per_stage_mw_factor`
    *   `clocking_parameters.pll_base_power_mw_factor`
    *   `cdr` (cdr_p_per_flop_mw, cdr_p_base_unroll_mw, cdr_baseline_latency_cycles)

### 1.5 `src/tx.py`: Transmitter Power Modeling

*   **Role:** Models the power consumption of the transmitter's driver.
*   **Key Models:**
    *   **Impedance-Scaled Power:** Calculates Tx power based on main driver legs and a power-per-leg factor, scaled inversely with target impedance.
*   **Key Parameters (from `config/parameters.yaml`):**
    *   `equalizer_parameters.tx_driver_pwr_per_leg_mw_factor` (implicitly used by `ppa.py`)

### 1.6 `src/stats.py`: Monte Carlo & Yield Prediction

*   **Role:** Performs statistical yield analysis by simulating process variations to predict design robustness.
*   **Key Models:**
    *   **Behavioral Monte Carlo:** Runs multiple iterations, applying Gaussian variations to key architectural "knobs" (latency, DFE error, CDR bandwidth, ISI).
    *   **Behavioral Link Model:** Uses a simplified, configurable behavioral model to estimate margin for each Monte Carlo iteration.
*   **Key Parameters (from `config/parameters.yaml`):**
    *   `monte_carlo` (base_latency, base_bw, parameters.latency_sigma_ps, parameters.dfe_tap_err_sigma_mv, etc.)
    *   `behavioral_model` (ideal_v_opening, dfe_efficiency, cdr_tax_per_ps)

### 1.7 `src/visualizer.py`: Data Visualization

*   **Role:** Generates `matplotlib` plots for visualizing simulation results.
*   **Key Features:**
    *   **Multi-Stage Eye Diagrams:** A 4-panel dashboard showing signal recovery at different points in the link (Tx Output, Rx Input, Post-CTLE, Final Eye).
    *   **Contribution Waterfall Chart:** Visualizes margin loss breakdown.
    *   **Phase Error Histograms:** Illustrates CDR stability.

### 1.8 `src/serdes_app_main.py`: Orchestration & Reporting

*   **Role:** The main entry point of the tool. Orchestrates the different simulation modes, integrates all modules, and generates comprehensive reports.
*   **Key Features:**
    *   **Command-Line Interface:** Uses `argparse` to select analysis modes (`--baseline`, `--sweep`, `--monte-carlo`).
    *   **Waterfall PPA Table:** Presents stage-by-stage margin and power.
    *   **Detailed CDR Report:** Provides transparency into horizontal margin calculation.
    *   **Unified Margin Calculation:** Ensures consistency in margin reporting across different analysis modes.

## 2. Parameterization Strategy

The tool's behavioral models are highly parameterized. All key assumptions and constants are managed centrally in `config/parameters.yaml`, making the tool configurable and adaptable. Technology-specific parameters are in `config/tech_3nm.yaml`.

## 3. Design Assumptions & Heuristics

Throughout the behavioral models, various heuristics and simplifying assumptions have been made. These are detailed in the comments within the code and in `config/parameters.yaml`. These behavioral models are intended for architectural exploration and trade-off analysis, rather than transistor-level accuracy.

---
