#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for required in agent.py uzanet-vpn-agent.service; do
  if [[ ! -f "${script_dir}/${required}" ]]; then
    echo "Missing ${script_dir}/${required}" >&2
    exit 1
  fi
done
if [[ ! -f /etc/ppp/chap-secrets ]] || ! systemctl is-active --quiet xl2tpd; then
  echo "xl2tpd must be active and /etc/ppp/chap-secrets must exist." >&2
  exit 1
fi

install -d -m 0755 /usr/local/lib/uzanet-vpn-agent
install -m 0755 "${script_dir}/agent.py" /usr/local/lib/uzanet-vpn-agent/agent.py
install -d -m 0700 /etc/uzanet-vpn-agent
install -d -m 0700 /var/lib/uzanet-vpn-agent/backups

env_file=/etc/uzanet-vpn-agent/agent.env
if [[ ! -f ${env_file} ]]; then
  shared_secret=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  umask 077
  {
    echo "UZANET_AGENT_SHARED_SECRET=${shared_secret}"
    echo "UZANET_AGENT_SOCKET=/run/uzanet-vpn-agent/agent.sock"
    echo "UZANET_AGENT_SOCKET_GID=10001"
    echo "UZANET_CHAP_SECRETS=/etc/ppp/chap-secrets"
    echo "UZANET_PPP_SERVER_NAME=l2tpd"
    echo "UZANET_IP_RANGE_START=10.10.10.10"
    echo "UZANET_IP_RANGE_END=10.10.10.100"
  } > "${env_file}"
fi

install -m 0644 "${script_dir}/uzanet-vpn-agent.service" /etc/systemd/system/uzanet-vpn-agent.service
systemctl daemon-reload
systemctl enable --now uzanet-vpn-agent.service
systemctl --no-pager --full status uzanet-vpn-agent.service

echo
echo "Installed. Add this value to the Coolify app secrets as VPN_AGENT_SHARED_SECRET:"
sed -n 's/^UZANET_AGENT_SHARED_SECRET=//p' "${env_file}"
echo "Mount /run/uzanet-vpn-agent into the app container and redeploy."
