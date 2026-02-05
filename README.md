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

### 3. Statistical Monte Carlo & Yield Predictor
The suite includes a 500-iteration Monte Carlo engine that varies 3nm process parameters:
*   **Logic Speed:** Jitter in the CDR latency.
*   **Voltage Offsets:** Summer errors in the DFE taps.
*   **Package Discontinuities:** Variations in the measured 56mV ISI.

## 📊 The "Real Measure" Waterfall
The tool calculates the vertical and horizontal margin through a cumulative recovery process:

| Architectural Stage | Vertical Margin (mV) | Horizontal Margin (UI) | Power (mW) |
| :------------------ | :------------------- | :--------------------- | :--------- |
| Raw Link            | -15.99               | 0.350                  | 59.60      |
| + FFE (Tx)          | 7.99                 | 0.420                  | 4.52       |
| + CTLE (Rx)         | 12.50                | 0.580                  | 2.10       |
| + DFE (Rx)          | 36.31                | 0.610                  | 6.00       |
| + CDR (Final)       | 36.31                | 0.485                  | 7.20       |

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
