# Interactive Shell Management

This project provides tools for managing interactive shell sessions.

## Why pexpect?

`pexpect` is used in this project primarily because it provides **pseudo-terminal (PTY) emulation**.
This is crucial for interacting with command-line applications that behave differently when run interactively
versus non-interactively. Many shell commands and interactive programs require a PTY to function
correctly, display color output, handle prompts, or manage buffering as a human user would expect.
While `asyncio.subprocess.exec` can run external processes, it does not provide a PTY, making
`pexpect` the more suitable tool for simulating a user's interaction with a terminal.
