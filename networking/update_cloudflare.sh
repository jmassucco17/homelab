#!/bin/bash
cd "$(dirname "$0")"

set -euo pipefail

# --- Temporary files ---
TMP_IPV4=$(mktemp)
TMP_IPV6=$(mktemp)
TMP_ALL=$(mktemp)

# Fetch Cloudflare IPs
curl -s https://www.cloudflare.com/ips-v4 -o "$TMP_IPV4"
curl -s https://www.cloudflare.com/ips-v6 -o "$TMP_IPV6"

# Combine to single newline-delimited file
cat "$TMP_IPV4" > "$TMP_ALL"
printf '\n' >> "$TMP_ALL"
cat "$TMP_IPV6" >> "$TMP_ALL"

# Get current Cloudflare rules in UFW (parse the IPs only)
mapfile -t CURRENT_IPS < <(sudo ufw status | grep 'cloudflare' | awk '{print $3}' | sort -u)

# Get new Cloudflare IPs
mapfile -t NEW_IPS < <(sort -u "$TMP_ALL")

# Diff them
IPS_TO_REMOVE=()
IPS_TO_ADD=()

for ip in "${CURRENT_IPS[@]}"; do
    if ! grep -Fxq "$ip" "$TMP_ALL"; then
        IPS_TO_REMOVE+=("$ip")
    fi
done

for ip in "${NEW_IPS[@]}"; do
    if ! printf '%s\n' "${CURRENT_IPS[@]}" | grep -Fxq "$ip"; then
        IPS_TO_ADD+=("$ip")
    fi
done

echo "Updating firewall rules..."

# Remove outdated rules
if [[ ${#IPS_TO_REMOVE[@]} -gt 0 ]]; then
    echo "Removing outdated Cloudflare rules..."
    for ip in "${IPS_TO_REMOVE[@]}"; do
        sudo ufw delete allow from "$ip" to any port 443 proto tcp || true
    done
else
    echo "No Cloudflare rules to remove."
fi

# Add new rules
if [[ ${#IPS_TO_ADD[@]} -gt 0 ]]; then
    echo "Adding new Cloudflare rules..."
    for ip in "${IPS_TO_ADD[@]}"; do
        echo "$ip"
        sudo ufw allow from "$ip" to any port 443 proto tcp comment 'cloudflare'
    done
else
    echo "No new Cloudflare IPs to add."
fi

# Update Cloudflare env file for docker
echo "Updating docker env..."
ENV_FILE=".env"
ENV_VAR_NAME="CLOUDFLARE_TRUSTED_IPS"

# Turn IP files into comma-separated list
cf_ips=$(cat "$TMP_ALL" | tr '\n' ',' | sed 's/,$//')

# Replace CLOUDFLARE_TRUSTED_IPS in existing .env file
sed -i "s|^${ENV_VAR_NAME}=.*|${ENV_VAR_NAME}=${cf_ips}|" "$ENV_FILE"
echo "Updated."

# Cleanup temp files
rm -f "$TMP_IPV4" "$TMP_IPV6" "$TMP_ALL"
