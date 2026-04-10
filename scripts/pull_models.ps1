$models = @(
    "deepseek-r1:8b",
    "mistral:7b"
)

foreach ($model in $models) {
    Write-Host "Pulling $model"
    ollama pull $model
}
