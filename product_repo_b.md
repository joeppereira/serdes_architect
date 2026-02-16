# Product Specification: Physics Accelerated (Repo B)

This document defines the "Intellectual Property" of the AI repository (`physics_accelerated`). 
In the SerDes Architect system, **Repo A (`serdes_architect`) acts as the "Sensor"** (providing ground-truth physical simulation data), while **Repo B (`physics_accelerated`) acts as the "Brain"** (providing optimized strategies and fast surrogates).

## 1. Commercial Purpose
- **Role**: AI-Driven Optimization & Surrogate Modeling Engine.
- **Goal**: Decouple slow physics simulation from fast design space exploration.

## 2. Model Architecture
- **Type**: Mini-SAUFNO-JEPA (Self-Attention U-Net Fourier Neural Operator with Joint-Embedding Predictive Architecture).
- **Size**: ~0.6 Million Parameters (Lightweight).
- **Performance Target**: 100x faster inference speed compared to Repo A's physics engine (`physics.py`).

## 3. Input Interface (Shared Interface)
- **Format**: JSON / Parquet (via `simulation_result` directory).
- **Schema**: Matches Repo A's `simulation_result` output.
- **Key Parameters (10-Scalar Config)**:
  - FFE Taps (4 coefficients)
  - Channel Loss (dB @ Nyquist)
  - Temperature (Ambient/Junction)
  - Power constraints
  - Baud Rate / Sampling parameters

## 4. Output Contract
- **Response**: 15-Scalar Prediction Vector.
- **Content**:
  - **7-Stage Margins**: Vertical (mV) and Horizontal (UI) margins for all 7 tracking stages (Raw TX -> Final CDR).
  - **Junction Temperature (Tj)**: Predicted thermal impact.
- **Usage**: Used by Repo A to bypass full simulation during high-volume sweeps or initial optimization passes.

## 5. Logic Constraint
- **Mechanism**: Physics-Informed Loss (PIL).
- **Rule**: Enforces the **35mV DFE Tap-1 limit** mandated by the 3nm technology specification.
- **Behavior**: Penalizes optimized configurations that achieve margins by violating electrical constraints (e.g., driving DFE taps too hard).

## 6. Optimization Strategy
- **Algorithm**: GEPA (Generative Evolutionary PPA Architecture).
- **Method**: Evolutionary Reflection.
- **Objective**: Evolve Power, Performance, and Area (PPA) metrics to achieve an energy efficiency target of **$< 0.60 \text{ pJ/bit}$**.
