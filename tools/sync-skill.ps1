#Requires -Version 5.1
<#
.SYNOPSIS
    Sync rive-tips docs into the rive-ops Agent Skill snapshot.

.DESCRIPTION
    skills/rive-ops/references/ are SNAPSHOTS of docs/. Run this after any
    docs change so the skill never drifts from the repository.

    Relative links that point at docs/<name>.md are REWRITTEN to the snapshot's
    English name while copying. The installed skill has no docs/ folder, so
    without this step every "see also" link inside references/ is dead.

    Mapping (docs/ -> skills/rive-ops/references/):
        速查表.md               -> pitfalls.md
        MCP接入与联调.md         -> mcp.md
        CLI与RML工作流.md        -> cli.md
        画板体检与交付整理.md     -> audit.md
        跨文件搬运画板.md         -> transfer.md
        无清空合并文件.md         -> merge.md
        AI素材导入链路.md         -> asset-import.md
        导出规则与交付验收.md     -> delivery.md
        运行时选型与车机落地.md   -> runtime.md
        数据绑定与状态机驱动.md   -> binding.md
        性能诊断与资产瘦身.md     -> performance.md
        按钮开关与按压动效.md     -> toggle-button.md
    Plus: tools/runtime-check/index.html -> assets/runtime-check-index.html

    Files are written as UTF-8 WITHOUT BOM, so the snapshot stays a clean text
    copy. This script itself must keep its BOM: PS 5.1 would otherwise read the
    Chinese file names below as ANSI and every lookup would miss.

    -Check    verify only: drift between docs and references, docs not in the
              mapping table, and dead relative links. Exit 1 on any finding.

    -Install  also refresh the installed skill at
              $env:USERPROFILE\.workbuddy\skills\rive-ops (user scope).

.EXAMPLE
    .\sync-skill.ps1 -Check
.EXAMPLE
    .\sync-skill.ps1 -Install
#>
param(
    [switch]$Install,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$skill = Join-Path $repo 'skills\rive-ops'

if (-not (Test-Path (Join-Path $skill 'SKILL.md'))) {
    Write-Output 'ERROR: skills/rive-ops/SKILL.md not found; run from the rive-tips repository.'
    exit 1
}

$map = [ordered]@{
    '速查表.md'             = 'pitfalls.md'
    'MCP接入与联调.md'       = 'mcp.md'
    'CLI与RML工作流.md'      = 'cli.md'
    '画板体检与交付整理.md'   = 'audit.md'
    '跨文件搬运画板.md'       = 'transfer.md'
    '无清空合并文件.md'       = 'merge.md'
    'AI素材导入链路.md'       = 'asset-import.md'
    '导出规则与交付验收.md'   = 'delivery.md'
    '运行时选型与车机落地.md' = 'runtime.md'
    '数据绑定与状态机驱动.md' = 'binding.md'
    '性能诊断与资产瘦身.md'   = 'performance.md'
    '按钮开关与按压动效.md'   = 'toggle-button.md'
}

function Convert-DocLinks {
    param([string]$Text)
    # Longest name first, so a short name cannot match inside a longer one.
    foreach ($n in ($map.Keys | Sort-Object -Property Length -Descending)) {
        $target = $map[$n]
        $esc = [regex]::Escape($n)
        $Text = $Text -replace ('\]\((\.\./)?docs/' + $esc + '\)'), ('](' + $target + ')')
        $Text = $Text -replace ('\]\(' + $esc + '\)'), ('](' + $target + ')')
    }
    # Anything still pointing at docs/ has no snapshot counterpart: keep the
    # label, drop the link. Plain text beats a dead link.
    $Text = [regex]::Replace($Text, '\[([^\]]+)\]\((?:\.\./)?docs/[^)]+\.md\)', '$1')
    return $Text
}

function Read-Utf8 {
    param([string]$Path)
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8)
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $enc)
}

function Test-SkillLinks {
    param([string]$Root)
    $bad = New-Object System.Collections.ArrayList
    Get-ChildItem -LiteralPath $Root -Recurse -Filter *.md -File | ForEach-Object {
        $file = $_
        $text = Read-Utf8 $file.FullName
        if (-not $text) { return }
        foreach ($m in [regex]::Matches($text, '\[[^\]]*\]\(([^)]+)\)')) {
            $t = $m.Groups[1].Value.Trim()
            if ($t -match '^(https?:|mailto:|#)') { continue }
            $t = ($t -split '#')[0]
            if (-not $t) { continue }
            $p = Join-Path $file.DirectoryName $t
            if (-not (Test-Path -LiteralPath $p)) {
                [void]$bad.Add(($file.FullName.Substring($Root.Length).TrimStart('\') + ' -> ' + $t))
            }
        }
    }
    return $bad
}

# ---- 1. drift: docs vs snapshot, plus docs missing from the map -------------
$issues = New-Object System.Collections.ArrayList
foreach ($k in $map.Keys) {
    $src = Join-Path $repo ('docs\' + $k)
    $dst = Join-Path $skill ('references\' + $map[$k])
    if (-not (Test-Path -LiteralPath $src)) {
        [void]$issues.Add('MISSING DOC: docs/' + $k)
        continue
    }
    $expected = Convert-DocLinks (Read-Utf8 $src)
    if (-not (Test-Path -LiteralPath $dst)) {
        [void]$issues.Add('MISSING SNAPSHOT: references/' + $map[$k])
        continue
    }
    if ((Read-Utf8 $dst) -cne $expected) {
        [void]$issues.Add('DRIFT: references/' + $map[$k] + ' != docs/' + $k)
    }
}
Get-ChildItem -LiteralPath (Join-Path $repo 'docs') -Filter *.md -File | ForEach-Object {
    if (-not $map.Contains($_.Name)) {
        [void]$issues.Add('UNMAPPED: docs/' + $_.Name + ' (add it to the map)')
    }
}

# ---- 2. dead links inside the skill package ---------------------------------
$links = Test-SkillLinks -Root $skill

if ($Check) {
    foreach ($i in $issues) { Write-Output $i }
    foreach ($l in $links) { Write-Output ('DEAD LINK: ' + $l) }
    if (($issues.Count + $links.Count) -eq 0) {
        Write-Output ('OK: ' + $map.Count + ' references in sync, 0 dead links.')
        exit 0
    }
    Write-Output ('FAIL: ' + $issues.Count + ' drift/unmapped, ' + $links.Count + ' dead links.')
    exit 1
}

# ---- 3. write mode ----------------------------------------------------------
$done = 0
foreach ($k in $map.Keys) {
    $src = Join-Path $repo ('docs\' + $k)
    if (-not (Test-Path -LiteralPath $src)) {
        Write-Output ('SKIP missing source: ' + $k)
        continue
    }
    $dst = Join-Path $skill ('references\' + $map[$k])
    Write-Utf8NoBom $dst (Convert-DocLinks (Read-Utf8 $src))
    $done++
    Write-Output ('SYNCED docs/' + $k + ' -> references/' + $map[$k])
}

$idx = Join-Path $repo 'tools\runtime-check\index.html'
if (Test-Path -LiteralPath $idx) {
    Write-Utf8NoBom (Join-Path $skill 'assets\runtime-check-index.html') (Read-Utf8 $idx)
    Write-Output 'SYNCED tools/runtime-check/index.html -> assets/runtime-check-index.html'
}

Write-Output ('DONE ' + $done + ' docs + 1 asset. Links rewritten to snapshot names.')

$after = Test-SkillLinks -Root $skill
if ($after.Count -gt 0) {
    Write-Output ('WARN: ' + $after.Count + ' dead links remain:')
    foreach ($l in $after) { Write-Output ('  ' + $l) }
}

if ($Install) {
    $target = Join-Path $env:USERPROFILE '.workbuddy\skills\rive-ops'
    if (-not (Test-Path -LiteralPath $target)) {
        New-Item -ItemType Directory -Path $target -Force | Out-Null
    }
    Copy-Item (Join-Path $skill '*') $target -Recurse -Force
    Write-Output ('INSTALLED -> ' + $target)
}
