# Wrapper script to run the Telegram signal copier bot on Windows
# This script prevents sleep and runs the bot

param(
    [switch]$NoKeepAwake  # Skip keep-awake if running as a service
)

$ErrorActionPreference = "Stop"

# Change to script directory
Set-Location $PSScriptRoot

# Load environment variables from .env file
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match "^\s*([^#][^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove surrounding quotes if present
            $value = $value -replace '^["'']|["'']$', ''
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

# Create logs directory if needed
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Keep-awake function using Windows API
function Set-KeepAwake {
    param([bool]$Enable)

    $code = @'
    [DllImport("kernel32.dll", CharSet = CharSet.Auto, SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
'@

    if (-not ([System.Management.Automation.PSTypeName]'Win32.KeepAwake').Type) {
        Add-Type -MemberDefinition $code -Name KeepAwake -Namespace Win32
    }

    # Define flags as proper unsigned integers
    $ES_CONTINUOUS = [uint32]2147483648        # 0x80000000
    $ES_SYSTEM_REQUIRED = [uint32]1            # 0x00000001
    $ES_DISPLAY_REQUIRED = [uint32]2           # 0x00000002

    if ($Enable) {
        # ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED
        $flags = $ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED -bor $ES_DISPLAY_REQUIRED
        [Win32.KeepAwake]::SetThreadExecutionState($flags) | Out-Null
        Write-Host "Keep-awake enabled - system will not sleep" -ForegroundColor Green
    } else {
        # ES_CONTINUOUS - reset to normal
        [Win32.KeepAwake]::SetThreadExecutionState($ES_CONTINUOUS) | Out-Null
        Write-Host "Keep-awake disabled - normal power settings restored" -ForegroundColor Yellow
    }
}

# Enable keep-awake
if (-not $NoKeepAwake) {
    Set-KeepAwake -Enable $true
}

try {
    Write-Host "Starting bot at $(Get-Date)" -ForegroundColor Cyan
    Write-Host "Using Python: $(uv run which python)" -ForegroundColor Cyan
    Write-Host ""

    # Run the bot
    uv run python -m tania_signal_copier.bot

} finally {
    # Always restore normal power settings
    if (-not $NoKeepAwake) {
        Set-KeepAwake -Enable $false
    }
    Write-Host ""
    Write-Host "Bot exited at $(Get-Date)" -ForegroundColor Cyan
}
