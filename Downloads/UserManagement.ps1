#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Local Windows User Account Management Tool

.DESCRIPTION
    A help desk utility for managing local Windows user accounts.
    Supports both interactive menu mode and command-line argument mode.

.PARAMETER Action
    The action to perform: Create, Reset, Unlock, Disable, Enable, List, Info

.PARAMETER Username
    The target username for the action.

.PARAMETER Password
    The new password (for Create and Reset actions). If omitted, you will be prompted.

.PARAMETER FullName
    Full name of the user (for Create action).

.PARAMETER Description
    Account description (for Create action).

.EXAMPLE
    # Interactive mode
    .\UserManagement.ps1

.EXAMPLE
    # Create a user
    .\UserManagement.ps1 -Action Create -Username jdoe -FullName "John Doe" -Description "Help Desk"

.EXAMPLE
    # Reset a password
    .\UserManagement.ps1 -Action Reset -Username jdoe

.EXAMPLE
    # Unlock an account
    .\UserManagement.ps1 -Action Unlock -Username jdoe

.EXAMPLE
    # Disable an account
    .\UserManagement.ps1 -Action Disable -Username jdoe

.EXAMPLE
    # List all local users
    .\UserManagement.ps1 -Action List

.NOTES
    Author: Gabby Roustic
    Requires administrator privileges.
    All actions are logged to UserManagement.log in the script directory.
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $false)]
    [ValidateSet("Create", "Reset", "Unlock", "Disable", "Enable", "List", "Info")]
    [string]$Action,

    [Parameter(Mandatory = $false)]
    [string]$Username,

    [Parameter(Mandatory = $false)]
    [string]$Password,

    [Parameter(Mandatory = $false)]
    [string]$FullName,

    [Parameter(Mandatory = $false)]
    [string]$Description
)

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

$LogFile = Join-Path $PSScriptRoot "UserManagement.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogFile -Value $entry
    switch ($Level) {
        "ERROR"   { Write-Host $entry -ForegroundColor Red }
        "WARN"    { Write-Host $entry -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $entry -ForegroundColor Green }
        default   { Write-Host $entry }
    }
}

# ─────────────────────────────────────────────
# Helper: Prompt for secure password
# ─────────────────────────────────────────────

function Get-SecurePasswordFromInput {
    param([string]$PromptText = "Enter new password")
    $secure = Read-Host -Prompt $PromptText -AsSecureString
    return $secure
}

function ConvertTo-SecureStringFromPlain {
    param([string]$PlainText)
    return ConvertTo-SecureString -String $PlainText -AsPlainText -Force
}

# ─────────────────────────────────────────────
# Core Functions
# ─────────────────────────────────────────────

function New-LocalUserAccount {
    param(
        [string]$User,
        [string]$Plain,
        [string]$Name = "",
        [string]$Desc = ""
    )

    if (Get-LocalUser -Name $User -ErrorAction SilentlyContinue) {
        Write-Log "User '$User' already exists." "WARN"
        return
    }

    try {
        $secure = if ($Plain) { ConvertTo-SecureStringFromPlain $Plain } else { Get-SecurePasswordFromInput "Password for $User" }
        $params = @{
            Name                 = $User
            Password             = $secure
            PasswordNeverExpires = $false
            AccountNeverExpires  = $true
        }
        if ($Name) { $params["FullName"] = $Name }
        if ($Desc) { $params["Description"] = $Desc }

        New-LocalUser @params | Out-Null
        Write-Log "Created user '$User' (FullName: '$Name')." "SUCCESS"
    }
    catch {
        Write-Log "Failed to create user '$User': $_" "ERROR"
    }
}

function Reset-LocalUserPassword {
    param([string]$User, [string]$Plain)

    if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
        Write-Log "User '$User' not found." "ERROR"
        return
    }

    try {
        $secure = if ($Plain) { ConvertTo-SecureStringFromPlain $Plain } else { Get-SecurePasswordFromInput "New password for $User" }
        Set-LocalUser -Name $User -Password $secure
        Write-Log "Password reset for '$User'." "SUCCESS"
    }
    catch {
        Write-Log "Failed to reset password for '$User': $_" "ERROR"
    }
}

function Unlock-LocalUserAccount {
    param([string]$User)

    $account = Get-LocalUser -Name $User -ErrorAction SilentlyContinue
    if (-not $account) {
        Write-Log "User '$User' not found." "ERROR"
        return
    }

    try {
        # Local accounts don't have a true lockout like AD, but we re-enable
        # and clear any disabled state that mimics a lockout in local policy.
        Enable-LocalUser -Name $User
        Write-Log "Account '$User' unlocked/enabled successfully." "SUCCESS"
    }
    catch {
        Write-Log "Failed to unlock '$User': $_" "ERROR"
    }
}

function Disable-LocalUserAccount {
    param([string]$User)

    if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
        Write-Log "User '$User' not found." "ERROR"
        return
    }

    try {
        Disable-LocalUser -Name $User
        Write-Log "Account '$User' disabled." "SUCCESS"
    }
    catch {
        Write-Log "Failed to disable '$User': $_" "ERROR"
    }
}

function Enable-LocalUserAccount {
    param([string]$User)

    if (-not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
        Write-Log "User '$User' not found." "ERROR"
        return
    }

    try {
        Enable-LocalUser -Name $User
        Write-Log "Account '$User' enabled." "SUCCESS"
    }
    catch {
        Write-Log "Failed to enable '$User': $_" "ERROR"
    }
}

function Get-AllLocalUsers {
    Write-Host "`n--- Local User Accounts ---" -ForegroundColor Cyan
    Get-LocalUser | Sort-Object Name | ForEach-Object {
        $status = if ($_.Enabled) { "Enabled" } else { "Disabled" }
        $color  = if ($_.Enabled) { "Green" } else { "Red" }
        Write-Host ("{0,-20} {1,-10} Last Logon: {2}" -f $_.Name, $status, $_.LastLogon) -ForegroundColor $color
    }
    Write-Host ""
    Write-Log "Listed all local users."
}

function Get-LocalUserInfo {
    param([string]$User)

    $account = Get-LocalUser -Name $User -ErrorAction SilentlyContinue
    if (-not $account) {
        Write-Log "User '$User' not found." "ERROR"
        return
    }

    Write-Host "`n--- Account Info: $User ---" -ForegroundColor Cyan
    $account | Format-List Name, FullName, Description, Enabled, LastLogon, PasswordLastSet, PasswordExpires, AccountExpires
    Write-Log "Viewed info for '$User'."
}

# ─────────────────────────────────────────────
# Interactive Menu
# ─────────────────────────────────────────────

function Show-Menu {
    Write-Host "`n=====================================" -ForegroundColor Cyan
    Write-Host "   Local User Management Tool" -ForegroundColor Cyan
    Write-Host "=====================================" -ForegroundColor Cyan
    Write-Host " 1. Create user"
    Write-Host " 2. Reset password"
    Write-Host " 3. Unlock / Enable account"
    Write-Host " 4. Disable account"
    Write-Host " 5. Enable account"
    Write-Host " 6. List all users"
    Write-Host " 7. View user info"
    Write-Host " 8. Exit"
    Write-Host "-------------------------------------"
}

function Start-InteractiveMode {
    do {
        Show-Menu
        $choice = Read-Host "Select an option"

        switch ($choice) {
            "1" {
                $u = Read-Host "Username"
                $f = Read-Host "Full name (optional)"
                $d = Read-Host "Description (optional)"
                New-LocalUserAccount -User $u -Name $f -Desc $d
            }
            "2" {
                $u = Read-Host "Username"
                Reset-LocalUserPassword -User $u
            }
            "3" {
                $u = Read-Host "Username"
                Unlock-LocalUserAccount -User $u
            }
            "4" {
                $u = Read-Host "Username"
                Disable-LocalUserAccount -User $u
            }
            "5" {
                $u = Read-Host "Username"
                Enable-LocalUserAccount -User $u
            }
            "6" {
                Get-AllLocalUsers
            }
            "7" {
                $u = Read-Host "Username"
                Get-LocalUserInfo -User $u
            }
            "8" {
                Write-Host "Exiting." -ForegroundColor Yellow
                break
            }
            default {
                Write-Host "Invalid option. Try again." -ForegroundColor Red
            }
        }
    } while ($choice -ne "8")
}

# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

Write-Log "Session started by $env:USERNAME on $env:COMPUTERNAME"

if (-not $Action) {
    # No arguments provided, launch interactive menu
    Start-InteractiveMode
}
else {
    # Command-line mode
    switch ($Action) {
        "Create"  { New-LocalUserAccount -User $Username -Plain $Password -Name $FullName -Desc $Description }
        "Reset"   { Reset-LocalUserPassword -User $Username -Plain $Password }
        "Unlock"  { Unlock-LocalUserAccount -User $Username }
        "Disable" { Disable-LocalUserAccount -User $Username }
        "Enable"  { Enable-LocalUserAccount -User $Username }
        "List"    { Get-AllLocalUsers }
        "Info"    { Get-LocalUserInfo -User $Username }
    }
}

Write-Log "Session ended."
