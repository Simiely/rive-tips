#Requires -Version 5.1
<#
.SYNOPSIS
    Import a .rev snapshot into the Rive file that is currently open.

.DESCRIPTION
    upload_rev with target=open_file requires a file with ZERO artboards.
    This script waits until the target file becomes the active file in the
    editor, deletes the artboards that are already there, then imports.

    Workflow:
      1. Export the source file to .rev (export_file, format=rev)
      2. Switch the editor to the target file (a click; the script polls)
      3. Run this script -- it clears and imports
      4. Delete the artboards you do not want (delete_objects)

    Note: export_file needs network access. A system proxy can break it with
    "HandshakeException: Connection terminated during handshake" -- turn the
    proxy off before exporting.

.PARAMETER TargetFileId
    fileId of the destination file (from session_info).

.PARAMETER RevPath
    Absolute path to the .rev on disk. Prefer an ASCII-only path.

.PARAMETER WaitSeconds
    How long to wait for the target file to become active.

.EXAMPLE
    .\rive-import.ps1 -TargetFileId 2682212 -RevPath D:\export\src.rev
#>
param(
    [Parameter(Mandatory = $true)][string]$TargetFileId,
    [Parameter(Mandatory = $true)][string]$RevPath,
    [int]$WaitSeconds = 600,
    [string]$Endpoint = 'http://127.0.0.1:9791/mcp'
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$script:SessionId = $null

function Invoke-McpPost {
    param([string]$Body)
    $headers = @{ 'Accept' = 'application/json, text/event-stream' }
    if ($script:SessionId) { $headers['Mcp-Session-Id'] = $script:SessionId }
    $resp = Invoke-WebRequest -Uri $Endpoint -Method Post `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($Body)) `
        -ContentType 'application/json' -Headers $headers `
        -TimeoutSec 300 -UseBasicParsing
    return [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
}

function ConvertFrom-SseText {
    param([string]$Text)
    $dataLines = ($Text -split "`r?`n") | Where-Object { $_ -match '^data:\s*' } |
        ForEach-Object { $_ -replace '^data:\s*', '' }
    $payload = if ($dataLines) { $dataLines -join '' } else { $Text }
    return ($payload | ConvertFrom-Json)
}

function Invoke-Tool {
    param([string]$Name, [hashtable]$Arguments)
    $body = @{
        jsonrpc = '2.0'; id = 9; method = 'tools/call'
        params  = @{ name = $Name; arguments = $Arguments }
    } | ConvertTo-Json -Depth 12 -Compress
    $res = ConvertFrom-SseText (Invoke-McpPost -Body $body)
    if ($res.error) { return @{ __error = ($res.error | ConvertTo-Json -Depth 6 -Compress) } }
    $text = ($res.result.content | Where-Object { $_.type -eq 'text' } | Select-Object -First 1).text
    if ($res.result.isError) { return @{ __error = $text } }
    if (-not $text) { return @{} }
    try { return ($text | ConvertFrom-Json) } catch { return @{ raw = $text } }
}

if (-not (Test-Path -LiteralPath $RevPath)) {
    Write-Output ("ERROR: .rev not found: " + $RevPath)
    exit 1
}

$headers = @{ 'Accept' = 'application/json, text/event-stream' }
$initBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"rive-import","version":"1.0"}}}'
$initResp = Invoke-WebRequest -Uri $Endpoint -Method Post -Body $initBody `
    -ContentType 'application/json' -Headers $headers -TimeoutSec 20 -UseBasicParsing
$script:SessionId = $initResp.Headers['Mcp-Session-Id']
Invoke-McpPost -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' | Out-Null

$deadline = (Get-Date).AddSeconds($WaitSeconds)
$activeId = $null
while ((Get-Date) -lt $deadline) {
    $info = Invoke-Tool 'session_info' @{}
    $activeId = $info.activeFileId
    if ("$activeId" -eq $TargetFileId) { break }
    Start-Sleep -Seconds 2
}
if ("$activeId" -ne $TargetFileId) {
    Write-Output ("TIMEOUT: active file is " + $activeId + ", expected " + $TargetFileId)
    exit 2
}
Write-Output ("ACTIVE_OK fileId=" + $activeId)

$artboards = @((Invoke-Tool 'open_file_editor' @{ command = 'listArtboards' }).artboards)
Write-Output ("BEFORE_COUNT=" + $artboards.Count)

# Delete everything except the first, then try importing. If the import still
# complains about content, delete the last one and retry.
$toDelete = @($artboards | Select-Object -Skip 1 | ForEach-Object { $_.id })
if ($toDelete.Count -gt 0) {
    $result = Invoke-Tool 'delete_objects' @{ objectIds = $toDelete }
    Write-Output ("DELETE_EXTRA: " + ($result | ConvertTo-Json -Depth 5 -Compress))
}

$import = Invoke-Tool 'upload_rev' @{ file = $RevPath; target = 'open_file' }
Write-Output ("IMPORT: " + ($import | ConvertTo-Json -Depth 5 -Compress))

$errorText = "$($import.__error) $($import.error)"
if ($errorText -match 'empty|existing content') {
    Write-Output 'RETRY_AFTER_CLEAR'
    $remaining = @((Invoke-Tool 'open_file_editor' @{ command = 'listArtboards' }).artboards)
    foreach ($item in $remaining) {
        $result = Invoke-Tool 'delete_objects' @{ objectIds = @($item.id) }
        Write-Output ("  CLEAR " + $item.id + " -> " + ($result | ConvertTo-Json -Depth 4 -Compress))
    }
    $import = Invoke-Tool 'upload_rev' @{ file = $RevPath; target = 'open_file' }
    Write-Output ("IMPORT_RETRY: " + ($import | ConvertTo-Json -Depth 5 -Compress))
}

$after = @((Invoke-Tool 'open_file_editor' @{ command = 'listArtboards' }).artboards)
Write-Output ("AFTER_COUNT=" + $after.Count)
$after | ForEach-Object { Write-Output ("  AFTER id=" + $_.id + " name=" + $_.name) }
