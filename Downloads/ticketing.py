#!/usr/bin/env python3
"""
Help Desk Ticketing System
A command-line tool for managing IT support tickets.
"""

import json
import os
import sys
from datetime import datetime

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────

DATA_FILE = "tickets.json"
LOG_FILE  = "tickets.log"

PRIORITIES  = ["Low", "Medium", "High", "Critical"]
CATEGORIES  = ["Hardware", "Software", "Network", "Account", "Other"]
STATUSES    = ["Open", "In Progress", "Resolved", "Closed"]

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

# ─────────────────────────────────────────────
# DATA LAYER
# ─────────────────────────────────────────────

def load_tickets():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_tickets(tickets):
    with open(DATA_FILE, "w") as f:
        json.dump(tickets, f, indent=2)

def next_id(tickets):
    if not tickets:
        return 1
    return max(t["id"] for t in tickets) + 1

# ─────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────

PRIORITY_COLORS = {
    "Low":      "\033[32m",   # green
    "Medium":   "\033[33m",   # yellow
    "High":     "\033[91m",   # orange/red
    "Critical": "\033[31m",   # red
}
STATUS_COLORS = {
    "Open":        "\033[94m",  # blue
    "In Progress": "\033[93m",  # yellow
    "Resolved":    "\033[92m",  # green
    "Closed":      "\033[90m",  # grey
}
RESET = "\033[0m"

def colorize(text, color_map):
    color = color_map.get(text, "")
    return f"{color}{text}{RESET}" if color else text

def divider(char="─", width=70):
    print(char * width)

def print_ticket_row(t):
    pid   = str(t["id"]).ljust(5)
    title = t["title"][:35].ljust(36)
    pri   = colorize(t["priority"].ljust(8), PRIORITY_COLORS)
    cat   = t["category"].ljust(10)
    sta   = colorize(t["status"].ljust(12), STATUS_COLORS)
    print(f"  #{pid} {title} {pri} {cat} {sta} {t['created'][:10]}")

def print_ticket_detail(t):
    divider("═")
    print(f"  Ticket #{t['id']}  |  {colorize(t['priority'], PRIORITY_COLORS)}  |  {colorize(t['status'], STATUS_COLORS)}")
    divider()
    print(f"  Title      : {t['title']}")
    print(f"  Category   : {t['category']}")
    print(f"  Submitter  : {t['submitter']}")
    print(f"  Assignee   : {t.get('assignee') or 'Unassigned'}")
    print(f"  Created    : {t['created']}")
    print(f"  Updated    : {t['updated']}")
    print(f"\n  Description:\n  {t['description']}")
    if t.get("notes"):
        print(f"\n  Notes / Updates:")
        for n in t["notes"]:
            print(f"    [{n['timestamp'][:16]}] {n['text']}")
    divider("═")

# ─────────────────────────────────────────────
# PROMPT HELPERS
# ─────────────────────────────────────────────

def choose(prompt, options):
    print(f"\n  {prompt}")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        try:
            choice = int(input("  Select: "))
            if 1 <= choice <= len(options):
                return options[choice - 1]
        except ValueError:
            pass
        print("  Invalid selection.")

def ask(prompt, required=True):
    while True:
        val = input(f"  {prompt}: ").strip()
        if val or not required:
            return val
        print("  This field is required.")

# ─────────────────────────────────────────────
# ACTIONS
# ─────────────────────────────────────────────

def create_ticket(tickets):
    print("\n  ── New Ticket ──")
    title       = ask("Title")
    description = ask("Description")
    submitter   = ask("Submitter name")
    priority    = choose("Priority", PRIORITIES)
    category    = choose("Category", CATEGORIES)
    assignee    = ask("Assignee (leave blank to skip)", required=False)

    now = datetime.now().isoformat()
    ticket = {
        "id":          next_id(tickets),
        "title":       title,
        "description": description,
        "submitter":   submitter,
        "assignee":    assignee,
        "priority":    priority,
        "category":    category,
        "status":      "Open",
        "created":     now,
        "updated":     now,
        "notes":       []
    }
    tickets.append(ticket)
    save_tickets(tickets)
    log(f"Ticket #{ticket['id']} created: '{title}' [{priority}] [{category}]")
    print(f"\n  Ticket #{ticket['id']} created successfully.")

def view_tickets(tickets, filter_status=None, filter_priority=None, filter_category=None):
    results = tickets[:]
    if filter_status:
        results = [t for t in results if t["status"] == filter_status]
    if filter_priority:
        results = [t for t in results if t["priority"] == filter_priority]
    if filter_category:
        results = [t for t in results if t["category"] == filter_category]

    if not results:
        print("\n  No tickets found.")
        return

    divider()
    print(f"  {'ID':<6} {'Title':<37} {'Priority':<9} {'Category':<11} {'Status':<13} {'Created'}")
    divider()
    for t in sorted(results, key=lambda x: x["id"]):
        print_ticket_row(t)
    divider()
    print(f"  {len(results)} ticket(s) shown.")

def view_ticket_detail(tickets):
    tid = ask("Enter ticket ID")
    try:
        tid = int(tid)
    except ValueError:
        print("  Invalid ID.")
        return
    match = next((t for t in tickets if t["id"] == tid), None)
    if not match:
        print(f"  Ticket #{tid} not found.")
        return
    print_ticket_detail(match)

def update_ticket(tickets):
    tid = ask("Enter ticket ID to update")
    try:
        tid = int(tid)
    except ValueError:
        print("  Invalid ID.")
        return
    ticket = next((t for t in tickets if t["id"] == tid), None)
    if not ticket:
        print(f"  Ticket #{tid} not found.")
        return

    print(f"\n  Updating Ticket #{tid}: {ticket['title']}")
    print("  Leave blank to keep current value.\n")

    new_status   = choose("New status", STATUSES)
    new_priority = choose("New priority", PRIORITIES)
    new_assignee = ask(f"Assignee (current: {ticket.get('assignee') or 'Unassigned'})", required=False)
    note_text    = ask("Add a note (optional)", required=False)

    ticket["status"]   = new_status
    ticket["priority"] = new_priority
    ticket["updated"]  = datetime.now().isoformat()

    if new_assignee:
        ticket["assignee"] = new_assignee
    if note_text:
        ticket["notes"].append({
            "timestamp": datetime.now().isoformat(),
            "text":      note_text
        })

    save_tickets(tickets)
    log(f"Ticket #{tid} updated: status={new_status}, priority={new_priority}")
    print(f"\n  Ticket #{tid} updated.")

def close_ticket(tickets):
    tid = ask("Enter ticket ID to close")
    try:
        tid = int(tid)
    except ValueError:
        print("  Invalid ID.")
        return
    ticket = next((t for t in tickets if t["id"] == tid), None)
    if not ticket:
        print(f"  Ticket #{tid} not found.")
        return
    if ticket["status"] == "Closed":
        print("  Ticket is already closed.")
        return

    ticket["status"]  = "Closed"
    ticket["updated"] = datetime.now().isoformat()
    note = ask("Closing note (optional)", required=False)
    if note:
        ticket["notes"].append({
            "timestamp": datetime.now().isoformat(),
            "text":      f"[CLOSED] {note}"
        })

    save_tickets(tickets)
    log(f"Ticket #{tid} closed.")
    print(f"\n  Ticket #{tid} closed.")

def search_tickets(tickets):
    query = ask("Search query").lower()
    results = [
        t for t in tickets
        if query in t["title"].lower()
        or query in t["description"].lower()
        or query in t.get("submitter", "").lower()
        or query in t.get("assignee", "").lower()
    ]
    if not results:
        print(f"\n  No tickets matched '{query}'.")
        return
    print(f"\n  Results for '{query}':")
    view_tickets(results)

def filter_tickets(tickets):
    print("\n  Filter by:")
    field = choose("Field", ["Status", "Priority", "Category"])
    if field == "Status":
        val = choose("Status", STATUSES)
        view_tickets(tickets, filter_status=val)
    elif field == "Priority":
        val = choose("Priority", PRIORITIES)
        view_tickets(tickets, filter_priority=val)
    elif field == "Category":
        val = choose("Category", CATEGORIES)
        view_tickets(tickets, filter_category=val)

def show_stats(tickets):
    if not tickets:
        print("\n  No tickets in the system.")
        return

    total = len(tickets)
    divider("═")
    print("  TICKET STATISTICS")
    divider()

    print(f"\n  Total tickets: {total}\n")

    print("  By Status:")
    for s in STATUSES:
        count = sum(1 for t in tickets if t["status"] == s)
        bar   = "█" * count
        print(f"    {s:<14} {str(count).rjust(3)}  {colorize(bar, STATUS_COLORS)}")

    print("\n  By Priority:")
    for p in PRIORITIES:
        count = sum(1 for t in tickets if t["priority"] == p)
        bar   = "█" * count
        print(f"    {p:<14} {str(count).rjust(3)}  {colorize(bar, PRIORITY_COLORS)}")

    print("\n  By Category:")
    for c in CATEGORIES:
        count = sum(1 for t in tickets if t["category"] == c)
        print(f"    {c:<14} {str(count).rjust(3)}")

    open_tickets = [t for t in tickets if t["status"] not in ("Resolved", "Closed")]
    critical     = [t for t in open_tickets if t["priority"] == "Critical"]

    print(f"\n  Open / In Progress : {len(open_tickets)}")
    print(f"  Critical open      : {len(critical)}")

    if critical:
        print("\n  Critical tickets requiring attention:")
        for t in critical:
            print(f"    #{t['id']} - {t['title']}")

    divider("═")

# ─────────────────────────────────────────────
# MENU
# ─────────────────────────────────────────────

def show_menu():
    print("\n" + "═" * 50)
    print("   HELP DESK TICKETING SYSTEM")
    print("═" * 50)
    print("  1. Create ticket")
    print("  2. View all tickets")
    print("  3. View ticket detail")
    print("  4. Update ticket")
    print("  5. Close ticket")
    print("  6. Search tickets")
    print("  7. Filter tickets")
    print("  8. Stats & reporting")
    print("  Q. Quit")
    print("─" * 50)

def main():
    while True:
        tickets = load_tickets()
        show_menu()
        choice = input("  Select: ").strip().upper()

        if choice == "1":
            create_ticket(tickets)
        elif choice == "2":
            view_tickets(tickets)
        elif choice == "3":
            view_ticket_detail(tickets)
        elif choice == "4":
            update_ticket(tickets)
        elif choice == "5":
            close_ticket(tickets)
        elif choice == "6":
            search_tickets(tickets)
        elif choice == "7":
            filter_tickets(tickets)
        elif choice == "8":
            show_stats(tickets)
        elif choice == "Q":
            print("\n  Goodbye.\n")
            sys.exit(0)
        else:
            print("  Invalid option.")

        input("\n  Press Enter to continue...")

if __name__ == "__main__":
    main()
