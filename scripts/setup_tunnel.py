#!/usr/bin/env python3
import os
import platform
import stat
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

# Constants
CLOUDFLARED_DIR = Path.home() / ".gemini" / "antigravity"
CLOUDFLARED_BIN = CLOUDFLARED_DIR / "cloudflared"
CERT_PATH = Path.home() / ".cloudflared" / "cert.pem"
TUNNEL_NAME = "antigravity"


def get_download_url():
    """Determine the correct cloudflared binary URL based on OS and architecture."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Map architectures
    arch = "amd64"
    if machine in ["arm64", "aarch64"]:
        arch = "arm64"

    if system == "darwin":
        return f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-{arch}"
    elif system == "linux":
        return f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"
    elif system == "windows":
        return f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-{arch}.exe"
    else:
        raise Exception(f"Unsupported system: {system}")


def install_cloudflared():
    """Download and install cloudflared if not present."""
    if CLOUDFLARED_BIN.exists():
        print(f"[+] cloudflared already installed at {CLOUDFLARED_BIN}")
        return

    print("[+] Downloading cloudflared...")
    CLOUDFLARED_DIR.mkdir(parents=True, exist_ok=True)
    url = get_download_url()

    if platform.system().lower() == "windows":
        dest = CLOUDFLARED_DIR / "cloudflared.exe"
    else:
        dest = CLOUDFLARED_BIN

    urllib.request.urlretrieve(url, dest)

    # Make executable
    if platform.system().lower() != "windows":
        st = os.stat(dest)
        os.chmod(dest, st.st_mode | stat.S_IEXEC)

    print(f"[+] Successfully installed cloudflared to {dest}")


def run_login():
    """Run cloudflared tunnel login and wait for cert.pem."""
    if CERT_PATH.exists():
        print("[+] Certificate already exists. Skipping login.")
        return

    print("[!] Initiating Cloudflare authentication...")
    # Start the login process
    process = subprocess.Popen(
        [str(CLOUDFLARED_BIN), "tunnel", "login"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    auth_url = None
    # Parse output to find the URL
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(line, end="")
        if "https://dash.cloudflare.com/argotunnel" in line:
            auth_url = line.strip()
            print(f"\n[+] Opening browser automatically to: {auth_url}\n")
            try:
                webbrowser.open(auth_url)
            except Exception as e:
                print(f"[-] Could not open browser automatically: {e}")
            break

    print("\n[!] Please log in and authorize the tunnel in your browser.")
    print("[!] Waiting for certificate to be downloaded... (Timeout: 5 minutes)")

    # Wait up to 5 minutes for cert.pem
    start_time = time.time()
    while time.time() - start_time < 300:
        if CERT_PATH.exists():
            print("[+] Certificate successfully acquired!")
            try:
                process.terminate()
            except Exception:
                pass
            return
        time.sleep(2)

    print("[-] Timeout waiting for certificate. Please try again.")
    process.terminate()
    sys.exit(1)


def setup_tunnel(domain):
    """Create the tunnel and route DNS."""
    print(f"[+] Creating tunnel '{TUNNEL_NAME}'...")
    subprocess.run([str(CLOUDFLARED_BIN), "tunnel", "create", TUNNEL_NAME], check=False)

    print(f"[+] Routing DNS for {domain} to tunnel '{TUNNEL_NAME}'...")
    result = subprocess.run(
        [str(CLOUDFLARED_BIN), "tunnel", "route", "dns", TUNNEL_NAME, domain],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        if "already exists" in result.stderr.lower():
            print(f"[+] Route already exists for {domain}.")
        else:
            print(f"[-] Error routing DNS: {result.stderr}")
            sys.exit(1)

    print("\n[================================================]")
    print("[✅] Tunnel Setup Complete!")
    print("[+] Your local server is now globally exposed at:")
    print(f"[+] https://{domain}")
    print("[================================================]\n")

    print("To run the tunnel in the background, you can use the following command:")
    print(f"nohup {CLOUDFLARED_BIN} tunnel run --url http://localhost:5173 {TUNNEL_NAME} > cloudflared.log 2>&1 &\n")


if __name__ == "__main__":
    print("🚀 Antigravity-K Global Access Automator 🚀")
    domain = input("Enter your custom domain (e.g., antigravity-k.cloud): ").strip()
    if not domain:
        print("[-] Domain is required.")
        sys.exit(1)

    try:
        install_cloudflared()
        run_login()
        setup_tunnel(domain)
    except KeyboardInterrupt:
        print("\n[-] Setup aborted.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[-] Unexpected error: {e}")
        sys.exit(1)
