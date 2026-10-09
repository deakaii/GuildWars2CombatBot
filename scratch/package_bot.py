import os
import shutil
import zipfile

desktop = r"C:\Users\dakot\Desktop"
source_dir = r"C:\Users\dakot\Desktop\Antigrav\screen_monitor_bot"
target_dir = os.path.join(desktop, "GW2_Bot")
zip_path = os.path.join(desktop, "GW2_Bot_Transfer.zip")

print(f"Cleaning previous targets if exist...")
if os.path.exists(target_dir):
    shutil.rmtree(target_dir)
if os.path.exists(zip_path):
    os.remove(zip_path)

os.makedirs(target_dir, exist_ok=True)

print(f"Copying files from {source_dir} to {target_dir}...")
for item in os.listdir(source_dir):
    if item in ['.venv', '__pycache__', '.pytest_cache']:
        continue
    src_item = os.path.join(source_dir, item)
    dst_item = os.path.join(target_dir, item)
    if os.path.isdir(src_item):
        shutil.copytree(src_item, dst_item, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    else:
        shutil.copy2(src_item, dst_item)

# Also copy MIGRATION_GUIDE.md if exists
guide_src = r"C:\Users\dakot\Desktop\Antigrav\MIGRATION_GUIDE.md"
if os.path.exists(guide_src):
    shutil.copy2(guide_src, os.path.join(target_dir, "MIGRATION_GUIDE.md"))

print(f"Creating ZIP archive at {zip_path}...")
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(target_dir):
        # Skip pycache dirs
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, target_dir)
            zipf.write(file_path, arcname)

size_mb = os.path.getsize(zip_path) / (1024 * 1024)
print(f"SUCCESS! Package created successfully.")
print(f"Folder: {target_dir}")
print(f"ZIP: {zip_path} ({size_mb:.2f} MB)")
