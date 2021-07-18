$MyInvocation.MyCommand.Path | Split-Path | Push-Location
    # Invoke a Python script in PowerShell. $args[0] is
    # the name of the script and the the rest of the arges
    # are passed to the script.
    #
    # It acivates the virtual environment in ./venv
    #
    # Invoke with subprocess.Popen(["powershell.exe",
#                                   <path>/invok_powershell_venv.ps1,
#                                   prog_name])
.\venv\Scripts\activate.ps1
"arguments are" + $args
python $args[0]
"exiting"