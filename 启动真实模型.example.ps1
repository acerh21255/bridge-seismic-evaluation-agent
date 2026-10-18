# 在自己的终端会话中填写这些环境变量，不要将真实密钥写入项目文件。
# 模型服务须兼容OpenAI工具调用协议；本项目不自动开户或购买服务。
$env:BRIDGE_AGENT_MODEL='填写模型名称'
$env:BRIDGE_AGENT_BASE_URL='填写模型服务API地址'
$credential=Read-Host '输入API key（不会显示或保存到项目文件）' -AsSecureString
$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential)
try {$env:BRIDGE_AGENT_API_KEY=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)}
finally {[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
# 使用新端口确保新服务继承当前环境；已运行的离线服务不会自动获得新变量。
& "$PSScriptRoot/Start-Demo.ps1" -Port 8770
