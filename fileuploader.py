import os
import subprocess

# ===== CONFIG =====
REPO_URL = "https://github.com/Smaron47/SwiftTask.git"
BRANCH = "main"
COMMIT_MSG = "🚀 Auto upload from Python scripts"

# ===== RUN COMMAND FUNCTION =====
def run(cmd):
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"❌ Error running: {cmd}")
        exit()

# ===== CHECK GIT INSTALLED =====
print("🔍 Checking Git...")
run("git --version")

# ===== INIT REPO IF NOT EXISTS =====
if not os.path.exists(".git"):
    print("📁 Initializing Git repo...")
    run("git init")

# ===== ADD REMOTE IF NOT EXISTS =====
remotes = subprocess.getoutput("git remote")
if "origin" not in remotes:
    print("🔗 Adding remote...")
    run(f"git remote add origin {REPO_URL}")

# ===== ADD ALL FILES =====
print("📦 Adding files...")
run("git add .")

# ===== COMMIT =====
print("📝 Committing...")
run(f'git commit -m "{COMMIT_MSG}"')

# ===== RENAME BRANCH TO MAIN =====
print("🔄 Renaming branch to main...")
run(f"git branch -M {BRANCH}")

# PUSH এর আগে এইটা থাকবে
print("🔄 Pulling latest changes...")
run(f"git pull origin {BRANCH} --rebase")

print("🚀 Pushing to GitHub...")
run(f"git push -u origin {BRANCH}")
# # ===== PUSH =====
# print("🚀 Pushing to GitHub...")
# run(f"git branch -M {BRANCH}")
# run(f"git push -u origin {BRANCH}")

print("✅ Upload Complete!")