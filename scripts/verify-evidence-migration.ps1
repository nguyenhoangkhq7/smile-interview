$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$containerName = 'codex-evidence-test-' + [guid]::NewGuid().ToString('N').Substring(0, 10)
$testPassword = [guid]::NewGuid().ToString('N')
try {
    docker run --detach --rm --network none --name $containerName --env "POSTGRES_PASSWORD=$testPassword" postgres:17 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not start isolated PostgreSQL' }
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        docker exec $containerName pg_isready -U postgres *> $null
        if ($LASTEXITCODE -eq 0) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) { throw 'PostgreSQL did not become ready' }
    $files = @('backend/src/main/resources/db/migration/V1__init_schema.sql',
               'backend/src/main/resources/db/migration/V2__evidence_interviews.sql',
               'backend/src/test/resources/evidence-migration-assertions.sql')
    foreach ($file in $files) {
        Get-Content -Raw -LiteralPath (Join-Path $repoRoot $file) | docker exec -i $containerName psql -U postgres -v ON_ERROR_STOP=1
        if ($LASTEXITCODE -ne 0) { throw "Migration validation failed: $file" }
    }
    Write-Output 'PostgreSQL 17 migration and constraints passed.'
} finally {
    docker rm --force $containerName | Out-Null
}
