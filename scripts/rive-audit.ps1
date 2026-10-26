#Requires -Version 5.1
<#
.SYNOPSIS
    Collect a structural fingerprint for every artboard in the active Rive file.

.DESCRIPTION
    For each artboard: focus it, then read its state machines and linear
    animations, and compute an 8-part fingerprint:

        stateMachines / layers / states / animationStates / transitions /
        inputs / listeners / linearAnimations

    Use it before and after a move or rename to prove nothing changed.
    Note: animation_editor only works on the ACTIVE artboard, so this script
    focuses each artboard in turn (the editor view will jump around).

.PARAMETER OutFile
    TSV output path.

.PARAMETER KeepFocus
    When set, leaves the last artboard focused. Default restores the
    originally active artboard.

.EXAMPLE
    .\rive-audit.ps1 -OutFile audit.tsv
#>
param(
    [string]$OutFile = 'rive-audit.tsv',
    [string]$Endpoint = 'http://127.0.0.1:9791/mcp',
    [switch]$KeepFocus
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
        -TimeoutSec 120 -UseBasicParsing
    return [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
}

function ConvertFrom-SseText {
    param([string]$Text)
    $dataLines = ($Text -split "`r?`n") | Where-Object { $_ -match '^data:\s*' } |
        ForEach-Object { $_ -replace '^data:\s*', '' }
    $payload = if ($dataLines) { $dataLines -join '' } else { $Text }
    return ($payload | ConvertFrom-Json)
}

function Connect-Mcp {
    $headers = @{ 'Accept' = 'application/json, text/event-stream' }
    $body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"rive-audit","version":"1.0"}}}'
    $resp = Invoke-WebRequest -Uri $Endpoint -Method Post -Body $body `
        -ContentType 'application/json' -Headers $headers -TimeoutSec 20 -UseBasicParsing
    $script:SessionId = $resp.Headers['Mcp-Session-Id']
    Invoke-McpPost -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' | Out-Null
}

function Invoke-Tool {
    param([string]$Name, [hashtable]$Arguments)
    $body = @{
        jsonrpc = '2.0'; id = 9; method = 'tools/call'
        params  = @{ name = $Name; arguments = $Arguments }
    } | ConvertTo-Json -Depth 12 -Compress
    $res = ConvertFrom-SseText (Invoke-McpPost -Body $body)
    if ($res.error) { throw ('MCP error: ' + ($res.error | ConvertTo-Json -Depth 5 -Compress)) }
    $text = ($res.result.content | Where-Object { $_.type -eq 'text' } | Select-Object -First 1).text
    if (-not $text) { return $null }
    try { return ($text | ConvertFrom-Json) } catch { return @{ raw = $text } }
}

Connect-Mcp

$artboards = @((Invoke-Tool 'open_file_editor' @{ command = 'listArtboards' }).artboards)
$originallyActive = ($artboards | Where-Object { $_.isActive } | Select-Object -First 1)
Write-Output ("ARTBOARDS=" + $artboards.Count)

$rows = New-Object System.Collections.ArrayList
$index = 0

foreach ($ab in $artboards) {
    $index++
    try { Invoke-Tool 'open_file_editor' @{ command = 'focusArtboard'; data = @{ artboardId = $ab.id } } | Out-Null } catch { }
    Start-Sleep -Milliseconds 80

    $stateMachines = @()
    try { $stateMachines = @((Invoke-Tool 'animation_editor' @{ command = 'listStateMachines' }).stateMachines) } catch { }
    $animations = @()
    try { $animations = @((Invoke-Tool 'animation_editor' @{ command = 'listLinearAnimations' }).linearAnimations) } catch { }

    $layers = 0; $states = 0; $animationStates = 0; $transitions = 0; $inputs = 0; $listeners = 0
    foreach ($sm in $stateMachines) {
        $q = $null
        try { $q = Invoke-Tool 'animation_editor' @{ command = 'queryStateMachine'; data = @{ stateMachineId = $sm.id } } } catch { }
        if (-not $q) { continue }
        $inputs += @($q.inputs).Count
        $listeners += @($q.listeners).Count
        foreach ($layer in $q.layers) {
            $layers++
            $states += @($layer.states).Count
            $animationStates += @(@($layer.states) | Where-Object { $_.type -eq 'animation' }).Count
            $transitions += @($layer.transitions).Count
        }
    }

    $smNames = (@($stateMachines | ForEach-Object { $_.name }) -join '|')
    $animNames = (@($animations | ForEach-Object { $_.name }) -join '|')
    $durations = (@($animations | ForEach-Object { $_.duration }) -join '|')

    $null = $rows.Add([pscustomobject]@{
            name             = $ab.name
            id               = $ab.id
            width            = [int]$ab.width
            height           = [int]$ab.height
            smCount          = @($stateMachines).Count
            smNames          = $smNames
            layers           = $layers
            states           = $states
            animationStates  = $animationStates
            transitions      = $transitions
            inputs           = $inputs
            listeners        = $listeners
            animCount        = @($animations).Count
            animNames        = $animNames
            durations        = $durations
            fingerprint      = "$(@($stateMachines).Count)/$layers/$states/$animationStates/$transitions/$inputs/$listeners/$(@($animations).Count)"
            hasTrailingSpace = ($ab.name -ne $ab.name.TrimEnd())
            hasDefaultName   = ($smNames -match 'State Machine \d' -or $animNames -match 'Timeline')
        })

    Write-Output ("[" + $index + "/" + $artboards.Count + "] " + $ab.name)
}

if (-not $KeepFocus -and $originallyActive) {
    try { Invoke-Tool 'open_file_editor' @{ command = 'focusArtboard'; data = @{ artboardId = $originallyActive.id } } | Out-Null } catch { }
}

$rows | Export-Csv -Path $OutFile -NoTypeInformation -Delimiter "`t" -Encoding UTF8
Write-Output ("WROTE: " + $OutFile)
