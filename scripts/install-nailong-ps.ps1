$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$cliPath = Join-Path $repoRoot "eleven-rag\nailong_cli.py"
if (-not (Test-Path $cliPath)) {
  throw "nailong_cli.py not found: $cliPath"
}

$profilePath = $PROFILE
$profileDir = Split-Path -Parent $profilePath
if (-not (Test-Path $profileDir)) {
  New-Item -ItemType Directory -Force $profileDir | Out-Null
}
if (-not (Test-Path $profilePath)) {
  New-Item -ItemType File -Force $profilePath | Out-Null
}

$triggerName = ([char]0x5976) + ([char]0x9F99) # 奶龙
$functionBlock = @"
function nailong {
  param([Parameter(ValueFromRemainingArguments = `$true)][string[]]`$Args)
  uv run --python 3.12 python "$cliPath" (`$Args -join " ")
}
Set-Alias -Name $triggerName -Value nailong -Scope Global
"@

$content = Get-Content $profilePath -Raw
# Cleanup previous mojibake function name if it exists.
$content = $content -replace "(?ms)function\s+濂堕緳\s*\{.*?\}\s*", ""
$content = $content -replace "(?ms)function\s+nailong\s*\{.*?\}\s*", ""
$content = $content -replace "(?m)^\s*Set-Alias\s+-Name\s+.*?-Value\s+nailong.*$\r?\n?", ""

$updated = ($content.TrimEnd() + "`r`n`r`n" + $functionBlock + "`r`n")
Set-Content -Path $profilePath -Value $updated -Encoding UTF8
Write-Output "Installed command alias '$triggerName' into profile: $profilePath"

Write-Output "Done. Reopen terminal or run: . `$PROFILE"
Write-Output "Usage: 奶龙 这份文档讲了什么？"
