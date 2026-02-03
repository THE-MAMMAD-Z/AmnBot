"""
URL processing scripts that can be run in parallel on a URL.
Each script function takes a URL as input and returns a dictionary with results.
"""
import logging
import time
from typing import Dict, Any
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import subprocess
import os
import tempfile
import json

logger = logging.getLogger(__name__)



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
    host = extract_host(url)
    
    wordlist = os.path.join(os.path.dirname(__file__), "dirsearch-wordlist.txt")
    if not os.path.exists(wordlist):
        wordlist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dirsearch-wordlist.txt")
        if not os.path.exists(wordlist):
            logger.error("Dirsearch wordlist not found")
            return {'error': 'wordlist missing'}

    # Temp file for JSON
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
        report_path = tmp.name

    cmd = (
        f"dirsearch -u {host} -w {wordlist} "
        f"-e php,html,js,bak,old,txt,asp,aspx,jsp -t 50 "
        f"--json-report {report_path} "   # ← try this first
        "--quiet-mode "                   # or -q if --quiet-mode fails
        "--no-color "
        "--exclude-status=301,302,400 "
    )

    print(f"[+] Starting Dirsearch on {url} (attempting JSON report)...")
    output = run_command(cmd)

    metadata = {
        'script_name': 'dirsearch scan for vulnerability',
        'raw_output': output,
    }

    try:
        with open(report_path, 'r') as f:
            content = f.read().strip()
            if not content:
                raise ValueError("Empty report file")
            results = json.loads(content)
        
        # Adapt based on actual structure (often flat list or {'results': [...]})
        findings = results if isinstance(results, list) else results.get('results', [])
        
        interesting = [
            entry for entry in findings
            if isinstance(entry, dict) and entry.get('status') in [200, 403, 500, 401, 302]  # include some redirects if useful
        ]

        metadata['structured_results'] = interesting
        metadata['summary_for_llm'] = (
            f"Dirsearch found {len(interesting)} potentially interesting paths on {host}:\n"
            + "\n".join(
                f"- {entry.get('url', entry.get('path', 'unknown'))} → status {entry.get('status')} "
                f"(size: {entry.get('size', 'unknown')})"
                for entry in interesting
            )
        )

    except (json.JSONDecodeError, ValueError, Exception) as e:
        logger.error(f"Report parsing failed: {e}")
        metadata['error'] = f"Failed to parse JSON report: {str(e)}\nRaw console: {output}"
        # Fallback: parse console output minimally
        lines = output.splitlines()
        interesting_lines = [line.strip() for line in lines if ' 200 ' in line or ' 403 ' in line or ' 500 ' in line]
        if interesting_lines:
            metadata['fallback_summary'] = "\n".join(interesting_lines)

    finally:
        try:
            os.unlink(report_path)
        except:
            pass

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
    dirsearch_scan
]

