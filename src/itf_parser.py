import re
import numpy as np

class ITFParser:
    def __init__(self, itf_path):
        self.path = itf_path
        self.materials = {}
        self.layers = {}
        self._parse()

    def _parse(self):
        """
        Extracts DIELECTRIC and CONDUCTOR blocks from foundry ITF.
        """
        try:
            with open(self.path, 'r') as f:
                content = f.read()

            # Regex to find Dielectric properties: ER (Permittivity) and LOSS_TANGENT/D
            dielectric_matches = re.finditer(r'DIELECTRIC\s+(\w+)\s*\{([^}]+)\}', content)
            for match in dielectric_matches:
                name = match.group(1)
                params = match.group(2)
                
                # Extract ER
                er_match = re.search(r'ER\s*=\s*([\d.]+)', params)
                er = float(er_match.group(1)) if er_match else 1.0
                
                # Extract Loss Tangent (D or LOSS_TANGENT)
                df_match = re.search(r'(?:LOSS_TANGENT|D)\s*=\s*([\d.]+)', params)
                df = float(df_match.group(1)) if df_match else 0.001
                
                self.materials[name] = {"er": er, "df": df}

            # Regex to find Conductor properties: RESISTIVITY
            conductor_matches = re.finditer(r'CONDUCTOR\s+(\w+)\s*\{([^}]+)\}', content)
            for match in conductor_matches:
                name = match.group(1)
                params = match.group(2)
                
                res_match = re.search(r'RESISTIVITY\s*=\s*([\d.]+)', params)
                res = float(res_match.group(1)) if res_match else 0.0
                
                self.layers[name] = {"resistivity": res}
                
        except FileNotFoundError:
            print(f"Warning: ITF file not found at {self.path}. Using defaults.")

    def get_layer_loss_params(self, layer_name, dielectric_name):
        """Returns the specific physics constants needed for the 128G link simulation."""
        layer_res = self.layers.get(layer_name, {"resistivity": 0.0})["resistivity"]
        mat_props = self.materials.get(dielectric_name, {"er": 1.0, "df": 0.0})
        
        return {
            "rho": layer_res,
            "er": mat_props["er"],
            "df": mat_props["df"]
        }
