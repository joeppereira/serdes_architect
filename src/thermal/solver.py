import numpy as np
from scipy.sparse import lil_matrix, linalg

class SpatialThermalSolver:
    def __init__(self, size=16, pitch_um=50):
        self.N = size
        self.dx = pitch_um
        
    def solve(self, power_grid, k_sub=150.0, k_pkg=5.0):
        N = self.N
        k_conv = 1e-3
        g_lat = (k_sub * k_conv) * (self.dx * 100.0) / self.dx 
        g_vert = (k_pkg * k_conv) * (self.dx * self.dx) / 10.0
        
        # Build Sparse Matrix directly for accuracy
        size = N * N
        G = lil_matrix((size, size))
        
        for r in range(N):
            for c in range(N):
                idx = r * N + c
                
                # Count neighbors
                neighbors = []
                if r > 0: neighbors.append((r-1) * N + c)
                if r < N-1: neighbors.append((r+1) * N + c)
                if c > 0: neighbors.append(r * N + (c-1))
                if c < N-1: neighbors.append(r * N + (c+1))
                
                # Diagonal: Sum of lateral conductances + vertical
                G[idx, idx] = (len(neighbors) * g_lat) + g_vert
                
                # Off-diagonal: Lateral coupling
                for neigh_idx in neighbors:
                    G[idx, neigh_idx] = -g_lat
                    
        P = power_grid.flatten() + (g_vert * 25.0)
        
        try:
            T_flat = linalg.spsolve(G.tocsr(), P)
            return T_flat.reshape((N, N))
        except:
            return np.full((N, N), 25.0)
