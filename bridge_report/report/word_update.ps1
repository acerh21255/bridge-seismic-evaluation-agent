param(
    [Parameter(Mandatory = $true)][string]$Docx,
    [string]$Pdf = ''
)
# Refresh all fields and the table of contents, save, and optionally export PDF.
# Only the Word instance created here is closed; running user instances are not touched.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$word = $null
$doc = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($Docx, $false, $false, $false)
    $doc.Fields.Update() | Out-Null
    foreach ($toc in $doc.TablesOfContents) { $toc.Update() }
    $doc.Repaginate()
    foreach ($toc in $doc.TablesOfContents) { $toc.UpdatePageNumbers() }
    $pages = $doc.ComputeStatistics(2)
    $doc.Save()
    if ($Pdf) { $doc.ExportAsFixedFormat($Pdf, 17) }
    Write-Output (@{ ok = $true; pages = $pages } | ConvertTo-Json -Compress)
}
catch {
    Write-Output (@{ ok = $false; message = $_.Exception.Message } | ConvertTo-Json -Compress)
    exit 1
}
finally {
    if ($doc) { $doc.Close(0) | Out-Null }
    if ($word) {
        $word.Quit() | Out-Null
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
}
