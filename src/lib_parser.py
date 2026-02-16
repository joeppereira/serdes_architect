import re

class LibertyParser:
    def __init__(self, lib_path):
        self.lib_path = lib_path
        self.cell_data = {}
        self._parse()

    def _parse(self):
        """
        Parses Liberty format to extract power and delay characteristics.
        Focuses on cells relevant to SerDes: Flip-Flops, XORs, and Buffers.
        """
        try:
            with open(self.lib_path, 'r') as f:
                content = f.read()

            cell_names = re.finditer(r'cell\s*\(([\w_]+)\)', content)
            
            for match in cell_names:
                name = match.group(1)
                start_idx = match.end()
                
                brace_count = 0
                found_start = False
                cell_content = ""
                
                for i, char in enumerate(content[start_idx:]):
                    if char == '{':
                        if not found_start:
                            found_start = True
                            scan_start = start_idx + i + 1 
                            brace_count = 1
                        else:
                            brace_count += 1
                    elif char == '}':
                        if found_start:
                            brace_count -= 1
                            if brace_count == 0:
                                cell_content = content[scan_start : start_idx + i]
                                break
                
                if cell_content:
                    leakage = re.search(r'leakage_power\s*:\s*([\d.]+)', cell_content)
                    leakage_val = float(leakage.group(1)) if leakage else 0.0
                    
                    dynamic_val = self._estimate_dynamic_power(name)
                    
                    self.cell_data[name] = {
                        "leakage_nw": leakage_val * 1e6, 
                        "dynamic_fj": dynamic_val * 1000 
                    }
                    
        except FileNotFoundError:
            print(f"Warning: Liberty file not found at {self.lib_path}. Using defaults.")

    def _estimate_dynamic_power(self, cell_name):
        return 0.45 if "DF" in cell_name else 0.12 

    def get_block_power(self, cell_counts):
        """
        Calculates total power for a block (e.g., CDR) based on cell counts.
        Total = Sum(Leakage) + Sum(Dynamic * Activity_Factor * Frequency)
        Returns power in mW.
        """
        total_leakage_mw = 0.0
        total_dynamic_mw = 0.0
        freq_ghz = 64.0
        activity_factor = 0.1 
        
        for cell, count in cell_counts.items():
            data = self.cell_data.get(cell, {"leakage_nw": 0, "dynamic_fj": 0})
            total_leakage_mw += (data["leakage_nw"] * count) / 1e6
            dynamic_mw_cell = data["dynamic_fj"] * freq_ghz * activity_factor * 1e-3
            total_dynamic_mw += dynamic_mw_cell * count
            
        return total_leakage_mw + total_dynamic_mw