controlled shutdown for Windows

###Problem
 
Graceful shutdown with control-c does not work for Windows.
 
###Solution

A file name is used as a semaphore. Daemons 
check if it is present and shutdown if so.

###Class win_ip_signal 
####Init(file path)
saves file path
####clear()
If the file is present, deletes it. No return.
####exists()
If the file is present return true.
####set()
Creates and empty file at the path location.

###Protocol for Daemons in this project
- All daemons clear the semaphore on startup.
- All daemons check it at a safe place to stop.
- A utility exists solely to shut down. It sets the semaphore
