#!/bin/bash

# Navigate to the project directory
cd /Users/rohananthony/Downloads/files_new || exit

# Add all changes
git add .

# Create a commit with the current timestamp
TIMESTAMP=$(date +"%Y-%m-%d %H:%M:%S")
git commit -m "Automated push: $TIMESTAMP"

# Push to the current branch
# Make sure your upstream branch is set (e.g. git push -u origin main) 
# and that you have authenticated with GitHub (SSH or cached HTTPS).
git push origin HEAD
