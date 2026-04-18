# Run the Item Data Agent API Server

Write-Host "Starting Item Data Agent API Server..." -ForegroundColor Cyan
Write-Host ""
Write-Host "API will be available at: http://localhost:8000" -ForegroundColor Green
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

uv run python -m item_data_agent.main
