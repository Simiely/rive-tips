#Requires -Version 5.1
<#
.SYNOPSIS
    Single-call wrapper for the Rive desktop app's local MCP server.

.DESCRIPTION
    Performs initialize -> notifications/initialized -> tools/call against
    http://127.0.0.1:9791/mcp and prints the text content of the result.
    Image content is written to -OutImage when provided.

    The Rive desktop app must be running; the port only exists while it is.

.PARAMETER Tool
    MCP tool name, e.g. session_info, capture_artboard, animation_editor.

.PARAMETER ArgsJson
    Tool arguments as a JSON object string. Defaults to {}.

.PARAMETER OutImage
    When the result contains image content, save it to this path.

.PARAMETER Endpoint
    MCP endpoint. Default http://127.0.0.1:9791/mcp

.EXAMPLE
    .\rive-mcp.ps1 -Tool session_info

.EXAMPLE
    .\rive-mcp.ps1 -Tool capture_artboard -ArgsJson '{"artboardId":"0-1","longEdge":1024}' -OutImage out.png
#>
param(
    [Parameter(Mandatory = $true)][string]$Tool,
    [string]$ArgsJson = '{}',
    [string]$OutImage = '',
    [string]$Endpoint = 'http://127.0.0.1:9791/mcp',
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Invoke-McpPost {
    param([string]$Body, [string]$SessionId)
    $headers = @{ 'Accept' = 'application/json, text/event-stream' }
    if ($SessionId) { $headers['Mcp-Session-Id'] = $SessionId }
    $resp = Invoke-WebRequest -Uri $Endpoint -Method Post `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($Body)) `
        -ContentType 'application/json' -Headers $headers `
        -TimeoutSec $TimeoutSec -UseBasicParsing
    return [System.Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
}

function ConvertFrom-SseText {
    param([string]$Text)
    $dataLines = ($Text -split "`r?`n") | Where-Object { $_ -match '^data:\s*' } |
        ForEach-Object { $_ -replace '^data:\s*', '' }
    $payload = if ($dataLines) { $dataLines -join '' } else { $Text }
    return ($payload | ConvertFrom-Json)
}

try {
    $initHeaders = @{ 'Accept' = 'application/json, text/event-stream' }
    $initBody = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"rive-mcp-ps","version":"1.0"}}}'
    $initResp = Invoke-WebRequest -Uri $Endpoint -Method Post `
        -Body $initBody -ContentType 'application/json' -Headers $initHeaders `
        -TimeoutSec 20 -UseBasicParsing
    $sessionId = $initResp.Headers['Mcp-Session-Id']

    Invoke-McpPost -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}' -SessionId $sessionId | Out-Null

    $call = @{
        jsonrpc = '2.0'
        id      = 2
        method  = 'tools/call'
        params  = @{ name = $Tool; arguments = ($ArgsJson | ConvertFrom-Json) }
    } | ConvertTo-Json -Depth 12 -Compress

    $result = ConvertFrom-SseText (Invoke-McpPost -Body $call -SessionId $sessionId)

    if ($result.error) {
        Write-Output ('MCP_ERROR: ' + ($result.error | ConvertTo-Json -Depth 6 -Compress))
        exit 1
    }

    foreach ($item in $result.result.content) {
        if ($item.type -eq 'image') {
            if ($OutImage) {
                [IO.File]::WriteAllBytes($OutImage, [Convert]::FromBase64String($item.data))
                Write-Output ("IMAGE_SAVED: " + $OutImage)
            } else {
                Write-Output ("IMAGE_BASE64_LEN: " + $item.data.Length)
            }
        } elseif ($item.type -eq 'text') {
            Write-Output $item.text
        } else {
            Write-Output ($item | ConvertTo-Json -Depth 6 -Compress)
        }
    }
} catch {
    Write-Output ('CONNECTION_ERROR: ' + $_.Exception.Message)
    Write-Output 'Check that the Rive desktop app is running and port 9791 is listening.'
    exit 1
}
