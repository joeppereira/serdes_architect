import matplotlib.pyplot as plt
import numpy as np

class SerDesVisualizer:
    def __init__(self, ui_ps=7.8125, samples_per_ui=64):
        self.ui = ui_ps
        self.spu = samples_per_ui

    def plot_multistage_analysis(self, stages_data):
        fig, axs = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle("SerDes Signal Integrity Virtual Oscilloscope", fontsize=16)
        
        titles = ["1. Tx Output (Post-FFE)", "2. Rx Input (Post-Channel)", 
                  "3. Post-CTLE (Linear EQ)", "4. Final Eye (Post-DFE & CDR)"]
        
        for i, data in enumerate(stages_data):
            ax = axs[i//2, i%2]
            self._render_eye_on_axis(ax, data, titles[i])
            
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.show(block=False)

    def _render_eye_on_axis(self, ax, waveform, title):
        # Standard 2-UI folding logic for PAM4
        segment_len = self.spu * 2
        num_segments = len(waveform) // segment_len
        if num_segments == 0:
            ax.text(0.5, 0.5, "Not enough data for eye diagram", ha='center', va='center')
            return
            
        segments = waveform[:num_segments * segment_len].reshape(-1, segment_len)
        
        time_axis = np.linspace(0, 2, segment_len)
        # Plot a subset of segments for performance
        for seg in segments[:min(500, num_segments)]:
            ax.plot(time_axis, seg, color='darkblue', alpha=0.05, linewidth=0.5)
        
        ax.set_title(title)
        ax.set_ylim(-1.5, 1.5)
        ax.set_xlabel("Time (UI)")
        ax.set_ylabel("Amplitude (V)")
        ax.grid(True, which='both', linestyle=':', alpha=0.3)

    def plot_contribution_waterfall(self, diag_results):
        """
        Creates the 'Margin Thieves' chart based on the diagnostic results.
        """
        categories = ['ISI Error', 'Jitter Tax', 'Crosstalk/Noise']
        values = [
            diag_results.get('ISI_Contribution_mV', 0),
            diag_results.get('Jitter_Tax_mV', 0),
            diag_results.get('Crosstalk_Noise_mV', 0)
        ]
        
        plt.figure(figsize=(9, 5))
        bars = plt.bar(categories, values, color=['#e63946', '#f1faee', '#a8dadc'], edgecolor='black')
        
        plt.title("Margin Thieves: Contribution to Eye Closure")
        plt.ylabel("Voltage Loss (mV)")
        
        # Add labels on top of bars
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1, f"{yval:.2f}mV", ha='center', va='bottom', weight='bold')
            
        plt.tight_layout()
        plt.show(block=False)

    def plot_phase_error_histogram(self, phase_history, title="CDR Phase Error Distribution"):
        """
        Plots a histogram of the CDR's phase error over time.
        A "skinny" histogram indicates a tight lock.
        """
        plt.figure(figsize=(10, 6))
        
        # Convert phase history from UI to pico-seconds for readability
        phase_history_ps = np.array(phase_history) * self.ui
        
        plt.hist(phase_history_ps, bins=50, density=True, alpha=0.8, color='purple', label='Phase Error')
        
        mean_error = np.mean(phase_history_ps)
        std_dev = np.std(phase_history_ps)
        
        plt.axvline(mean_error, color='red', linestyle='--', label=f'Mean: {mean_error:.2f} ps')
        plt.title(title)
        plt.xlabel("Phase Error (ps)")
        plt.ylabel("Probability Density")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.show(block=False)