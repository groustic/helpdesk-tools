#Requires -Module ActiveDirectory

<#
.SYNOPSIS
    Active Directory User Management Tool

.DESCRIPTION
    A help desk utility for common AD user management tasks.
    Supports both interactive menu mode and command-line argument mode.

.PARAMETER Action
    The action to perform: CreateUser, ResetPassword, UnlockAccount, DisableUser, EnableUser, GetUserInfo

.PARAMETER Username
    The SAMAccountName of the target user.

.PARAMETER FirstName
    First name of the new user (CreateUser only).

.PARAMETER LastName
    Last name of the new user (CreateUser only).

.PARAMETER Department
    Department of the new user (CreateUser only).

.PARAMETER OU
    Distinguished Name of the OU to place the new user in (CreateUser only).

.EXAMPLE
    # Interactive mode
    .\AD-UserManagement.ps1

.EXAMPLE
    # Create a new user
    .\AD-UserManagement.ps1 -Action CreateUser -FirstName "Jane" -LastName "Doe" -Department "IT" -OU "OU=Staff,DC=company,DC=com"

.EXAMPLE
    # Reset a user's password
    .\AD-UserManagement.ps1 -Action ResetPassword -Username "jdoe"

.EXAMPLE
    # Unlock an account
    .\AD-UserManagement.ps1 -Action UnlockAccount -Username "jdoe"

.EXAMPLE
    # Disable a user
    .\AD-UserManagement.ps1 -Action DisableUser -Username "jdoe"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory=$false)]
    [ValidateSet("CreateUser", "ResetPassword", "UnlockAccount", "DisableUser", "EnableUser", "GetUserInfo")]
    [string]$Action,

    [Parameter(Mandatory=$false)]
    [string]$Username,

    [Parameter(Mandatory=$false)]
    [string]$FirstName,

    [Parameter(Mandatory=$false)]
    [string]$LastName,

    [Parameter(Mandatory=$false)]
    [string]$Department,

    [Parameter(Mandatory=$false)]
    [string]$OU
)

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

$LogPath = "$PSScriptRoot\AD-UserManagement.log"

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $entry = "[$timestamp] [$Level] $Message"
    Add-Content -Path $LogPath -Value $entry
    switch ($Level) {
        "ERROR"   { Write-Host $entry -ForegroundColor Red }
        "WARNING" { Write-Host $entry -ForegroundColor Yellow }
        "SUCCESS" { Write-Host $entry -ForegroundColor Green }
        default   { Write-Host $entry }
    }
}

# ─────────────────────────────────────────────
# HELPER: CHECK MODULE
# ─────────────────────────────────────────────

function Assert-ADModule {
    if (-not (Get-Module -Name ActiveDirectory -ErrorAction SilentlyContinue)) {
        try {
            Import-Module ActiveDirectory -ErrorAction Stop
        } catch {
            Write-Log "ActiveDirectory module not found. Install RSAT tools." "ERROR"
            exit 1
        }
    }
}

# ─────────────────────────────────────────────
# HELPER: GET USER (with error handling)
# ─────────────────────────────────────────────

function Get-ADUserSafe {
    param([string]$Sam)
    try {
        $user = Get-ADUser -Identity $Sam -Properties * -ErrorAction Stop
        return $user
    } catch {
        Write-Log "User '$Sam' not found in Active Directory." "ERROR"
        return $null
    }
}

# ─────────────────────────────────────────────
# ACTIONS
# ─────────────────────────────────────────────

function Invoke-CreateUser {
    param(
        [string]$First,
        [string]$Last,
        [string]$Dept,
        [string]$OUPath
    )

    $sam = ($First[0] + $Last).ToLower() -replace '\s', ''
    $upnDomain = (Get-ADDomain).DNSRoot
    $upn = "$sam@$upnDomain"
    $displayName = "$First $Last"

    # Check if user already exists
    if (Get-ADUser -Filter { SamAccountName -eq $sam } -ErrorAction SilentlyContinue) {
        Write-Log "User '$sam' already exists. Aborting." "WARNING"
        return
    }

    $password = Read-Host "Set initial password for $sam" -AsSecureString

    $params = @{
        SamAccountName        = $sam
        UserPrincipalName     = $upn
        Name                  = $displayName
        GivenName             = $First
        Surname               = $Last
        DisplayName           = $displayName
        Department            = $Dept
        AccountPassword       = $password
        Enabled               = $true
        ChangePasswordAtLogon = $true
        Path                  = $OUPath
    }

    try {
        New-ADUser @params -ErrorAction Stop
        Write-Log "Created user '$sam' ($displayName) in OU: $OUPath" "SUCCESS"
        Write-Host ""
        Write-Host "  Username : $sam"
        Write-Host "  UPN      : $upn"
        Write-Host "  Dept     : $Dept"
        Write-Host "  OU       : $OUPath"
    } catch {
        Write-Log "Failed to create user '$sam': $_" "ERROR"
    }
}

function Invoke-ResetPassword {
    param([string]$Sam)
    $user = Get-ADUserSafe -Sam $Sam
    if (-not $user) { return }

    $newPassword = Read-Host "Enter new password for $Sam" -AsSecureString
    try {
        Set-ADAccountPassword -Identity $Sam -NewPassword $newPassword -Reset -ErrorAction Stop
        Set-ADUser -Identity $Sam -ChangePasswordAtLogon $true -ErrorAction Stop
        Write-Log "Password reset for '$Sam'. User must change password at next logon." "SUCCESS"
    } catch {
        Write-Log "Failed to reset password for '$Sam': $_" "ERROR"
    }
}

function Invoke-UnlockAccount {
    param([string]$Sam)
    $user = Get-ADUserSafe -Sam $Sam
    if (-not $user) { return }

    if (-not $user.LockedOut) {
        Write-Log "Account '$Sam' is not currently locked." "WARNING"
        return
    }

    try {
        Unlock-ADAccount -Identity $Sam -ErrorAction Stop
        Write-Log "Account '$Sam' has been unlocked." "SUCCESS"
    } catch {
        Write-Log "Failed to unlock '$Sam': $_" "ERROR"
    }
}

function Invoke-DisableUser {
    param([string]$Sam)
    $user = Get-ADUserSafe -Sam $Sam
    if (-not $user) { return }

    if (-not $user.Enabled) {
        Write-Log "Account '$Sam' is already disabled." "WARNING"
        return
    }

    try {
        Disable-ADAccount -Identity $Sam -ErrorAction Stop
        Write-Log "Account '$Sam' has been disabled." "SUCCESS"
    } catch {
        Write-Log "Failed to disable '$Sam': $_" "ERROR"
    }
}

function Invoke-EnableUser {
    param([string]$Sam)
    $user = Get-ADUserSafe -Sam $Sam
    if (-not $user) { return }

    if ($user.Enabled) {
        Write-Log "Account '$Sam' is already enabled." "WARNING"
        return
    }

    try {
        Enable-ADAccount -Identity $Sam -ErrorAction Stop
        Write-Log "Account '$Sam' has been enabled." "SUCCESS"
    } catch {
        Write-Log "Failed to enable '$Sam': $_" "ERROR"
    }
}

function Invoke-GetUserInfo {
    param([string]$Sam)
    $user = Get-ADUserSafe -Sam $Sam
    if (-not $user) { return }

    Write-Host ""
    Write-Host "─────────────────────────────────"
    Write-Host "  User Info: $Sam"
    Write-Host "─────────────────────────────────"
    Write-Host "  Display Name   : $($user.DisplayName)"
    Write-Host "  UPN            : $($user.UserPrincipalName)"
    Write-Host "  Department     : $($user.Department)"
    Write-Host "  Enabled        : $($user.Enabled)"
    Write-Host "  Locked Out     : $($user.LockedOut)"
    Write-Host "  Last Logon     : $($user.LastLogonDate)"
    Write-Host "  Password Last  : $($user.PasswordLastSet)"
    Write-Host "  Pwd Expires    : $($user.PasswordNeverExpires)"
    Write-Host "  OU             : $($user.DistinguishedName)"
    Write-Host "─────────────────────────────────"
    Write-Host ""

    Write-Log "Retrieved info for '$Sam'." "INFO"
}

# ─────────────────────────────────────────────
# INTERACTIVE MENU
# ─────────────────────────────────────────────

function Show-Menu {
    Clear-Host
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "   AD User Management Tool" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  1. Create New User"
    Write-Host "  2. Reset Password"
    Write-Host "  3. Unlock Account"
    Write-Host "  4. Disable User"
    Write-Host "  5. Enable User"
    Write-Host "  6. Get User Info"
    Write-Host "  Q. Quit"
    Write-Host "----------------------------------------"
}

function Start-InteractiveMode {
    do {
        Show-Menu
        $choice = Read-Host "Select an option"

        switch ($choice.ToUpper()) {
            "1" {
                $f  = Read-Host "First Name"
                $l  = Read-Host "Last Name"
                $d  = Read-Host "Department"
                $ou = Read-Host "OU (e.g. OU=Staff,DC=company,DC=com)"
                Invoke-CreateUser -First $f -Last $l -Dept $d -OUPath $ou
            }
            "2" {
                $u = Read-Host "Username (SAMAccountName)"
                Invoke-ResetPassword -Sam $u
            }
            "3" {
                $u = Read-Host "Username (SAMAccountName)"
                Invoke-UnlockAccount -Sam $u
            }
            "4" {
                $u = Read-Host "Username (SAMAccountName)"
                Invoke-DisableUser -Sam $u
            }
            "5" {
                $u = Read-Host "Username (SAMAccountName)"
                Invoke-EnableUser -Sam $u
            }
            "6" {
                $u = Read-Host "Username (SAMAccountName)"
                Invoke-GetUserInfo -Sam $u
            }
            "Q" { Write-Host "Exiting." -ForegroundColor Cyan }
            default { Write-Host "Invalid option. Try again." -ForegroundColor Yellow }
        }

        if ($choice.ToUpper() -ne "Q") {
            Read-Host "`nPress Enter to continue"
        }

    } while ($choice.ToUpper() -ne "Q")
}

# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────

Assert-ADModule

if (-not $Action) {
    Start-InteractiveMode
} else {
    switch ($Action) {
        "CreateUser"    { Invoke-CreateUser -First $FirstName -Last $LastName -Dept $Department -OUPath $OU }
        "ResetPassword" { Invoke-ResetPassword -Sam $Username }
        "UnlockAccount" { Invoke-UnlockAccount -Sam $Username }
        "DisableUser"   { Invoke-DisableUser -Sam $Username }
        "EnableUser"    { Invoke-EnableUser -Sam $Username }
        "GetUserInfo"   { Invoke-GetUserInfo -Sam $Username }
    }
}
