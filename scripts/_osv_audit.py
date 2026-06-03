#!/usr/bin/env python3
"""Fail (exit non-zero) if any pin in a --require-hashes lockfile has a known OSV advisory.

Usage: _osv_audit.py <lockfile>
Uses only the stdlib; requires network (runs on the connected build host, never the agent).
"""
import json
import re
import sys
import urllib.request


def query(name, version):
    body = json.dumps(
        {"version": version, "package": {"name": name, "ecosystem": "PyPI"}}
    ).encode()
    req = urllib.request.Request(
        "https://api.osv.dev/v1/query",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("vulns", [])


def main():
    pins = []
    with open(sys.argv[1]) as f:
        for line in f:
            m = re.match(r"^([A-Za-z0-9._-]+)==([^\s\\]+)", line.strip())
            if m:
                pins.append((m.group(1), m.group(2)))

    bad = False
    for name, version in pins:
        vulns = query(name, version)
        if vulns:
            bad = True
            print(f"VULN {name}=={version}: {[v.get('id') for v in vulns]}")
        else:
            print(f"ok   {name}=={version}")

    if bad:
        sys.exit("CVE scan FAILED: advisories present. Bump pins and re-vendor.")
    print("CVE scan clean.")


if __name__ == "__main__":
    main()
