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
      - Only documents this script opened are closed, and never saved

    TEXT: by default text stays as <text> elements. Rive maps font-family by name
    and can fall back to its bundled Inter font (no CJK), which kills Chinese.
    Pass -OutlineText to run createOutline() on every text frame before exporting
    (equivalent to Type > Create Outlines). It walks textFrames in REVERSE because
    createOutline() replaces the frame with a group and shifts the collection.
    Outlining is one-way: the source .ai is closed WITHOUT saving, so keep a
    master copy if the text still needs editing.

.PARAMETER FileName
    Exact document file name to export (must be open, or use -SourceAi).

.PARAMETER SourceAi
    Absolute path of the .ai to open if not already open.

.PARAMETER OutSvg
    Output SVG path.

.PARAMETER OutlineText
    Convert every text frame to outlines before exporting (recommended for Rive).

.PARAMETER KeepOpen
    Do not close the document after exporting.

.EXAMPLE
    .\ai-svg-export.ps1 -FileName '261026x01深色.ai' -SourceAi 'D:\src\261026x01深色.ai' -OutSvg 'D:\out\dark.svg' -OutlineText
#>
param(
    [Parameter(Mandatory = $true)][string]$FileName,
    [string]$SourceAi = '',
    [Parameter(Mandatory = $true)][string]$OutSvg,
    [switch]$OutlineText,
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
    "if (!doc) { doc = app.open(new File(`"$srcJs`")); opened = true; }"
} else {
    "if (!doc) { throw new Error('document not open: " + $FileName + "'); }"
}

# ExtendScript snippets are assembled as PowerShell strings: never put PowerShell
# syntax (-not, $x.IsPresent) inside the here-string, it is not JavaScript.
$outlineJs = if ($OutlineText) {
    @'
var outlined = 0, failed = 0;
for (var k = doc.textFrames.length - 1; k >= 0; k--) {
  try { doc.textFrames[k].createOutline(); outlined++; } catch (e) { failed++; }
}
r += " outlined=" + outlined + " failed=" + failed;
'@
} else {
    'r += " textFrames=" + doc.textFrames.length + " kept as text";'
}
$closeJs = if ($KeepOpen) { '' } else { 'if (opened) { doc.close(SaveOptions.DONOTSAVECHANGES); r += " closed"; }' }

$js = @"
app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
var doc = null;
var opened = false;
for (var i = 0; i < app.documents.length; i++) {
  if (app.documents[i].name == "$matchName") { doc = app.documents[i]; break; }
}
$openLine
var r = "doc=" + doc.name + " items=" + doc.pageItems.length;
$outlineJs
var opt = new ExportOptionsSVG();
opt.embedRasterImages = true;
try { opt.preserveEditability = false; } catch (e) {}
try { opt.cssProperties = SVGCSSPropertyLocation.PRESENTATIONATTRIBUTES; } catch (e) {}
var f = new File("$outJs");
doc.exportFile(f, ExportType.SVG, opt);
r += " exists=" + f.exists;
$closeJs
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
    Write-Output 'NEXT: scripts/svg-prep.py clean -> images -> clip -> mask, then upload via data URI.'
} else {
    Write-Output 'SVG_MISSING: export reported success but no file was written.'
    Write-Output 'Known cause: ExportOptionsSVG.fontType = OUTLINEFONT fails silently on AI 30.1.0.'
    exit 1
}
