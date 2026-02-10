"""
URL processing scripts that can be run in parallel on a URL.
Each script function takes a URL as input and returns a dictionary with results.
"""
import logging
from urllib.parse import urlparse
import subprocess
import os
from typing import Dict, Any, List
import os
import uuid
import re

logger = logging.getLogger(__name__)

DIRSEARCH_LINE_RE = re.compile(
    r"^(\d+)\s+(\S+)\s+(.+)$"  # Match: status size url
)

def run_command(command, output_file=None, timeout=900):
    """
    Execute a shell command and capture its output.
    Optionally save output to a file.
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout  # Default 15 minutes timeout
        )
        output = result.stdout + "\n" + result.stderr

        if output_file:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(output)
        
        return output
    except subprocess.TimeoutExpired:
        return "[ERROR] Command timed out after {} seconds.".format(timeout)
    except Exception as e:
        return f"[ERROR] {str(e)}"

def ensure_http(url):
    if not url.startswith("http"):
        url = "https://" + url
    return url

def extract_host(target):
    """
    Extract hostname/IP from URL or return raw input if it's already an IP/hostname.
    """
    if target.startswith(("http://", "https://")):
        parsed = urlparse(target)
        return parsed.netloc.split(":")[0]  # Remove port if present
    return target

# 1. Nmap - Comprehensive port and service scan
def nmap_scan(url: str) -> Dict[str, Any]:
    """Perform Nmap scan: service detection, default scripts, OS detection, all ports"""
    host = extract_host(url)
    print(host)
    cmd = f"nmap -sS -O -p- --min-rate 1000 -T4 {host} "
    print(f"[+] Starting Nmap scan on {host}...")
    output = run_command(cmd)
    print(output)
    metadata = {
            'script_name': 'nmap scan for vulnrability',
            'script_output' : output
        }
    return metadata

# 2. Dirsearch - Brute force hidden directories and files using common wordlist
def dirsearch_scan(url: str) -> Dict[str, Any]:
    """
    Run dirsearch and return ONLY parsed JSON result.
    No stdout, no raw output.
    """

    print(f"[+] Starting Dirsearch scan on {url}...")

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # Look for wordlist in multiple possible locations
    possible_paths = [
        os.path.join(base_dir, "dirsearch-wordlist.txt"),  # In chat directory
        os.path.join(os.path.dirname(base_dir), "dirsearch-wordlist.txt"),  # In project root
        "/app/dirsearch-wordlist.txt",  # In container app directory
        "./dirsearch-wordlist.txt",  # Current working directory
    ]

    wordlist = None
    for path in possible_paths:
        if os.path.exists(path):
            wordlist = path
            break

    if wordlist is None:
        return {
            "script_name": "dirsearch",
            "target": url,
            "error": "wordlist missing",
        }

    output_file = os.path.join(
        base_dir, f"dirsearch_results.txt"
    )

    cmd = (
        f"dirsearch -u {url} -w {wordlist} -e php,html,js,txt,asp,aspx -t 10 --include-status=200,401,403,500 --random-agent -o {output_file}"
    )

    run_command(cmd)

    results: List[Dict[str, Any]] = []

    if os.path.exists(output_file):
        print('in if block')
        print(output_file)
        with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('Target:') or 'Dirsearch started' in line:
                    continue

                # Example of actual format:
                # 200     4KB  https://example.com/admin
                match = DIRSEARCH_LINE_RE.match(line)
                if not match:
                    continue

                status = int(match.group(1))
                # group(2) is the size (e.g., "4KB")
                full_url = match.group(3)

                # Extract just the path portion from the full URL
                parsed_url = urlparse(full_url)
                path = parsed_url.path

                results.append({
                    "status": status,
                    "path": path,
                    "url": full_url,
                })

    metadata = {
        "script_name": "dirsearch",
        "target": url,
        "total_found": len(results),
        "results": results,
    }
    return metadata
    



# 3. Nuclei - Fast template-based vulnerability scanner
def nuclei_scan(url: str) -> Dict[str, Any]:
    """Run Nuclei with default templates against the target"""
    # host = extract_host(url)
    cmd = f"nuclei -u {url} -severity low,medium,high,critical -json "
    print(f"[+] Starting Nuclei scan on {url}...")
    output = run_command(cmd)
    print(output)
    metadata = {
            'script_name': 'nuclei scan for vulnrability',
            'script_output' : output
        }
    return metadata


def nikto_scan(target):
    """Identify web server and other vulnerabilities"""
    url = ensure_http(target).rstrip("/")
    cmd = f"nikto -h {url}"
    print(f"[+] Starting Nikto scan on {url}...")
    output = run_command(cmd)
    print(output)
    metadata = {
            'script_name': 'nikto scan for vulnrability',
            'script_output' : output
        }
    return metadata


# 4. Gobuster - Alternative directory brute force (DNS mode also possible)
# def gobuster_scan(target):
#     """Fast directory brute force using gobuster"""
#     url = ensure_http(target).rstrip("/")
#     host = extract_host(target)
#     wordlist = "/usr/share/wordlists/dirb/common.txt"
#     output_file = os.path.join(OUTPUT_DIR, f"gobuster_{host}.txt")
#     cmd = f"gobuster dir -u {url} -w {wordlist} -t 50 -o {output_file}"
#     print(f"[+] Starting Gobuster on {url}...")
#     output = run_command(cmd, output_file)
#     return output, output_file

def whatweb_scan(url: str) -> Dict[str, Any]:
    """Identify CMS, frameworks, servers, and other web technologies"""
    host = extract_host(url)
    cmd = f"whatweb -a 3 {url} "
    print(f"[+] Starting WhatWeb fingerprinting on {url}...")
    output = run_command(cmd)
    print(output)
    metadata = {
            'script_name': 'whatweb scan for vulnrability',
            'script_output' : output
        }
    return metadata

# List of all available scripts
AVAILABLE_SCRIPTS = [
    nmap_scan,
    # nuclei_scan,
    dirsearch_scan,
    nikto_scan,
    whatweb_scan
]

