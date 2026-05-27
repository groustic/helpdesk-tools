#!/usr/bin/env python3
"""
Auth Log Parser
Parses Windows Event Logs and Linux auth logs for suspicious activity.
Detects failed logins, brute force attempts, off-hours access, and unknown users.
Outputs a summary report.
"""

import re
import os
import sys
import json
import argparse
from datetime import datetime, time
from collections import defaultdict

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

# Off-hours window (flag logins outside 7am-7pm)
BUSINESS_HOURS_START = time(7, 0)
BUSINESS_HOURS_END   = time(19, 0)

# Brute force threshold: X failures from same IP within Y minutes
BRUTE_FORCE_THRESHOLD = 5
BRUTE_FORCE_WINDOW    = 10  # minutes

# Known/expected usernames (add your environment's service accounts etc.)
KNOWN_USERS = set()  # leave empty to skip unknown user detection

REPORT_FILE = "log_report.txt"

# ─────────────────────────────────────────────
# DATA STRUCTURES
# ─────────────────────────────────────────────

class LogEvent:
    def __init__(self, timestamp, username, source_ip, event_type, raw, platform):
        self.timestamp  = timestamp   # datetime object
        self.username   = username
        self.source_ip  = source_ip
        self.event_type = event_type  # "failed", "success", "other"
        self.raw        = raw
        self.platform   = platform    # "linux" or "windows"

# ─────────────────────────────────────────────
# LINUX PARSER (/var/log/auth.log)
# ─────────────────────────────────────────────

# Example lines:
# Jan  5 03:17:12 server sshd[1234]: Failed password for root from 192.168.1.10 port 22 ssh2
# Jan  5 03:17:15 server sshd[1234]: Accepted password for alice from 10.0.0.5 port 22 ssh2
# Jan  5 03:17:18 server sshd[1234]: Invalid user hacker from 203.0.113.1 port 51234

LINUX_FAILED_RE  = re.compile(
    r'(\w+\s+\d+\s+\d+:\d+:\d+).*Failed password for (?:invalid user )?(\S+) from (\S+)'
)
LINUX_SUCCESS_RE = re.compile(
    r'(\w+\s+\d+\s+\d+:\d+:\d+).*Accepted \S+ for (\S+) from (\S+)'
)
LINUX_INVALID_RE = re.compile(
    r'(\w+\s+\d+\s+\d+:\d+:\d+).*Invalid user (\S+) from (\S+)'
)

def parse_linux_timestamp(ts_str):
    current_year = datetime.now().year
    try:
        return datetime.strptime(f"{current_year} {ts_str.strip()}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None

def parse_linux_log(filepath):
    events = []
    with open(filepath, "r", errors="ignore") as f:
        for line in f:
            line = line.strip()

            m = LINUX_FAILED_RE.search(line)
            if m:
                ts = parse_linux_timestamp(m.group(1))
                if ts:
                    events.append(LogEvent(ts, m.group(2), m.group(3), "failed", line, "linux"))
                continue

            m = LINUX_SUCCESS_RE.search(line)
            if m:
                ts = parse_linux_timestamp(m.group(1))
                if ts:
                    events.append(LogEvent(ts, m.group(2), m.group(3), "success", line, "linux"))
                continue

            m = LINUX_INVALID_RE.search(line)
            if m:
                ts = parse_linux_timestamp(m.group(1))
                if ts:
                    events.append(LogEvent(ts, m.group(2), m.group(3), "failed", line, "linux"))

    return events

# ─────────────────────────────────────────────
# WINDOWS PARSER (exported Security Event Log CSV)
# ─────────────────────────────────────────────

# Expects a CSV export from Windows Event Viewer with columns:
# TimeCreated, EventId, AccountName, IpAddress, LogonType, Message
# EventId 4625 = failed logon, 4624 = successful logon

import csv

def parse_windows_log(filepath):
    events = []
    with open(filepath, "r", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                event_id  = row.get("EventId", "").strip()
                ts_str    = row.get("TimeCreated", "").strip()
                username  = row.get("AccountName", "").strip()
                source_ip = row.get("IpAddress", "-").strip()
                raw       = str(row)

                # Parse timestamp (common Windows formats)
                ts = None
                for fmt in ("%m/%d/%Y %I:%M:%S %p", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                    try:
                        ts = datetime.strptime(ts_str, fmt)
                        break
                    except ValueError:
                        continue

                if not ts:
                    continue

                if event_id == "4625":
                    events.append(LogEvent(ts, username, source_ip, "failed", raw, "windows"))
                elif event_id == "4624":
                    events.append(LogEvent(ts, username, source_ip, "success", raw, "windows"))

            except Exception:
                continue

    return events

# ─────────────────────────────────────────────
# DETECTION ENGINE
# ─────────────────────────────────────────────

def detect_brute_force(events):
    """Flag IPs with >= BRUTE_FORCE_THRESHOLD failures within BRUTE_FORCE_WINDOW minutes."""
    failures_by_ip = defaultdict(list)
    for e in events:
        if e.event_type == "failed" and e.source_ip and e.source_ip not in ("-", "::1", "127.0.0.1"):
            failures_by_ip[e.source_ip].append(e.timestamp)

    flagged = {}
    for ip, timestamps in failures_by_ip.items():
        timestamps.sort()
        for i in range(len(timestamps)):
            window = [t for t in timestamps[i:] if (t - timestamps[i]).total_seconds() <= BRUTE_FORCE_WINDOW * 60]
            if len(window) >= BRUTE_FORCE_THRESHOLD:
                flagged[ip] = {
                    "count":      len(timestamps),
                    "first_seen": timestamps[0],
                    "last_seen":  timestamps[-1],
                    "max_burst":  len(window)
                }
                break

    return flagged

def detect_off_hours(events):
    """Flag successful logins outside business hours."""
    flagged = []
    for e in events:
        if e.event_type == "success":
            t = e.timestamp.time()
            if not (BUSINESS_HOURS_START <= t <= BUSINESS_HOURS_END):
                flagged.append(e)
    return flagged

def detect_unknown_users(events):
    """Flag logins from usernames not in KNOWN_USERS (only if KNOWN_USERS is populated)."""
    if not KNOWN_USERS:
        return []
    flagged = []
    for e in events:
        if e.username and e.username.lower() not in {u.lower() for u in KNOWN_USERS}:
            flagged.append(e)
    return flagged

def detect_high_failure_users(events):
    """Flag usernames with high numbers of failed attempts."""
    failures = defaultdict(int)
    for e in events:
        if e.event_type == "failed" and e.username:
            failures[e.username] += 1
    return {u: c for u, c in failures.items() if c >= BRUTE_FORCE_THRESHOLD}

# ─────────────────────────────────────────────
# REPORT
# ─────────────────────────────────────────────

def build_report(events, brute_ips, off_hours, unknown_users, high_fail_users, source_files):
    lines = []
    sep   = "=" * 70
    dash  = "-" * 70

    total       = len(events)
    failed      = sum(1 for e in events if e.event_type == "failed")
    successful  = sum(1 for e in events if e.event_type == "success")
    linux_count = sum(1 for e in events if e.platform == "linux")
    win_count   = sum(1 for e in events if e.platform == "windows")

    lines.append(sep)
    lines.append("  AUTH LOG PARSER - SECURITY REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(sep)

    lines.append("\n  SOURCE FILES")
    lines.append(dash)
    for f in source_files:
        lines.append(f"  {f}")

    lines.append("\n  SUMMARY")
    lines.append(dash)
    lines.append(f"  Total events parsed   : {total}")
    lines.append(f"  Failed login attempts : {failed}")
    lines.append(f"  Successful logins     : {successful}")
    lines.append(f"  Linux events          : {linux_count}")
    lines.append(f"  Windows events        : {win_count}")
    lines.append(f"  Brute force IPs       : {len(brute_ips)}")
    lines.append(f"  Off-hours logins      : {len(off_hours)}")
    lines.append(f"  High-failure users    : {len(high_fail_users)}")
    lines.append(f"  Unknown users flagged : {len(unknown_users)}")

    # Brute force
    lines.append("\n  BRUTE FORCE ATTEMPTS")
    lines.append(dash)
    if brute_ips:
        for ip, info in sorted(brute_ips.items(), key=lambda x: -x[1]["count"]):
            lines.append(f"  IP: {ip}")
            lines.append(f"    Total failures : {info['count']}")
            lines.append(f"    Max burst      : {info['max_burst']} in {BRUTE_FORCE_WINDOW} min")
            lines.append(f"    First seen     : {info['first_seen']}")
            lines.append(f"    Last seen      : {info['last_seen']}")
    else:
        lines.append("  None detected.")

    # High failure users
    lines.append("\n  HIGH-FAILURE USERNAMES")
    lines.append(dash)
    if high_fail_users:
        for user, count in sorted(high_fail_users.items(), key=lambda x: -x[1]):
            lines.append(f"  {user:<30} {count} failures")
    else:
        lines.append("  None detected.")

    # Off-hours
    lines.append(f"\n  OFF-HOURS SUCCESSFUL LOGINS (outside {BUSINESS_HOURS_START.strftime('%H:%M')}-{BUSINESS_HOURS_END.strftime('%H:%M')})")
    lines.append(dash)
    if off_hours:
        for e in sorted(off_hours, key=lambda x: x.timestamp):
            lines.append(f"  [{e.timestamp}] user={e.username} ip={e.source_ip} platform={e.platform}")
    else:
        lines.append("  None detected.")

    # Unknown users
    lines.append("\n  UNKNOWN USER ATTEMPTS")
    lines.append(dash)
    if not KNOWN_USERS:
        lines.append("  Skipped (KNOWN_USERS list is empty — populate it to enable this check).")
    elif unknown_users:
        seen = set()
        for e in unknown_users:
            key = (e.username, e.source_ip)
            if key not in seen:
                seen.add(key)
                lines.append(f"  [{e.timestamp}] user={e.username} ip={e.source_ip} platform={e.platform}")
    else:
        lines.append("  None detected.")

    # Top attacking IPs
    lines.append("\n  TOP ATTACKING IPs (by failure count)")
    lines.append(dash)
    ip_failures = defaultdict(int)
    for e in events:
        if e.event_type == "failed" and e.source_ip and e.source_ip not in ("-", "::1"):
            ip_failures[e.source_ip] += 1
    top_ips = sorted(ip_failures.items(), key=lambda x: -x[1])[:10]
    if top_ips:
        for ip, count in top_ips:
            bar = "█" * min(count, 40)
            lines.append(f"  {ip:<20} {str(count).rjust(5)}  {bar}")
    else:
        lines.append("  No attacking IPs found.")

    lines.append("\n" + sep)
    lines.append("  END OF REPORT")
    lines.append(sep)

    return "\n".join(lines)

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def print_color(text, color):
    colors = {"red": "\033[31m", "yellow": "\033[33m", "green": "\033[32m", "cyan": "\033[36m"}
    print(f"{colors.get(color, '')}{text}\033[0m")

def main():
    parser = argparse.ArgumentParser(
        description="Auth Log Parser - Detects suspicious login activity in Linux and Windows logs."
    )
    parser.add_argument(
        "files", nargs="+",
        help="Log files to parse. Linux: auth.log style. Windows: CSV export from Event Viewer."
    )
    parser.add_argument(
        "--known-users", nargs="*", default=[],
        help="List of known/expected usernames. Logins from others will be flagged."
    )
    parser.add_argument(
        "--brute-threshold", type=int, default=BRUTE_FORCE_THRESHOLD,
        help=f"Failed login threshold for brute force detection (default: {BRUTE_FORCE_THRESHOLD})"
    )
    parser.add_argument(
        "--brute-window", type=int, default=BRUTE_FORCE_WINDOW,
        help=f"Time window in minutes for brute force detection (default: {BRUTE_FORCE_WINDOW})"
    )
    parser.add_argument(
        "--no-report", action="store_true",
        help="Print results to terminal only, do not save report file."
    )
    args = parser.parse_args()

    global BRUTE_FORCE_THRESHOLD, BRUTE_FORCE_WINDOW, KNOWN_USERS
    BRUTE_FORCE_THRESHOLD = args.brute_threshold
    BRUTE_FORCE_WINDOW    = args.brute_window
    if args.known_users:
        KNOWN_USERS = set(args.known_users)

    all_events   = []
    source_files = []

    for filepath in args.files:
        if not os.path.exists(filepath):
            print_color(f"  File not found: {filepath}", "red")
            continue

        source_files.append(filepath)
        ext = filepath.lower()

        if ext.endswith(".csv"):
            print_color(f"  Parsing Windows log: {filepath}", "cyan")
            events = parse_windows_log(filepath)
        else:
            print_color(f"  Parsing Linux log: {filepath}", "cyan")
            events = parse_linux_log(filepath)

        print(f"  Found {len(events)} events.")
        all_events.extend(events)

    if not all_events:
        print_color("\n  No events parsed. Check your file paths and formats.", "red")
        sys.exit(1)

    print_color(f"\n  Total events: {len(all_events)}. Running detection...", "cyan")

    brute_ips       = detect_brute_force(all_events)
    off_hours       = detect_off_hours(all_events)
    unknown_users   = detect_unknown_users(all_events)
    high_fail_users = detect_high_failure_users(all_events)

    report = build_report(all_events, brute_ips, off_hours, unknown_users, high_fail_users, source_files)

    print("\n" + report)

    if not args.no_report:
        with open(REPORT_FILE, "w") as f:
            f.write(report)
        print_color(f"\n  Report saved to {REPORT_FILE}", "green")

if __name__ == "__main__":
    main()
