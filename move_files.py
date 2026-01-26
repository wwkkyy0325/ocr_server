import shutil
import os

base_dir = os.path.dirname(os.path.abspath(__file__))
dist_output = os.path.join(base_dir, "dist_output")
source_dir = os.path.join(dist_output, "python-3.9.13-embed-amd64")

print(f"Base dir: {base_dir}")
print(f"Dist output: {dist_output}")
print(f"Source dir: {source_dir}")

if os.path.exists(dist_output):
    print(f"Contents of dist_output: {os.listdir(dist_output)}")
else:
    print("dist_output does not exist!")

if os.path.exists(source_dir):
    for filename in os.listdir(source_dir):
        source_file = os.path.join(source_dir, filename)
        target_file = os.path.join(dist_output, filename)
        
        # Skip if target file already exists (e.g. if we ran this partially)
        if os.path.exists(target_file):
            print(f"Skipping {filename}, already exists in target.")
            continue
            
        if os.path.isfile(source_file):
            shutil.move(source_file, target_file)
        elif os.path.isdir(source_file):
             if not os.path.exists(target_file):
                shutil.move(source_file, target_file)
    
    # Remove the empty directory
    try:
        os.rmdir(source_dir)
        print("Source directory removed.")
    except OSError as e:
        print(f"Could not remove source directory: {e}")
    print("Files moved successfully.")
else:
    print("Source directory not found.")
