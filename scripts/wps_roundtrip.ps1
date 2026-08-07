[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputDirectory
)

$ErrorActionPreference = 'Stop'

$sourcePath = (Resolve-Path -LiteralPath $InputPath).Path
if ([IO.Path]::GetExtension($sourcePath) -ne '.docx') {
    throw "Input must be a .docx file: $sourcePath"
}

$outputRoot = [IO.Path]::GetFullPath($OutputDirectory)
[void](New-Item -ItemType Directory -Path $outputRoot -Force)
$stem = [IO.Path]::GetFileNameWithoutExtension($sourcePath)
$roundtripPath = Join-Path $outputRoot "$stem.wps-roundtrip.docx"
$pdfPath = Join-Path $outputRoot "$stem.wps.pdf"
if ((Test-Path -LiteralPath $roundtripPath) -or (Test-Path -LiteralPath $pdfPath)) {
    throw "Refusing to overwrite an existing WPS QA artifact in: $outputRoot"
}

$beforePids = @(Get-Process -Name wps -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$application = $null
$document = $null
try {
    $application = New-Object -ComObject KWps.Application
    $application.Visible = $false
    $document = $application.Documents.Open($sourcePath, $false, $true)
    $document.SaveAs2($roundtripPath, 12) # wdFormatXMLDocument
    $document.ExportAsFixedFormat($pdfPath, 17) # wdExportFormatPDF
    $document.Close($false)
    $document = $null
    $application.Quit()
    $application = $null
}
finally {
    if ($null -ne $document) {
        try { $document.Close($false) } catch { Write-Warning $_ }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($document)
    }
    if ($null -ne $application) {
        try { $application.Quit() } catch { Write-Warning $_ }
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($application)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Start-Sleep -Seconds 3
$afterPids = @(Get-Process -Name wps -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
$newPids = @($afterPids | Where-Object { $_ -notin $beforePids })
if ($newPids.Count -gt 0) {
    Write-Warning "WPS left new background process IDs running: $($newPids -join ', ')"
}

Get-Item -LiteralPath $roundtripPath, $pdfPath |
    Select-Object FullName, Length, LastWriteTime
