param(
    [string]$PdfPath = "docs\[Tailieuvui.com]_giao-trinh-tieng-han-tong-hop-trung-cap-4-pdf.pdf",
    [string]$MarkerSingle = $env:MARKER_SINGLE
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $MarkerSingle) {
    $MarkerSingle = "C:\marker-pilot-venv\Scripts\marker_single.exe"
}

$inputPdf = Resolve-Path -LiteralPath (Join-Path $repoRoot $PdfPath)
$outputRoot = Join-Path $repoRoot "private-data\marker-pilot"
$markdownDir = Join-Path $outputRoot "markdown"
$jsonDir = Join-Path $outputRoot "json"
New-Item -ItemType Directory -Force -Path $markdownDir, $jsonDir | Out-Null

$common = @(
    $inputPdf.Path,
    "--mode", "fast",
    "--disable_ocr",
    "--page_range", "17-34",
    "--disable_multiprocessing",
    "--disable_tqdm"
)

$env:PYTHONIOENCODING = "utf-8"
& $MarkerSingle @common --output_format markdown --output_dir $markdownDir --paginate_output
if ($LASTEXITCODE -ne 0) { throw "Marker Markdown pilot failed with exit code $LASTEXITCODE" }

& $MarkerSingle @common --output_format json --output_dir $jsonDir
if ($LASTEXITCODE -ne 0) { throw "Marker JSON pilot failed with exit code $LASTEXITCODE" }

Write-Output "Marker pilot complete: PDF pages 18-35 (Marker page_range 17-34)."
