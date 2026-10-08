# Windows fallback when the bundled render_docx.py cannot find a bundled office renderer.
param([string]$Docx,[string]$Pdf)
$ErrorActionPreference='Stop'
$word=New-Object -ComObject Word.Application
$word.Visible=$false
$word.DisplayAlerts=0
try {
  $document=$word.Documents.Open((Resolve-Path -LiteralPath $Docx).Path,$false,$true)
  try { $document.ExportAsFixedFormat([IO.Path]::GetFullPath($Pdf),17) }
  finally {$document.Close(0)}
} finally {$word.Quit()}
