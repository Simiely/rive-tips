#Requires -Version 5.1
<#
.SYNOPSIS
    Sync rive-tips docs into the rive-ops Agent Skill snapshot.

.DESCRIPTION
    skills/rive-ops/references/ are SNAPSHOTS of docs/. Run this after any
    docs change so the skill never drifts from the repository.

    Mapping (docs/ -> skills/rive-ops/references/):
        速查表.md              -> pitfalls.md
        AI素材导入链路.md       -> asset-import.md
        导出规则与交付验收.md    -> delivery.md
        跨文件搬运画板.md       -> transfer.md
        MCP接入与联调.md        -> mcp.md
        性能诊断与资产瘦身.md    -> performance.md
    Plus: tools/runtime-check/index.html -> assets/runtime-check-index.html

    -Install also refreshes the installed skill at
    $env:USERPROFILE\.workbuddy\skills\rive-ops (user scope).

.PARAMETER Install
    Additionally copy skills/rive-ops to the user skill directory.

.EXAMPLE
    .\sync-skill.ps1 -Install
#>
param([switch]$Install)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$skill = Join-Path $repo 'skills\rive-ops'

if (-not (Test-Path (Join-Path $skill 'SKILL.md'))) {
    Write-Output 'ERROR: skills/rive-ops/SKILL.md not found; run from the rive-tips repository.'
    exit 1
}

$map = [ordered]@{
    '速查表.md'            = 'pitfalls.md'
    'AI素材导入链路.md'     = 'asset-import.md'
    '导出规则与交付验收.md'  = 'delivery.md'
    '跨文件搬运画板.md'      = 'transfer.md'
    'MCP接入与联调.md'      = 'mcp.md'
    '性能诊断与资产瘦身.md'  = 'performance.md'
}

$done = 0
foreach ($k in $map.Keys) {
    $src = Join-Path $repo ("docs\" + $k)
    $dst = Join-Path $skill ("references\" + $map[$k])
    if (-not (Test-Path $src)) { Write-Output ("SKIP missing source: " + $k); continue }
    Copy-Item $src $dst -Force
    $done++
    Write-Output ("SYNCED docs/" + $k + " -> references/" + $map[$k])
}

$idx = Join-Path $repo 'tools\runtime-check\index.html'
if (Test-Path $idx) {
    Copy-Item $idx (Join-Path $skill 'assets\runtime-check-index.html') -Force
    Write-Output 'SYNCED tools/runtime-check/index.html -> assets/runtime-check-index.html'
}

Write-Output ("DONE " + $done + " docs + 1 asset. Skill snapshot is up to date.")

if ($Install) {
    $target = Join-Path $env:USERPROFILE '.workbuddy\skills\rive-ops'
    if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }
    Copy-Item (Join-Path $skill '*') $target -Recurse -Force
    Write-Output ('INSTALLED -> ' + $target)
}
