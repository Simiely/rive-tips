#Requires -Version 5.1
<#
.SYNOPSIS
    Export an Adobe Illustrator document to SVG, ready for Rive import.

.DESCRIPTION
    Attaches to a RUNNING Illustrator instance via COM and exports via
    ExtendScript. Requires the document to be open, or opens it by path.

    Guards included (all learned the hard way, see docs/AI素材导入链路.md):
      - DONTDISPLAYALERTS is set first, or any dialog hangs COM forever
      - Document matched by EXACT file name ("深色.ai" vs "浅色.ai" share a prefix)
      - Artboards collection is never enumerated with foreach (infinite output)
      - After export, the file's existence is reported (some options fail silently)

    NOTE: text stays as <text> elements. Rive maps font-family by name and can
    fall back to its bundled Inter font (no CJK glyphs). Convert text to
    outlines in Illustrator (Type > Create Outlines) BEFORE exporting, or
    re-link fonts in Rive afterwards.

.PARAMETER FileName
    Exact document file name to export (must be open, or use -SourceAi).

.PARAMETER SourceAi
    Absolute path of the .ai to open if not already open.

.PARAMETER OutSvg
    Output SVG path.

.EXAMPLE
    .\ai-svg-export.ps1 -FileName '261026x01深色.ai' -SourceAi 'D:\src\261026x01深色.ai' -OutSvg 'D:\out\dark.svg'
#>
param(
    [Parameter(Mandatory = $true)][string]$FileName,
    [string]$SourceAi = '',
    [Parameter(Mandatory = $true)][string]$OutSvg,
    [string]$Endpoint = 'unused',
    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

if (Test-Path $OutSvg) { Remove-Item $OutSvg -Force }
$outJs = $OutSvg -replace '\\', '/'
$srcJs = if ($SourceAi) { $SourceAi -replace '\\', '/' } else { '' }

$ai = [Runtime.InteropServices.Marshal]::GetActiveObject('Illustrator.Application')
Write-Output ("ATTACHED v" + $ai.Version)

$matchName = $FileName -replace "'", "\'"
$openLine = if ($SourceAi) {
    "if (!doc) { doc = app.open(new File(`"$srcJs`")); }"
} else {
    "if (!doc) { throw new Error('document not open: " + $FileName + "'); }"
}

$js = @"
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var doc = null;
for (var i = 0; i < app.documents.length; i++) {
  if (app.documents[i].name == "$matchName") { doc = app.documents[i]; break; }
}
$openLine
var r = "doc=" + doc.name + " items=" + doc.pageItems.length;
var opt = new ExportOptionsSVG();
opt.embedRasterImages = true;
var f = new File("$outJs");
doc.exportFile(f, ExportType.SVG, opt);
r += " exists=" + f.exists;
if (-not ($KeepOpen.IsPresent)) { doc.close(SaveOptions.DONOTSAVECHANGES); r += " closed"; }
r;
"@

try {
    $res = $ai.DoJavaScript($js)
    Write-Output ("RESULT: " + $res)
} catch {
    Write-Output ("COM_ERROR: " + $_.Exception.Message)
    Write-Output 'If Illustrator is showing a dialog, dismiss it and retry.'
    exit 1
}

Start-Sleep -Milliseconds 800
if (Test-Path $OutSvg) {
    $kb = [math]::Round((Get-Item $OutSvg).Length / 1KB, 1)
    Write-Output ("SVG_OK: " + $OutSvg + " (" + $kb + " KB)")
    Write-Output 'NEXT: strip the embedded <font> block, then upload via upload_asset with a data URI.'
} else {
    Write-Output 'SVG_MISSING: export reported success but no file was written.'
    Write-Output 'Known cause: ExportOptionsSVG.fontType = OUTLINEFONT fails silently on AI 30.1.0.'
    exit 1
}
