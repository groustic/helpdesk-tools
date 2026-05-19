# Helpdesk Tools

A collection of scripts for common help desk and IT support tasks. Built to automate repetitive workflows, reduce human error, and log all actions for accountability.

---

## AD-UserManagement.ps1

A PowerShell utility for managing Active Directory user accounts. Covers the most common help desk tasks in a single script with both an interactive menu and command-line argument support.

### Features

- Create new AD users with auto-generated SAMAccountName and UPN
- Reset passwords and force change at next logon
- Unlock locked-out accounts
- Disable and enable user accounts
- Pull a full summary of any user's account info
- Automatic logging of all actions to `AD-UserManagement.log`

### Requirements

- Windows with RSAT installed
- ActiveDirectory PowerShell module
- Sufficient AD permissions for the actions you need to perform

### Usage

**Interactive menu mode**
```powershell
.\AD-UserManagement.ps1
```

**Command-line mode**
```powershell
# Create a new user
.\AD-UserManagement.ps1 -Action CreateUser -FirstName "Jane" -LastName "Doe" -Department "IT" -OU "OU=Staff,DC=company,DC=com"

# Reset a password
.\AD-UserManagement.ps1 -Action ResetPassword -Username "jdoe"

# Unlock an account
.\AD-UserManagement.ps1 -Action UnlockAccount -Username "jdoe"

# Disable a user
.\AD-UserManagement.ps1 -Action DisableUser -Username "jdoe"

# Enable a user
.\AD-UserManagement.ps1 -Action EnableUser -Username "jdoe"

# Get user info
.\AD-UserManagement.ps1 -Action GetUserInfo -Username "jdoe"
```

### Logging

Every action is written to `AD-UserManagement.log` in the same directory as the script, with a timestamp and result status. This provides an audit trail for all account changes made through the tool.

---

## ticketing.py

A command-line help desk ticketing system built in Python. Stores tickets as JSON locally and supports the full lifecycle of a support ticket from creation to closure.

### Features

- Create tickets with title, description, priority, category, submitter, and assignee
- View all tickets in a color-coded table
- View full ticket detail including notes and update history
- Update ticket status, priority, assignee, and add notes
- Close tickets with an optional closing note
- Search tickets by any text field
- Filter tickets by status, priority, or category
- Stats and reporting view with breakdowns by status, priority, and category, plus a flag for any open critical tickets
- Automatic logging of all actions to `tickets.log`

### Requirements

- Python 3
- No external dependencies

### Usage

```bash
python ticketing.py
```

Tickets are stored in `tickets.json` in the same directory. The interactive menu walks through all available actions.

### Priority Levels

- Low
- Medium
- High
- Critical

### Categories

- Hardware
- Software
- Network
- Account
- Other

---

## Coming Soon

- Log parser for failed logins and suspicious auth events
- Vulnerability scanner for common misconfigurations
