# Local User Management Tool

A PowerShell help desk utility for managing local Windows user accounts. Supports both an interactive terminal menu and command-line arguments for scripting and automation.

## Features

- Create new local user accounts
- Reset user passwords
- Unlock and enable disabled accounts
- Disable accounts (offboarding)
- List all local users with status and last logon
- View detailed account information
- Automatic logging of all actions to `UserManagement.log`

## Requirements

- Windows PowerShell 5.1 or later
- Administrator privileges

## Usage

### Interactive Mode

Launch without any arguments to get a numbered menu:

```powershell
.\UserManagement.ps1
```

### Command-Line Mode

```powershell
# Create a user
.\UserManagement.ps1 -Action Create -Username jdoe -FullName "John Doe" -Description "Finance Dept"

# Reset a password (will prompt securely if no password provided)
.\UserManagement.ps1 -Action Reset -Username jdoe

# Unlock / re-enable an account
.\UserManagement.ps1 -Action Unlock -Username jdoe

# Disable an account
.\UserManagement.ps1 -Action Disable -Username jdoe

# Enable an account
.\UserManagement.ps1 -Action Enable -Username jdoe

# List all local users
.\UserManagement.ps1 -Action List

# View account details
.\UserManagement.ps1 -Action Info -Username jdoe
```

## Logging

Every action is automatically written to `UserManagement.log` in the same directory as the script, including the timestamp, acting user, and machine name. This supports auditing and accountability in help desk environments.

## Notes

This tool targets local Windows accounts. For Active Directory environments, actions like unlocking accounts would use `Unlock-ADAccount` from the RSAT ActiveDirectory module instead. The architecture of this script is designed to be extended for AD with minimal changes.

## Author

Gabby Roustic — [github.com/groustic](https://github.com/groustic)
