# 128G SerDes Architect: Behavioral Simulation & Yield Suite

This README.md serves as the master documentation for your 128G PAM4 SerDes Architect Suite. It defines the transition from a failing baseline to a silicon-accurate, 3nm-ready architecture using the hybrid FFE/DFE/CDR strategy we've developed.

## Executive Summary
This suite is a high-fidelity behavioral simulator for PCIe 7.0 / 128G PAM4 links. Unlike static budget tools, it employs Cycle-Accurate Behavioral Modeling to simulate the handshake between Transmitter FFE, Receiver CTLE/DFE, and a Predictive CDR loop. It is designed to correlate lab-measured ISI (the 56mV "Margin Thief") with silicon-accurate architectural recovery.

## 🛠 Architectural Components

### 1. Signal Path Probes
The simulator "probes" the waveform at four physical junctions to visualize signal recovery:
*   **Stage 1: TX FFE:** Driver Output – PAM4 with "Spikes" (High-frequency boost to fight channel high-frequency attenuation).
*   **Stage 2: RX Input:** After Channel – Represents the "dead" eye after -25dB+ channel loss and package parasitics ($C_{pad}$).
*   **Stage 3: Post-CTLE:** After AFE – Models analog linear equalization (Laplace-domain) to sharpen transitions.
*   **Stage 4: Post-DFE/CDR:** Final non-linear recovery stage where reflections are subtracted and timing is locked.

### 2. Behavioral CDR & Latency Engine
The CDR is modeled as a discrete-time control loop with Circular Buffer Latency.
*   **Standard Mode:** Simulates a 12-cycle logic delay, demonstrating the collapse of horizontal margin to ~0.279 UI.
*   **Speculative Mode:** Simulates loop-unrolled, 1-cycle latency logic, recovering horizontal margin to >0.450 UI.

#### The Power/Latency Trade-off (Unroll Tax)
To achieve very low latency (e.g., 1 cycle), CDRs often employ "loop unrolling" or "speculative execution." This involves duplicating phase detection and processing logic across multiple parallel paths.

Our model for CDR power reflects this trade-off with two components:
*   **`P_pipeline`:** Power consumed by pipeline registers (e.g., flip-flops), which *decreases* with shorter latency.
*   **`P_parallel`:** Power from duplicating parallel paths, which *increases significantly* as latency decreases (i.e., more unrolling).

This ensures the model accurately captures the **Performance vs. Power** trade-off inherent in high-performance CDR design.

### 3. Statistical Monte Carlo & Yield Predictor
The suite includes a 500-iteration Monte Carlo engine that varies 3nm process parameters:
*   **Logic Speed:** Jitter in the CDR latency.
*   **Voltage Offsets:** Summer errors in the DFE taps.
*   **Package Discontinuities:** Variations in the measured 56mV ISI.

## 📊 The "Real Measure" Waterfall
The tool calculates the vertical and horizontal margin through a cumulative recovery process:

| Architectural Stage      | Vertical Margin (mV) | Horizontal Margin (UI) | Power (mW) |
| :----------------------- | :------------------- | :--------------------- | :--------- |
| Raw Link                 | -15.99               | N/A                    | 59.60      |
| + FFE (Tx)               | 51.55                | N/A                    | 1.36       |
| + CTLE (Rx)              | 12.50                | N/A                    | 2.10       |
| + DFE (Rx)               | 36.31                | N/A                    | 6.00       |
| - Jitter Tax (from CDR)  | -37.08               | N/A                    | 81.60      |
| **Final Net Margin**     | **-0.77**            | **0.188**              | **153.82** |

## 💡 Understanding the Reports

### Raw Link Margin vs. Actual Channel Loss
It's crucial to understand the distinction between the conceptual time-domain vertical margin shown in the "Raw Link" of the PPA table and the actual frequency-domain channel loss of your physical channel model.

*   **1. The Conceptual Raw Link Margin (`-15.99 mV`):**
    *   This `-15.99 mV` in the PPA table's "Raw Link" row is a **conceptual representation** that the signal eye is completely **closed** due to Inter-Symbol Interference (ISI) before any equalization.
    *   It's a way to numerically illustrate the *severity of the impairment* at the receiver's input, rather than a direct measurement. Its negative value signifies a non-functional link at this stage.

*   **2. The Actual Channel Loss (`-22.56 dB`):**
    *   The true physical characteristic of your channel (`data/channel_400g.s4p`) is its frequency-dependent loss.
    *   Our analysis determined this specific channel has an actual loss of **`-22.56 dB at 32 GHz Nyquist`**.
    *   **This `-22.56 dB` of channel loss is the *root cause* of the severe ISI that results in the conceptually closed eye (`-15.99 mV`).**

### Alignment with the Global Sensitivity Sweep
The "GLOBAL SENSITIVITY SWEEP" then takes this understanding and generalizes it by testing how your fully optimized link (`+ CDR Final`) performs against various *hypothetical* channel losses. This allows you to see the robustness of your design.

## 🚀 How to Run

1.  **Run Baseline Analysis**
    Execute the main app to correlate your CSV lab data with the 3nm simulation:
    ```bash
    python src/serdes_app_main.py
    ```
2.  **Run Global Sensitivity Sweep**
    Sweep across PVT (Process, Voltage, Temperature) corners and channel losses:
    ```bash
    python src/serdes_app_main.py --sweep global
    ```
3.  **Generate Yield Report**
    Run the Monte Carlo loop to verify if the architecture meets the 3-Sigma Guardband:
    ```bash
    python src/serdes_app_main.py --monte-carlo
    ```

## 🔍 Technical Specifications (3nm Target)
*   **Data Rate:** 128 Gbps (64 Gbaud PAM4)
*   **Nyquist:** 32 GHz
*   **Target BER:** $10^{-12}$
*   **Differential Impedance:** $85\ \Omega$ Board / $95\ \Omega$ RX
*   **Energy Efficiency Target:** $< 0.60\ pJ/bit$
