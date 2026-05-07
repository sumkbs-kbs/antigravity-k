---
name: expose-tunnel
description: |
  Automates the exposure of Antigravity-K to the public internet using Cloudflare Zero Trust Tunnels.
  Handles cloudflared installation, DNS routing, and interactive user guidance for nameserver setup.
  Use when the user asks to "expose the app to the internet", "setup cloudflare tunnel", or "make it globally accessible".
---

# Expose Tunnel Skill

This skill allows Antigravity-K to automatically set up a Cloudflare Tunnel, mapping `localhost:5173` to a public domain with an optional PIN security layer.

## How to use this skill

1. **Verify Prerequisites**: Ask the user if they have purchased a custom domain (e.g., from Gabia, Namecheap, Route53) and if they have a Cloudflare account.
2. **Execute Script**: Run the automated setup script.

```bash
python scripts/setup_tunnel.py
```

3. **Guide the User**:
   - The script will ask for the domain name and open a Cloudflare authentication window.
   - Instruct the user to verify their Cloudflare email if they haven't already.
   - Instruct the user to click `Authorize` on the browser window that opens.
   - The script will output the new nameservers (e.g., `anna.ns.cloudflare.com`).
   - Instruct the user to log into their domain registrar and replace their nameservers with the ones provided by Cloudflare.
   - Wait for DNS propagation (can take 10-30 minutes).
   - Verify that the tunnel is running successfully.

4. **PIN Security (Optional but Recommended)**:
   - Ensure the user's `config.yaml` has `security: access_pin: "0000"` configured.
   - Remind the user that the public URL is protected by the PIN.
