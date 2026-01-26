import os
import shutil
import glob

def reorganize():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dist_output = os.path.join(project_root, "dist_output")
    
    if not os.path.exists(dist_output):
        print(f"Error: {dist_output} does not exist.")
        return

    print(f"Reorganizing {dist_output}...")

    runtime_dir = os.path.join(dist_output, "runtime")
    packages_dir = os.path.join(dist_output, "packages")
    
    os.makedirs(runtime_dir, exist_ok=True)
    os.makedirs(packages_dir, exist_ok=True)

    # 1. Find Python environment
    # Check for extracted subdirectory first (e.g. python-3.9.13-embed-amd64)
    python_subdirs = glob.glob(os.path.join(dist_output, "python-*-embed-amd64"))
    
    python_src = None
    if python_subdirs:
        python_src = python_subdirs[0]
        print(f"Found Python environment in: {python_src}")
        
        # Move contents to runtime
        for item in os.listdir(python_src):
            s = os.path.join(python_src, item)
            d = os.path.join(runtime_dir, item)
            if os.path.exists(d):
                if os.path.isdir(d):
                    shutil.rmtree(d)
                else:
                    os.remove(d)
            shutil.move(s, d)
        
        # Remove empty dir
        os.rmdir(python_src)
    elif os.path.exists(os.path.join(dist_output, "python.exe")):
        print("Found Python environment in root of dist_output")
        # Move python related files
        for item in os.listdir(dist_output):
            if item in ["runtime", "packages", "app", "input", "temp", "databases", "dist_tools", "boot.py", "OCR_Server.bat", "main.py"]:
                continue
            
            s = os.path.join(dist_output, item)
            d = os.path.join(runtime_dir, item)
            
            # Move likely python files
            if item.startswith("python") or item.endswith(".dll") or item.endswith(".pyd") or item in ["Lib", "Scripts", "LICENSE.txt"]:
                 if os.path.exists(d):
                    if os.path.isdir(d):
                        shutil.rmtree(d)
                    else:
                        os.remove(d)
                 shutil.move(s, d)

    # 2. Setup _pth file to allow site-packages
    pth_files = glob.glob(os.path.join(runtime_dir, "*._pth"))
    if pth_files:
        pth_file = pth_files[0]
        print(f"Updating {pth_file}...")
        with open(pth_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        with open(pth_file, 'w', encoding='utf-8') as f:
            for line in lines:
                if line.strip().startswith("#import site"):
                    f.write("import site\n")
                else:
                    f.write(line)
            # Ensure packages dir is included if not standard
            # Actually, we want to point to ../packages
            # But 'import site' usually looks in standard locations.
            # Let's add explicit paths just in case
            f.write("..\n")
            f.write("..\packages\n")
            
    # 3. Create Launcher
    bat_path = os.path.join(dist_output, "OCR_Server.bat")
    with open(bat_path, "w", encoding="utf-8") as f:
        f.write('@echo off\n')
        f.write('cd /d "%~dp0"\n')
        f.write('set PYTHONPATH=%CD%\\packages;%CD%\n')
        f.write('start "" "runtime\\python.exe" boot.py\n')
    print(f"Created {bat_path}")
    
    # 4. Create separate packages folder if Lib/site-packages exists in runtime
    site_packages = os.path.join(runtime_dir, "Lib", "site-packages")
    if os.path.exists(site_packages):
        print("Moving existing site-packages to packages/...")
        # Move contents of site-packages to packages
        for item in os.listdir(site_packages):
            s = os.path.join(site_packages, item)
            d = os.path.join(packages_dir, item)
            if os.path.exists(d):
                continue # Skip existing
            shutil.move(s, d)
        
        # Clean up empty Lib/site-packages if desired, or keep it.
        # But 'import site' will look in Lib/site-packages. 
        # By setting PYTHONPATH=packages, we add it.
        pass

    print("Reorganization complete.")
    print("Structure:")
    print(f"  {dist_output}\\")
    print(f"    runtime\\   (Base Python Environment)")
    print(f"    packages\\  (Third-party Libraries)")
    print(f"    app\\       (Application Code)")
    print(f"    OCR_Server.bat (Launcher)")

if __name__ == "__main__":
    reorganize()
