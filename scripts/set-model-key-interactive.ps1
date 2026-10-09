param([Parameter(Mandatory=$true)][string]$BaseUrl)
$ErrorActionPreference = 'Stop'
if ($BaseUrl -notmatch '^https://[a-zA-Z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com/compatible-mode/v1/?$') { throw 'Expected the verified Beijing workspace Base URL.' }
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$repoDirectory = Split-Path $PSScriptRoot -Parent
$configPath = Join-Path $repoDirectory '.env.local'
$form = New-Object Windows.Forms.Form
$form.Text = 'Shopkeeper - secure Model Studio configuration'
$form.Size = New-Object Drawing.Size(760,300)
$form.StartPosition = 'CenterScreen'
$form.TopMost = $true
$label = New-Object Windows.Forms.Label
$label.Location = New-Object Drawing.Point(18,15)
$label.Size = New-Object Drawing.Size(710,100)
$label.Text = "Enter the NEW API Key below (hidden; never logged).`r`nEndpoint: $BaseUrl`r`nModels: qwen-plus / qwen3-vl-plus`r`nFile: $configPath"
$inputBox = New-Object Windows.Forms.TextBox
$inputBox.Location = New-Object Drawing.Point(18,120)
$inputBox.Size = New-Object Drawing.Size(700,28)
$inputBox.UseSystemPasswordChar = $true
$button = New-Object Windows.Forms.Button
$button.Text = 'Save securely'
$button.Location = New-Object Drawing.Point(18,165)
$button.Size = New-Object Drawing.Size(180,36)
$statusLabel = New-Object Windows.Forms.Label
$statusLabel.Location = New-Object Drawing.Point(18,210)
$statusLabel.Size = New-Object Drawing.Size(710,35)
$button.Add_Click({
    try {
        $keyValue = $inputBox.Text.Trim()
        if ([string]::IsNullOrWhiteSpace($keyValue) -or $keyValue -match "[^\x21-\x7E]|'") { throw 'Invalid key format' }
        $configText = [IO.File]::ReadAllText($configPath)
        $entries = [ordered]@{
            MODEL_CONFIG_SOURCE='file'; OPENAI_API_BASE=$BaseUrl.TrimEnd('/'); OPENAI_BASE_URL=$BaseUrl.TrimEnd('/')
            OPENAI_API_KEY=$keyValue; LLM_DEFAULT_MODEL='qwen-plus'; MODEL='qwen-plus'; ITEM_MODEL='qwen-plus'; VL_MODEL='qwen3-vl-plus'
        }
        foreach ($entry in $entries.GetEnumerator()) {
            $lineValue = $entry.Key + "='" + $entry.Value + "'"
            $matcher = [regex]('(?m)^' + [regex]::Escape($entry.Key) + '=.*$')
            if ($matcher.IsMatch($configText)) {
                $configText = $matcher.Replace($configText, [Text.RegularExpressions.MatchEvaluator]{param($match) $lineValue})
            } else { $configText = $configText.TrimEnd() + "`r`n" + $lineValue + "`r`n" }
        }
        $tempPath = $configPath + '.pending'
        [IO.File]::WriteAllText($tempPath,$configText,(New-Object Text.UTF8Encoding($false)))
        if ([IO.File]::ReadAllText($tempPath) -cne $configText) { throw 'Local write verification failed' }
        Move-Item -LiteralPath $tempPath -Destination $configPath -Force
        $receipt = @{status='saved'; saved_at=[DateTime]::UtcNow.ToString('o'); config_file=$configPath; models=@('qwen-plus','qwen3-vl-plus')}
        $receipt | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $repoDirectory 'data/model-config-receipt.json') -Encoding UTF8
        $inputBox.Clear(); $inputBox.Enabled=$false; $button.Enabled=$false
        $statusLabel.Text='Saved and verified. You can close this window; validation continues automatically.'
        $form.TopMost=$false
    } catch { $statusLabel.Text='Save failed. Paste the ASCII API Key without quotes/spaces, then retry. Check local file access.' }
    finally { $keyValue=$null; $configText=$null; $lineValue=$null; $entries=$null }
})
$form.Controls.AddRange(@($label,$inputBox,$button,$statusLabel))
$form.AcceptButton=$button
[void]$form.ShowDialog()
