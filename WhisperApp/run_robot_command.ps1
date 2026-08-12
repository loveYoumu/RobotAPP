$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
python "$Root\transcribe_robot_command.py" @args
