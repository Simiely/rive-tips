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

    And scripts/* -> skills/rive-ops/scripts/* (same basename, top level only).
    Scripts are copied BYTE FOR BYTE with no link rewriting, so a stale copy in
    the skill (an older ai-svg-export.ps1, a missing svg-prep.py) is caught by
    -Check exactly like doc drift. Subdirectories such as scripts/rive-merge/
    ship only inside the skill and are left untouched; a loose skill-only file
    at the top level is reported as SKILL-ONLY because it usually means a
    rename that was never mirrored back into the repo.

    Docs are written as UTF-8 WITHOUT BOM, so the snapshot stays a clean text
    copy. This script itself must keep its BOM: PS 5.1 would otherwise read the
    Chinese file names below as ANSI and every lookup would miss.

    -Check    verify only: drift between docs and references, drift between
              repo scripts and skill scripts, the pitfall-row count quoted in
              SKILL.md against the real table, docs not in the mapping table,
              and dead relative links. Exit 1 on any finding.

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

# ---- 1b. drift: repo scripts/* vs skill scripts/* (top level files only) ----
$scriptSrc = Join-Path $repo 'scripts'
$scriptDst = Join-Path $skill 'scripts'
$scriptFiles = @()
if (Test-Path -LiteralPath $scriptSrc) {
    $scriptFiles = @(Get-ChildItem -LiteralPath $scriptSrc -File | Sort-Object Name)
}
foreach ($f in $scriptFiles) {
    $dst = Join-Path $scriptDst $f.Name
    if (-not (Test-Path -LiteralPath $dst)) {
        [void]$issues.Add('MISSING SCRIPT: skills/rive-ops/scripts/' + $f.Name)
        continue
    }
    $ha = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    $hb = (Get-FileHash -LiteralPath $dst -Algorithm SHA256).Hash
    if ($ha -ne $hb) {
        [void]$issues.Add('DRIFT: skills/rive-ops/scripts/' + $f.Name + ' != scripts/' + $f.Name)
    }
}
# Directories under scripts/ (rive-merge/) are skill-only by design and are
# skipped; a top-level file with no repo source is almost always a rename.
if (Test-Path -LiteralPath $scriptDst) {
    Get-ChildItem -LiteralPath $scriptDst -File | ForEach-Object {
        if (-not (Test-Path -LiteralPath (Join-Path $scriptSrc $_.Name))) {
            [void]$issues.Add('SKILL-ONLY: skills/rive-ops/scripts/' + $_.Name + ' (no source in scripts/)')
        }
    }
}

# ---- 1c. stale numbers: the pitfall-row count quoted in SKILL.md ------------
# SKILL.md ends its symptom-routing table with "完整 N 行对照表：references/
# pitfalls.md". That N is the entry point to the full table — if it rots, the
# triage path lies about how much is behind it. Nothing else checks it: it is
# prose, not a link. So compare it against the real row count.
function Get-PitfallRowCount {
    param([string]$DocPath)
    if (-not (Test-Path -LiteralPath $DocPath)) { return -1 }
    $n = 0
    $inSec = $false
    foreach ($line in ((Read-Utf8 $DocPath) -split "`r?`n")) {
        if ($line -match '^## 七、') { $inSec = $true; continue }
        if ($inSec -and $line -match '^## 八、') { break }
        if ($inSec -and $line.StartsWith('|')) { $n++ }
    }
    return ($n - 2)   # minus header + separator
}

$skillMd = Join-Path $skill 'SKILL.md'
if (Test-Path -LiteralPath $skillMd) {
    $q = [regex]::Match((Read-Utf8 $skillMd), '完整\s*(\d+)\s*行对照表')
    if ($q.Success) {
        $real = Get-PitfallRowCount (Join-Path $repo 'docs\速查表.md')
        if ($real -ge 0 -and [int]$q.Groups[1].Value -ne $real) {
            [void]$issues.Add('STALE COUNT: SKILL.md quotes ' + $q.Groups[1].Value +
                              ' pitfall rows, docs/速查表.md has ' + $real)
        }
    }
}

# ---- 1d. SKILL.md frontmatter must start with a bare "---" ------------------
# PowerShell 5.1's `Set-Content -Encoding UTF8` writes a BOM. Applied to
# SKILL.md that turns the opening "---" into "\uFEFF---", and a YAML parser
# then no longer sees a frontmatter block at all — with no error anywhere.
if (Test-Path -LiteralPath $skillMd) {
    $bytes = [System.IO.File]::ReadAllBytes($skillMd)
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        [void]$issues.Add('BOM IN SKILL.md: frontmatter now starts with U+FEFF, YAML parsers may ignore it')
    }
    elseif (-not ($bytes.Length -ge 3 -and $bytes[0] -eq 0x2D -and $bytes[1] -eq 0x2D -and $bytes[2] -eq 0x2D)) {
        [void]$issues.Add('BAD FRONTMATTER: SKILL.md does not start with ---')
    }
}

# ---- 2. dead links inside the skill package ---------------------------------
$links = Test-SkillLinks -Root $skill

if ($Check) {
    foreach ($i in $issues) { Write-Output $i }
    foreach ($l in $links) { Write-Output ('DEAD LINK: ' + $l) }
    if (($issues.Count + $links.Count) -eq 0) {
        Write-Output ('OK: ' + $map.Count + ' references + ' + $scriptFiles.Count + ' scripts in sync, 0 dead links.')
        exit 0
    }
    Write-Output ('FAIL: ' + $issues.Count + ' drift/unmapped/missing, ' + $links.Count + ' dead links.')
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

# Byte copy: a .ps1 keeps its BOM (or its lack of one) exactly as committed.
$sdone = 0
if ($scriptFiles.Count -gt 0 -and -not (Test-Path -LiteralPath $scriptDst)) {
    New-Item -ItemType Directory -Path $scriptDst -Force | Out-Null
}
foreach ($f in $scriptFiles) {
    Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $scriptDst $f.Name) -Force
    $sdone++
    Write-Output ('SYNCED scripts/' + $f.Name + ' -> skills/rive-ops/scripts/' + $f.Name)
}

Write-Output ('DONE ' + $done + ' docs + 1 asset + ' + $sdone + ' scripts. Links rewritten to snapshot names.')

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
