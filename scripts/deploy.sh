#!/usr/bin/env bash

# Deploys optimized copy of current repo to remote server
set -euo pipefail

# Load deployment config
SCRIPT_DIR="$(dirname "$0")"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"

if [ -f "$SCRIPT_DIR/.env" ]; then
    source "$SCRIPT_DIR/.env"
else
    echo "❌ .env file not found. Please create it with SERVER_USER, SERVER_HOST, and DEPLOY_PATH"
    exit 1
fi

echo "🚀 Deploying homelab to ${SERVER_USER}@${SERVER_HOST}:${DEPLOY_PATH}"

# Create deployment archive using .gitignore patterns
echo "📦 Creating deployment archive..."
cd "$REPO_ROOT"

# Ensure blog is generated
echo "Generating blog HTML..."
pushd blog > /dev/null
../venv/bin/python3 ./generate_blog.py
popd > /dev/null

# Convert .gitignore to tar exclude format and add extra deployment exclusions
EXCLUDE_FILE=$(mktemp)
trap "rm -f $EXCLUDE_FILE" EXIT

# Process .gitignore patterns
grep -v '^#' .gitignore | grep -v '^$' > "$EXCLUDE_FILE" || true

# Add deployment-specific exclusions
cat >> "$EXCLUDE_FILE" << 'EOF'
.git/
*.tar.gz
EOF

# Make a tarball of the repo, excluding certain files but including needed deployment files
# First create uncompressed archive excluding everything in .gitignore
tar --exclude-from="$EXCLUDE_FILE" -cf homelab-deploy.tar .
rm -f $EXCLUDE_FILE
trap "rm -f homelab-deploy.tar" EXIT

# Then add back the specific files needed for deployment (if they exist)
if [ -f "networking/.env" ]; then
    tar --append -f homelab-deploy.tar networking/.env
fi
if [ -f "networking/acme.json" ]; then
    tar --append -f homelab-deploy.tar networking/acme.json
fi

# Compress the final archive
gzip homelab-deploy.tar
rm -f homelab-deploy.tar
trap "rm -f homelab-deploy.tar.gz" EXIT

# Show file size
FILE_SIZE=$(du -h homelab-deploy.tar.gz | cut -f1)
echo "📦 Archive size: $FILE_SIZE"

echo "📤 Uploading to server..."
scp homelab-deploy.tar.gz ${SERVER_USER}@${SERVER_HOST}:/tmp/

echo "🔄 Extracting and starting services..."
ssh ${SERVER_USER}@${SERVER_HOST} << 'EOF'
set -euo pipefail

# Create deployment directory
sudo mkdir -p /opt/homelab
cd /opt/homelab

# Extract new version
echo "📂 Extracting deployment..."
sudo tar -xzf /tmp/homelab-deploy.tar.gz 2>/dev/null || sudo tar -xzf /tmp/homelab-deploy.tar.gz
sudo chown -R $USER:$USER .

# Ensure acme.json has correct permissions
sudo touch networking/acme.json
sudo chmod 600 networking/acme.json

# Create web network if it doesn't exist
docker network create web 2>/dev/null || true

# Start services
echo "▶️ Starting services..."
./scripts/start_all.sh

echo "✅ Deployment complete!"
EOF

# Cleanup
rm homelab-deploy.tar.gz

echo "🎉 Deployment finished successfully!"
echo "Your services should be available at:"
echo "  - https://jamesmassucco.com (homepage)"
echo "  - https://blog.jamesmassucco.com (blog)"
echo "  - https://traefik.jamesmassucco.com (traefik dashboard)"