import torch
import numpy as np
import os
from src.thermal.solver import SpatialThermalSolver

def generate_nemo_dataset(samples=5000):
    print(f"🏭 Physics Factory: Generating {samples} spatial samples (Normalized)...")
    solver = SpatialThermalSolver()
    
    x_data = [] 
    y_data = [] 
    
    for i in range(samples):
        p_grid = np.zeros((16, 16))
        
        # DSP (Top) - Lower density but large area
        p_dsp = np.random.uniform(50, 200)
        p_grid[0:4, :] = p_dsp / (4*16)
        
        # TX (Bottom Left) - High density hotspot
        tx_row, tx_col = np.random.randint(10, 14), np.random.randint(1, 6)
        p_tx = np.random.uniform(100, 200) # Increased to ensure it is the peak
        p_grid[tx_row:tx_row+2, tx_col:tx_col+2] = p_tx / 4.0
        
        # RX (Bottom Right)
        rx_row, rx_col = np.random.randint(10, 14), np.random.randint(9, 14)
        p_rx = np.random.uniform(20, 50)
        p_grid[rx_row:rx_row+2, rx_col:rx_col+2] = p_rx / 4.0
        
        # Solve
        k_pkg = np.random.uniform(2.0, 8.0) 
        t_grid = solver.solve(p_grid, k_pkg=k_pkg)
        
        # NORMALIZE AT THE SOURCE
        # X: Divide by peak possible power density (~50 mW/pixel)
        # Y: Divide by 125.0 (Max Temp)
        x_data.append(p_grid / 50.0) 
        y_data.append(t_grid / 125.0)
        
        if (i+1) % 1000 == 0:
            # Quick check on the last sample
            max_p = np.unravel_index(np.argmax(p_grid), (16, 16))
            max_t = np.unravel_index(np.argmax(t_grid), (16, 16))
            print(f"   ... {i+1} samples. Peak P: {max_p}, Peak T: {max_t}")

    os.makedirs("data", exist_ok=True)
    torch.save(torch.tensor(np.array(x_data)).float().unsqueeze(-1), "data/x_spatial.pt")
    torch.save(torch.tensor(np.array(y_data)).float().unsqueeze(-1), "data/y_spatial.pt")
    print("✅ Normalized data ready in ../serdes_architect/data/")

if __name__ == "__main__":
    generate_nemo_dataset()
