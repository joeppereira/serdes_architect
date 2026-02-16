import pytest
import numpy as np
import os
import sys

# Add the project root to sys.path to allow imports from src
current_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
sys.path.insert(0, project_root)

from src.physics import SerdesPhysicsEngine

# Define a fixture for the physics engine to avoid re-instantiation
@pytest.fixture(scope="module")
def serdes_engine():
    # Assuming 'data/channel_400g.s4p' exists in the project root
    current_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(current_dir, os.pardir))
    
    channel_path = os.path.join(project_root, 'data', 'channel_400g.s4p')
    tech_file = os.path.join(project_root, 'config', 'tech_3nm.yaml')
    params_file = os.path.join(project_root, 'config', 'parameters.yaml')
    
    return SerdesPhysicsEngine(channel_path, tech_file=tech_file, params_file=params_file)

def test_waterfall_matches_readme(serdes_engine):
        # This test aims to reproduce the waterfall results described in the prompt/documentation.
        # The target values are from the "Trackable Channel Stages" table in the prompt.
    
        # Data rate for the PCIe 7.0 (128 GT/s)
        data_rate_gbps = 128
    
        waterfall_results, ui_time = serdes_engine.get_full_waterfall(data_rate_gbps)
    
        # Define expected ranges for each metric for each stage
        # Values are (nominal_value, relative_tolerance_percent, absolute_tolerance_for_zero_nominal)
        expected_results = {
            0: {"description": "Raw TX", "vert_mv": (-15.0, 50.0, 1.0), "horiz_ui": (0.35, 50.0, 0.01)},
            1: {"description": "Post-TX FFE", "vert_mv": (8.0, 50.0, 1.0), "horiz_ui": (0.42, 50.0, 0.01)},
            2: {"description": "Post-Channel", "vert_mv": (-20.0, 50.0, 1.0), "horiz_ui": (0.25, 50.0, 0.01)},
            3: {"description": "Post-Analog CTLE", "vert_mv": (0.0, 50.0, 1.0), "horiz_ui": (0.45, 50.0, 0.01)},
            4: {"description": "Post-29-tap RX-FFE", "vert_mv": (25.0, 50.0, 1.0), "horiz_ui": (0.55, 50.0, 0.01)},
            5: {"description": "Post-1-tap DFE", "vert_mv": (35.0, 50.0, 1.0), "horiz_ui": (0.60, 50.0, 0.01)},
            6: {"description": "Final (post-CDR)", "vert_mv": (36.0, 50.0, 1.0), "horiz_ui": (0.48, 50.0, 0.01)},
        }
    
        # Helper function for asserting values within a range
        def assert_within_range(actual, nominal, rel_tol_percent, abs_tol_for_zero_nominal, metric_name, stage_idx, unit):
            if nominal == 0.0:
                # For zero nominal, use absolute tolerance
                assert np.isclose(actual, nominal, atol=abs_tol_for_zero_nominal), \
                    f"Stage {stage_idx} {metric_name} mismatch: Expected {nominal:.2f}{unit} (abs_tol: {abs_tol_for_zero_nominal:.2f}{unit}), Got {actual:.2f}{unit}"
            else:
                # For non-zero nominal, use relative tolerance
                rel_diff_percent = abs((actual - nominal) / nominal) * 100
                assert rel_diff_percent <= rel_tol_percent, \
                    f"Stage {stage_idx} {metric_name} mismatch: Expected {nominal:.2f}{unit}, Got {actual:.2f}{unit} (Diff: {rel_diff_percent:.2f}%)"
    
    
        for stage_idx, expected in expected_results.items():
            actual = waterfall_results[stage_idx]
            
            # Check vertical margin
            nominal_vert_mv, rel_tol_vert, abs_tol_vert = expected["vert_mv"]
            actual_vert_mv = actual["vert_mv"]
            assert_within_range(actual_vert_mv, nominal_vert_mv, rel_tol_vert, abs_tol_vert, "Vertical Margin", stage_idx, "mV")
    
            # Check horizontal margin
            nominal_horiz_ui, rel_tol_horiz, abs_tol_horiz = expected["horiz_ui"]
            actual_horiz_ui = actual["horiz_ui"]
            assert_within_range(actual_horiz_ui, nominal_horiz_ui, rel_tol_horiz, abs_tol_horiz, "Horizontal Margin", stage_idx, "UI")
