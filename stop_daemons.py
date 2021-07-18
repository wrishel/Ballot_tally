"""Signal the daemons for graceful shutdown."""

import GLB_globs
import inter_proc_signal

GLB = GLB_globs.GLB_globs()
inter_proc_signal.win_ip_signal(GLB.daemon_semaphore_path).set()
