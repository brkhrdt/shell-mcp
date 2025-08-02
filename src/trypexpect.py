import sys
import pexpect

# Spawn a new shell process
child = pexpect.spawn('tclsh')

# Expect a prompt from the shell
child.expect('%')

# Send the first command and expect the prompt again
child.sendline('expr 3+2')
child.expect('%')

# Print the output from the first command
print(child.before.decode())

# Send a second command and expect the prompt
child.sendline('sleep 5')
child.expect('%')

# Print the output from the second command
print(child.before.decode())

# Close the child process
child.close()

# Print the exit code
print(f"\nShell exited with code: {child.exitstatus}")
