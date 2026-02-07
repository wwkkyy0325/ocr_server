import os
import shutil
import sys

# Ensure we can import build_dist
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import build_dist

def clean_and_rebuild():
    dist_output = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dist_output"))
    
    base_env = os.path.join(dist_output, "base_env")
    site_packages = os.path.join(dist_output, "site_packages")
    
    print(f"Cleaning {base_env}...")
    if os.path.exists(base_env):
        try:
            shutil.rmtree(base_env)
        except Exception as e:
            print(f"Error removing base_env: {e}")

    print(f"Cleaning {site_packages}...")
    if os.path.exists(site_packages):
        try:
            shutil.rmtree(site_packages)
        except Exception as e:
            print(f"Error removing site_packages: {e}")
        
    os.makedirs(site_packages, exist_ok=True)
    
    print("Rebuilding base_env...")
    build_dist.prepare_base_env(dist_output)
    
    print("Done. Environment is reset to base only.")

if __name__ == "__main__":
    clean_and_rebuild()
