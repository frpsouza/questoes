# Baixa as normas listadas em fontes.csv para a pasta originais/.
# Uso:  pwsh -File legislacao\baixar.ps1            (pula o que já foi baixado)
#       pwsh -File legislacao\baixar.ps1 -Forcar    (baixa tudo de novo)
param([switch]$Forcar)

$base = $PSScriptRoot
$dest = Join-Path $base 'originais'
New-Item -ItemType Directory -Force $dest | Out-Null

$falhas = @()
foreach ($f in Import-Csv (Join-Path $base 'fontes.csv') -Delimiter ';') {
    $out = Join-Path $dest $f.arquivo
    if ((Test-Path $out) -and -not $Forcar) { Write-Host "ok (já existe)  $($f.arquivo)"; continue }
    try {
        Invoke-WebRequest -Uri $f.url -OutFile $out -TimeoutSec 180 -UseBasicParsing
        $tam = (Get-Item $out).Length
        # Página sem texto da norma (ex.: LEGIS da AL-RS devolve página vazia para downloads automáticos)
        if ($f.arquivo -like '*.htm' -and -not (Select-String -Path $out -Pattern 'Art\.?\s*1' -Quiet)) {
            Remove-Item $out
            throw "página sem texto da norma ($tam bytes)"
        }
        Write-Host "baixado         $($f.arquivo) ($tam bytes)"
    } catch {
        Write-Warning "FALHOU          $($f.arquivo): $($_.Exception.Message)"
        $falhas += $f
    }
}

if ($falhas) {
    Write-Host "`nBaixe manualmente no navegador (Ctrl+S, 'Página da Web, somente HTML') e salve em $dest com o nome indicado:"
    $falhas | ForEach-Object { Write-Host " - $($_.arquivo)`n   $($_.url)" }
}
