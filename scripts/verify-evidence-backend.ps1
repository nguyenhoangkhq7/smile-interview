param([string]$JavaHome = $env:JAVA_HOME)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$containerName = 'codex-backend-test-' + [guid]::NewGuid().ToString('N').Substring(0, 10)
$testPassword = [guid]::NewGuid().ToString('N')
$previous = @{}
$names = @('JAVA_HOME', 'SPRING_DATASOURCE_URL', 'SPRING_DATASOURCE_USERNAME', 'SPRING_DATASOURCE_PASSWORD')
foreach ($name in $names) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    docker run --detach --rm --name $containerName -p '127.0.0.1::5432' --env "POSTGRES_PASSWORD=$testPassword" postgres:17 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Could not start isolated PostgreSQL' }
    $binding = docker port $containerName 5432/tcp
    $port = ($binding -split ':')[-1]
    $env:JAVA_HOME = $JavaHome
    $env:SPRING_DATASOURCE_URL = "jdbc:postgresql://127.0.0.1:$port/postgres"
    $env:SPRING_DATASOURCE_USERNAME = 'postgres'
    $env:SPRING_DATASOURCE_PASSWORD = $testPassword
    Push-Location (Join-Path $repoRoot 'backend')
    try {
        # Maven copies the source read-only attribute to generated resources on this host.
        $buildTarget = Join-Path $repoRoot 'backend/target'
        if (Test-Path -LiteralPath $buildTarget) {
            Get-ChildItem -LiteralPath $buildTarget -Recurse -File | ForEach-Object { $_.IsReadOnly = $false }
        }
        & .\mvnw.cmd -q '-DargLine=-Duser.timezone=UTC' test
        if ($LASTEXITCODE -ne 0) { throw 'Backend tests failed' }
    } finally { Pop-Location }
} finally {
    docker rm --force $containerName | Out-Null
    foreach ($name in $names) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
}
