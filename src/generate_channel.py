import numpy as np

def generate_true_s4p(filename, length_inches=5):
    freqs = np.linspace(0.1, 64, 500) 
    a1, a2 = 0.15 * length_inches, 0.04 * length_inches
    
    with open(filename, 'w') as f:
        f.write("# GHz S RI R 50\n")
        f.write(f"! True 4-Port Differential Channel: {length_inches} inches\n")
        for freq in freqs:
            # Transmission (S21/S43)
            loss_db = -(a1 * np.sqrt(freq) + a2 * freq)
            mag = 10**(loss_db / 20)
            phase = -2 * np.pi * freq * 0.160 * length_inches
            s_trans = f"{mag * np.cos(phase):.6f} {mag * np.sin(phase):.6f}"
            
            # Reflection (S11/S22/S33/S44) - small mismatch
            s_refl = "0.05 0.00"
            
            # Cross-talk/Isolation (S13/S14 etc) - assume high isolation for now
            s_iso = "0.00 0.00"
            
            # Row-by-row matrix (16 complex pairs)
            row1 = f"{s_refl} {s_iso} {s_trans} {s_iso}"
            row2 = f"{s_iso} {s_refl} {s_iso} {s_trans}"
            row3 = f"{s_trans} {s_iso} {s_refl} {s_iso}"
            row4 = f"{s_iso} {s_trans} {s_iso} {s_refl}"
            
            f.write(f"{freq:.4f} {row1} {row2} {row3} {row4}\n")

generate_true_s4p('data/channel_400g.s4p', length_inches=6)
