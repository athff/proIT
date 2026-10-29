$python = 'e:\proIT\.venv\Scripts\python.exe'
$command = '-m django test people --verbosity 2'
Write-Host "Running: $python $command"
& $python $command
Write-Host "Complete"