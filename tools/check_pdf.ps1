$figuresDir = "c:\Users\云发鹏🐧\Desktop\毕设\liziqun\paper\figures"
Get-ChildItem "$figuresDir\*.pdf" | ForEach-Object {
    Write-Host "$($_.Name): $($_.Length) bytes"
    $bytes = [System.IO.File]::ReadAllBytes($_.FullName)
    $text = [System.Text.Encoding]::ASCII.GetString($bytes)
    $fontMatches = [regex]::Matches($text, '/BaseFont\s*/\S+')
    Write-Host "  Fonts:"
    foreach ($m in $fontMatches) { Write-Host "    $($m.Value)" }
    $embeddedMatches = [regex]::Matches($text, '/FontFile[23]')
    Write-Host "  Embedded font references: $($embeddedMatches.Count)"
    Write-Host ""
}
