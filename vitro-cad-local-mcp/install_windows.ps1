# Installs the plugin for the current Windows user without system prerequisites.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

trap {
    [System.Windows.Forms.MessageBox]::Show(
        $_.Exception.Message,
        'Vitro-CAD MCP: ошибка установки',
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
    exit 1
}

function Get-VitroSha256 {
    param([string]$Path)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try {
        return [System.BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $algorithm.Dispose()
    }
}

function Expand-VitroRuntime {
    param([string]$ArchivePath, [string]$DestinationPath)
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    if (Test-Path -LiteralPath $DestinationPath) {
        Remove-Item -LiteralPath $DestinationPath -Recurse -Force
    }
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ArchivePath, $DestinationPath)
}

function Get-VitroCredential {
    $blue = [System.Drawing.ColorTranslator]::FromHtml('#283277')
    $green = [System.Drawing.ColorTranslator]::FromHtml('#16692F')
    $muted = [System.Drawing.ColorTranslator]::FromHtml('#596579')
    $surface = [System.Drawing.ColorTranslator]::FromHtml('#F5F7FA')
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'Подключение Vitro-CAD к агенту'
    $form.StartPosition = 'CenterScreen'
    $form.ClientSize = New-Object System.Drawing.Size -ArgumentList 510, 625
    $form.FormBorderStyle = 'FixedDialog'
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.BackColor = $surface
    $form.Font = New-Object System.Drawing.Font -ArgumentList 'Segoe UI', 10

    $header = New-Object System.Windows.Forms.Panel
    $header.Location = New-Object System.Drawing.Point -ArgumentList 0, 0
    $header.Size = New-Object System.Drawing.Size -ArgumentList 510, 88
    $header.BackColor = [System.Drawing.Color]::White
    $form.Controls.Add($header)
    $brandLine = New-Object System.Windows.Forms.Panel
    $brandLine.Location = New-Object System.Drawing.Point -ArgumentList 0, 85
    $brandLine.Size = New-Object System.Drawing.Size -ArgumentList 510, 3
    $brandLine.BackColor = $green
    $header.Controls.Add($brandLine)
    $titleLabel = New-Object System.Windows.Forms.Label
    $titleLabel.Text = 'Подключение Vitro-CAD'
    $titleLabel.Font = New-Object System.Drawing.Font -ArgumentList 'Segoe UI', 16, ([System.Drawing.FontStyle]::Bold)
    $titleLabel.ForeColor = $blue
    $titleLabel.AutoSize = $true
    $titleLabel.Location = New-Object System.Drawing.Point -ArgumentList 28, 103
    $form.Controls.Add($titleLabel)
    $subtitleLabel = New-Object System.Windows.Forms.Label
    $subtitleLabel.Text = 'Войдите под своей личной учетной записью. Доступ ограничен вашими правами.'
    $subtitleLabel.Font = New-Object System.Drawing.Font -ArgumentList 'Segoe UI', 9
    $subtitleLabel.ForeColor = $muted
    $subtitleLabel.AutoSize = $true
    $subtitleLabel.Location = New-Object System.Drawing.Point -ArgumentList 29, 141
    $form.Controls.Add($subtitleLabel)
    $portalLabel = New-Object System.Windows.Forms.Label
    $portalLabel.Text = 'Адрес портала Vitro-CAD (https://...)'
    $portalLabel.Location = New-Object System.Drawing.Point -ArgumentList 28, 177
    $portalLabel.AutoSize = $true
    $portalLabel.ForeColor = $blue
    $form.Controls.Add($portalLabel)
    $portalBox = New-Object System.Windows.Forms.TextBox
    $portalBox.Location = New-Object System.Drawing.Point -ArgumentList 28, 201
    $portalBox.Size = New-Object System.Drawing.Size -ArgumentList 450, 29
    $form.Controls.Add($portalBox)
    $loginLabel = New-Object System.Windows.Forms.Label
    $loginLabel.Text = 'Логин или e-mail'
    $loginLabel.Location = New-Object System.Drawing.Point -ArgumentList 28, 246
    $loginLabel.AutoSize = $true
    $loginLabel.ForeColor = $blue
    $form.Controls.Add($loginLabel)
    $loginBox = New-Object System.Windows.Forms.TextBox
    $loginBox.Location = New-Object System.Drawing.Point -ArgumentList 28, 270
    $loginBox.Size = New-Object System.Drawing.Size -ArgumentList 450, 29
    $form.Controls.Add($loginBox)
    $passwordLabel = New-Object System.Windows.Forms.Label
    $passwordLabel.Text = 'Пароль'
    $passwordLabel.Location = New-Object System.Drawing.Point -ArgumentList 28, 313
    $passwordLabel.AutoSize = $true
    $passwordLabel.ForeColor = $blue
    $form.Controls.Add($passwordLabel)
    $passwordBox = New-Object System.Windows.Forms.TextBox
    $passwordBox.Location = New-Object System.Drawing.Point -ArgumentList 28, 337
    $passwordBox.Size = New-Object System.Drawing.Size -ArgumentList 450, 29
    $passwordBox.UseSystemPasswordChar = $true
    $form.Controls.Add($passwordBox)

    $registryLabel = New-Object System.Windows.Forms.Label
    $registryLabel.Text = 'GUID реестра проектов (необязательно, можно задать позже)'
    $registryLabel.Location = New-Object System.Drawing.Point -ArgumentList 28, 384
    $registryLabel.AutoSize = $true
    $registryLabel.ForeColor = $muted
    $form.Controls.Add($registryLabel)
    $registryBox = New-Object System.Windows.Forms.TextBox
    $registryBox.Location = New-Object System.Drawing.Point -ArgumentList 28, 407
    $registryBox.Size = New-Object System.Drawing.Size -ArgumentList 270, 26
    $form.Controls.Add($registryBox)
    $agentsLabel = New-Object System.Windows.Forms.Label
    $agentsLabel.Text = 'Подключить к агентам:'
    $agentsLabel.Location = New-Object System.Drawing.Point -ArgumentList 28, 441
    $agentsLabel.AutoSize = $true
    $form.Controls.Add($agentsLabel)
    $codexCheck = New-Object System.Windows.Forms.CheckBox
    $codexCheck.Text = 'Codex Desktop'
    $codexCheck.Checked = $true
    $codexCheck.Location = New-Object System.Drawing.Point -ArgumentList 29, 466
    $codexCheck.AutoSize = $true
    $form.Controls.Add($codexCheck)
    $claudeCheck = New-Object System.Windows.Forms.CheckBox
    $claudeCheck.Text = 'Claude Code'
    $claudeCheck.Location = New-Object System.Drawing.Point -ArgumentList 190, 466
    $claudeCheck.AutoSize = $true
    $form.Controls.Add($claudeCheck)
    $qwenCheck = New-Object System.Windows.Forms.CheckBox
    $qwenCheck.Text = 'Qwen Code'
    $qwenCheck.Location = New-Object System.Drawing.Point -ArgumentList 335, 466
    $qwenCheck.AutoSize = $true
    $form.Controls.Add($qwenCheck)
    $privacyLabel = New-Object System.Windows.Forms.Label
    $privacyLabel.Text = 'Пароль хранится только в защищённом хранилище Windows.'
    $privacyLabel.Font = New-Object System.Drawing.Font -ArgumentList 'Segoe UI', 8.5
    $privacyLabel.ForeColor = $muted
    $privacyLabel.AutoSize = $true
    $privacyLabel.Location = New-Object System.Drawing.Point -ArgumentList 29, 570
    $form.Controls.Add($privacyLabel)
    $button = New-Object System.Windows.Forms.Button
    $button.Text = 'Подключить'
    $button.Location = New-Object System.Drawing.Point -ArgumentList 313, 526
    $button.Size = New-Object System.Drawing.Size -ArgumentList 165, 42
    $button.BackColor = $green
    $button.ForeColor = [System.Drawing.Color]::White
    $button.FlatStyle = [System.Windows.Forms.FlatStyle]::Flat
    $button.FlatAppearance.BorderSize = 0
    $button.Font = New-Object System.Drawing.Font -ArgumentList 'Segoe UI', 10, ([System.Drawing.FontStyle]::Bold)
    $button.Add_Click({
        if ($portalBox.Text.Trim() -and $loginBox.Text.Trim() -and $passwordBox.Text -and ($codexCheck.Checked -or $claudeCheck.Checked -or $qwenCheck.Checked)) {
            $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
            $form.Close()
        } else {
            [System.Windows.Forms.MessageBox]::Show('Введите адрес портала, логин, пароль и выберите хотя бы одного агента.') | Out-Null
        }
    })
    $form.Controls.Add($button)
    $form.AcceptButton = $button
    $form.TopMost = $true
    $form.Add_Shown({ $portalBox.Focus() })
    $result = $form.ShowDialog()
    if ($result -ne [System.Windows.Forms.DialogResult]::OK) {
        $form.Dispose()
        throw 'Ввод учетных данных отменен.'
    }
    $credential = [pscustomobject]@{ portal = $portalBox.Text.Trim(); login = $loginBox.Text.Trim(); password = $passwordBox.Text; registry_list_id = $registryBox.Text.Trim(); codex = $codexCheck.Checked; claude = $claudeCheck.Checked; qwen = $qwenCheck.Checked }
    $form.Dispose()
    return $credential
}

function Invoke-VitroCredentialSetup {
    param(
        [string]$PythonPath,
        [string]$SetupPath,
        [string]$CredentialJson
    )
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $PythonPath
    $startInfo.Arguments = ('"{0}" --credential-stdin' -f $SetupPath)
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardInput = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    $process = [System.Diagnostics.Process]::Start($startInfo)
    if (-not $process) { throw 'Не удалось запустить проверку входа Vitro-CAD.' }
    try {
        $inputBytes = [Text.Encoding]::UTF8.GetBytes($CredentialJson + [Environment]::NewLine)
        $process.StandardInput.BaseStream.Write($inputBytes, 0, $inputBytes.Length)
        $process.StandardInput.Close()
        $outputStream = New-Object IO.MemoryStream
        $errorStream = New-Object IO.MemoryStream
        $process.StandardOutput.BaseStream.CopyTo($outputStream)
        $process.StandardError.BaseStream.CopyTo($errorStream)
        $process.WaitForExit()
        $output = [Text.Encoding]::UTF8.GetString($outputStream.ToArray()).Trim()
        $errorText = [Text.Encoding]::UTF8.GetString($errorStream.ToArray()).Trim()
        if ($process.ExitCode -ne 0) {
            if ($errorText) { throw $errorText }
            throw 'Вход Vitro-CAD не подтвержден.'
        }
        if ($output) { Write-Host $output }
    } finally {
        $process.Dispose()
    }
}

if ($env:OS -ne 'Windows_NT') { throw 'Установщик предназначен для Windows.' }
$windowsIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$windowsPrincipal = New-Object System.Security.Principal.WindowsPrincipal -ArgumentList $windowsIdentity
if ($windowsPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Запуск с правами администратора Windows не нужен. Запустите установщик обычным двойным щелчком под той же учётной записью Windows, в которой работает ваш агент.'
}

$source = Split-Path -Parent $MyInvocation.MyCommand.Path
$destination = Join-Path $env:USERPROFILE '.codex\plugins\vitro-cad-local-mcp'
$marketplacePath = Join-Path $env:USERPROFILE '.agents\plugins\marketplace.json'
$configPath = Join-Path $env:USERPROFILE '.codex\config.toml'
$skillPath = Join-Path $env:USERPROFILE '.agents\skills\vitro-cad-local-mcp'

# SHA-256 checksums published on the Python 3.14.10 release page.
$runtimePackages = @{
    AMD64 = @{ File = 'python-3.14.10-embed-amd64.zip'; Sha256 = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159' }
    ARM64 = @{ File = 'python-3.14.10-embed-arm64.zip'; Sha256 = 'bbe116bb1248820359cbf25127ac5c7794ea161869d83686cfbc9a45203ff836' }
    x86 = @{ File = 'python-3.14.10-embed-win32.zip'; Sha256 = '11a28e8c00a6d8f56b0a6164d52546133a9ed015a5b33e04536917e4fd6e306c' }
}
$architecture = $env:PROCESSOR_ARCHITEW6432
if (-not $architecture) { $architecture = $env:PROCESSOR_ARCHITECTURE }
if (-not $runtimePackages.ContainsKey($architecture)) {
    throw "Неизвестная архитектура Windows: $architecture"
}
$package = $runtimePackages[$architecture]
$sourceArchive = Join-Path $source (Join-Path 'runtime\packages' $package.File)
if (-not (Test-Path -LiteralPath $sourceArchive)) { throw "В архиве плагина нет $($package.File)." }
$actualHash = Get-VitroSha256 -Path $sourceArchive
if ($actualHash -ne $package.Sha256) { throw "Контрольная сумма $($package.File) не совпадает. Получите исходный архив заново." }

if ([IO.Path]::GetFullPath($source).TrimEnd('\') -ne [IO.Path]::GetFullPath($destination).TrimEnd('\')) {
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
}

$runtimePath = Join-Path $destination 'runtime\active'
$pythonPath = Join-Path $runtimePath 'python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Expand-VitroRuntime -ArchivePath (Join-Path $destination (Join-Path 'runtime\packages' $package.File)) -DestinationPath $runtimePath
}
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Не удалось распаковать встроенную среду Python.' }
$pthPath = Join-Path $runtimePath 'python314._pth'
$pth = Get-Content -LiteralPath $pthPath -Raw -Encoding UTF8
if ($pth -notmatch '(?m)^\.\.\\\.\.\\server\r?$') {
    [IO.File]::AppendAllText($pthPath, "`r`n..\..\server`r`n", [Text.Encoding]::ASCII)
}

$setupPath = Join-Path $destination 'server\setup_windows.py'
Write-Host 'Откроется окно для ввода адреса портала и личных учётных данных Vitro-CAD.'
$vitroCredential = Get-VitroCredential
$installCodex = $vitroCredential.codex
$installClaude = $vitroCredential.claude
$installQwen = $vitroCredential.qwen
$credentialJson = [pscustomobject]@{ portal = $vitroCredential.portal; login = $vitroCredential.login; password = $vitroCredential.password; registry_list_id = $vitroCredential.registry_list_id } | ConvertTo-Json -Compress
Invoke-VitroCredentialSetup -PythonPath $pythonPath -SetupPath $setupPath -CredentialJson $credentialJson
$credentialJson = $null
$vitroCredential = $null

if ($installCodex) {
$marketplaceDirectory = Split-Path -Parent $marketplacePath
New-Item -ItemType Directory -Force -Path $marketplaceDirectory | Out-Null
if (Test-Path -LiteralPath $marketplacePath) {
    $marketplace = Get-Content -LiteralPath $marketplacePath -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $marketplace = [pscustomobject]@{ name = 'local-vitro-tools'; plugins = @() }
}
if (-not $marketplace.PSObject.Properties['name']) {
    $marketplace | Add-Member -NotePropertyName name -NotePropertyValue 'local-vitro-tools'
}
if (-not $marketplace.PSObject.Properties['plugins']) {
    $marketplace | Add-Member -NotePropertyName plugins -NotePropertyValue @()
}
if (-not $marketplace.plugins) { $marketplace.plugins = @() }
$entry = [pscustomobject]@{
    name = 'vitro-cad-local-mcp'
    source = [pscustomobject]@{ source = 'local'; path = './.codex/plugins/vitro-cad-local-mcp' }
    policy = [pscustomobject]@{ installation = 'AVAILABLE'; authentication = 'ON_INSTALL' }
    category = 'Productivity'
}
$marketplace.plugins = @($marketplace.plugins | Where-Object { $_.name -ne 'vitro-cad-local-mcp' }) + @($entry)
$utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList @($false)
[IO.File]::WriteAllText($marketplacePath, ($marketplace | ConvertTo-Json -Depth 12), $utf8NoBom)

}

$pluginInstalled = $false
if ($installCodex -and (Get-Command codex -ErrorAction SilentlyContinue)) {
    & codex plugin add "vitro-cad-local-mcp@$($marketplace.name)"
    $pluginInstalled = ($LASTEXITCODE -eq 0)
}

if ($installCodex -and -not $pluginInstalled) {
    # Codex Desktop can load a user MCP server and skill without the Codex CLI.
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $configPath) | Out-Null
    $config = if (Test-Path -LiteralPath $configPath) { Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 } else { '' }
    $config = [regex]::Replace($config, '(?ms)^# BEGIN vitro-cad-local-mcp MCP\r?\n.*?^# END vitro-cad-local-mcp MCP\r?\n?', '')
    if ($config -match '(?m)^\[mcp_servers\.vitro-cad-local(?:\.|\])') {
        $backupPath = '{0}.vitro-backup-{1}' -f $configPath, (Get-Date -Format 'yyyyMMddHHmmss')
        Copy-Item -LiteralPath $configPath -Destination $backupPath
        $config = [regex]::Replace($config, '(?ms)^\[mcp_servers\.vitro-cad-local(?:\.[^\]\r\n]+)?\]\r?\n.*?(?=^\[|\z)', '')
    }
    $tomlPython = ConvertTo-Json -InputObject $pythonPath -Compress
    $tomlServer = ConvertTo-Json -InputObject (Join-Path $destination 'server\mcp_server.py') -Compress
    $managed = @(
        '',
        '# BEGIN vitro-cad-local-mcp MCP',
        '[mcp_servers.vitro-cad-local]',
        ('command = ' + $tomlPython),
        ('args = [' + $tomlServer + ']'),
        '# END vitro-cad-local-mcp MCP',
        ''
    ) -join [Environment]::NewLine
    [IO.File]::WriteAllText($configPath, ($config.TrimEnd() + $managed), $utf8NoBom)
    if (Test-Path -LiteralPath $skillPath) {
        $marker = Join-Path $skillPath '.vitro-cad-local-mcp-managed'
        if (-not (Test-Path -LiteralPath $marker)) {
            $skillBackup = '{0}.backup-{1}' -f $skillPath, (Get-Date -Format 'yyyyMMddHHmmss')
            Move-Item -LiteralPath $skillPath -Destination $skillBackup
        }
    }
    New-Item -ItemType Directory -Force -Path $skillPath | Out-Null
    Copy-Item -Path (Join-Path $destination 'skills\vitro-cad\*') -Destination $skillPath -Recurse -Force
    New-Item -ItemType File -Force -Path (Join-Path $skillPath '.vitro-cad-local-mcp-managed') | Out-Null
    Write-Host 'Codex Desktop настроен для работы с Vitro-CAD.'
}
& $pythonPath (Join-Path $destination 'server\check_mcp.py') --check-login
if ($LASTEXITCODE -ne 0) { throw 'MCP-сервер не смог войти в Vitro-CAD. Установка не завершена.' }
$serverScript = Join-Path $destination 'server\mcp_server.py'
if ($installClaude) {
    if (-not (Get-Command claude -ErrorAction SilentlyContinue)) {
        throw 'Claude Code не найден в командной строке. Установите Claude Code и запустите установщик снова.'
    }
    & claude mcp add --scope user --transport stdio vitro-cad-local -- $pythonPath $serverScript
    if ($LASTEXITCODE -ne 0) {
        $existing = (& claude mcp get vitro-cad-local 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0 -or -not $existing.Contains($serverScript)) {
            throw 'Claude Code не принял подключение MCP. Проверьте его сообщение в этом окне.'
        }
    }
    Write-Host 'Claude Code подключён.'
}
if ($installQwen) {
    if (-not (Get-Command qwen -ErrorAction SilentlyContinue)) {
        throw 'Qwen Code не найден в командной строке. Установите Qwen Code и запустите установщик снова.'
    }
    & qwen mcp add --scope user vitro-cad-local $pythonPath $serverScript
    if ($LASTEXITCODE -ne 0) {
        $existing = (& qwen mcp list 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0 -or -not $existing.Contains($serverScript)) {
            throw 'Qwen Code не принял подключение MCP. Проверьте его сообщение в этом окне.'
        }
    }
    Write-Host 'Qwen Code подключён.'
}
$successMessage = @(
    'Вход в Vitro-CAD подтверждён. MCP-сервер установлен и проверен.'
    ''
    'Перезапустите выбранного агента и начните новую сессию.'
    'Для Codex Desktop завершите его также через значок у часов Windows.'
    'Попросите агента вызвать vitro_whoami.'
    'Для списка проектов может понадобиться GUID реестра вашего портала.'
) -join [Environment]::NewLine
Write-Host $successMessage
[System.Windows.Forms.MessageBox]::Show(
    $successMessage,
    'Vitro-CAD MCP',
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
) | Out-Null
