Product Specification: SerDes-Architect AI
1. Project Vision
SerDes-Architect AI is a "Shift-Left" micro-architecture exploration tool designed for high-speed interconnects (200Gbps PAM4 and 400Gbps/PCIe 7.0 PAM4/8). It bridges the gap between high-level architectural intent and physical silicon reality by providing real-time "Reasoning" on margin loss, power, and area (PPA).

2. Target Standards & Performance
Standard     Data Rate     Nyquist Freq     Targeted UI
PCIe 6.0     64 GT/s       16 GHz           15.6 ps (PAM4)
PCIe 7.0     128 GT/s      32 GHz           7.8 ps (PAM4)
OIF 112G     112 Gbps      28 GHz           8.9 ps (PAM4)
OIF 224G     224 Gbps      56 GHz           4.4 ps (PAM4)

3. Core Features & "Reasoning" Modules
A. Physics-Aware SBR Extraction (physics.py)
Feature: Converts Touchstone (.s4p) channel models into Time-Domain Single Bit Responses (SBR).
Requirement: Must support frequency-dependent insertion loss (Sdd21) and account for 3nm driver bandwidth limits.

B. Silicon Cost Engine (ppa.py)
Feature: Accelergy-style estimation of Area ($um^2$) and Power (mW).
Requirement: Scales based on the number of equalization "legs," clock distribution distance, and process node (3nm GAA).

C. Adaptive Leg Optimizer (optimizer.py)
Feature: Quantized LMS search for optimal FFE/DFE tap weights.
Requirement: Models hardware granularity (e.g., 64-leg driver strength) to calculate Quantization Tax on the vertical eye margin.

D. Path-Matching & Clocking (clocking.py)
Feature: Evaluates the physical H-tree clock distribution.
Requirement: Measures margin loss due to clock skew, path jitter, and deskew resolution.

E. Waterfall Margin Reasoner (reasoner.py)
Feature: A diagnostic "Waterfall" report that attributes margin loss.
Deliverable: Provides clear reasons for failure (e.g., "70% of margin lost to Jitter; suggest PLL upgrade").

4. User Configuration (YAML)
The tool is controlled via two primary configuration files:
tech_3nm.yaml: Contains process-specific constants (Jitter floor, LSB voltage, Gate area).
serdes_top.yaml: Defines the micro-architecture (Number of lanes, DFE tap count, Leg configuration).

5. Directory Structure
Plaintext
serdes_architect/
├── config/           # YAML Tech & Arch files
├── data/             # S-parameter (.s4p) files
├── src/              # Python Logic (Physics, PPA, Reasoner)
├── output/           # JSON Reports & Eye Diagrams
└── product.md        # This document

6. CLI
The tool is driven via a primary CLI script `serdes_app_main.py`.

7. Signal Integrity Targets ($85\ \Omega$ Differential)
To align with modern high-speed standards like PCIe 7.0, the system targets an 85-ohm differential impedance.

- **Channel Impedance ($Z_0$):** 85 $\Omega$
- **Receiver Termination ($Z_{RX}$):** 95 $\Omega$

This "High-Z" termination strategy, where the receiver impedance is intentionally set ~10-15% higher than the channel, is a common technique to compensate for the parasitic capacitance of the receiver's input pads, thus optimizing signal integrity for the overall link.
