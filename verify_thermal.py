import sys
import os
sys.path.insert(0, os.getcwd())

from src.itf_parser import ITFParser
from src.lib_parser import LibertyParser
from src.thermal import ThermalAuditor

def verify_thermal():
    print("=================================================================")
    print("VERIFICATION: THERMAL AUDITOR")
    print("=================================================================\n")
    
    # 1. Load Parsers
    print("[1] Loading Technology Files...")
    itf_parser = ITFParser('data/technology/process_3nm.itf')
    lib_parser = LibertyParser('data/technology/liberty_3nm.lib')
    
    # 2. Run Auditor
    print("[2] Running Thermal Auditor (Typical Case @ 25C)...")
    auditor = ThermalAuditor(itf_parser, lib_parser)
    report = auditor.generate_distribution_report(temp_c=25)
    
    print("\n--- Power Distribution Report (Typical) ---")
    print(report)
    
    # Verify values against the prompt's table
    # Table: Total ~50.8, Metal ~14.2
    total = report['summary']['total_power_mw']
    metal = report['breakdown_mw']['metal_interconnect']
    
    print(f"\n    Total Power: {total:.2f} mW (Target ~50.8)")
    print(f"    Metal Power: {metal:.2f} mW (Target ~14.2)")
    
    if 45 < total < 55 and 10 < metal < 18:
        print("    -> VERDICT: PASS. Values align with Sign-off View.")
    else:
        print("    -> VERDICT: FAIL. Values diverge from expectations.")

    # 3. Run Worst Case
    print("\n[3] Running Thermal Auditor (Worst Case @ 125C)...")
    report_wc = auditor.generate_distribution_report(temp_c=125)
    print(f"    Total Power: {report_wc['summary']['total_power_mw']:.2f} mW (Target ~66.5)")
    
    if report_wc['summary']['total_power_mw'] > total:
         print("    -> VERDICT: PASS. Power increases with temperature.")
    else:
         print("    -> VERDICT: FAIL. Power did not increase.")

if __name__ == "__main__":
    verify_thermal()
