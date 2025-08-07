import pexpect
import logging as log
from typing import Optional, List, NamedTuple
import time


# Configure logging for better debugging
log.basicConfig(level=log.DEBUG, format="%(asctime)s][SHELL]%(levelname)s- %(message)s")


class CommandHistoryEntry(NamedTuple):
    command: str
    output: str
    full_output: str
    timestamp: float


class InteractiveShell:
    def __init__(
        self,
        shell_command: List[str],
        cwd: Optional[str] = None,
    ):
        self._shell_command_list = shell_command
        self.cwd = cwd
        self.child: Optional[pexpect.spawn] = None

        # Initialize command history
        self.command_history: List[CommandHistoryEntry] = []
        # Buffer to hold current output that hasn't been "consumed" by a command
        self._current_buffer_content: str = ""

    def start(self, timeout: float = 1):
        """Start the interactive shell process."""
        # Convert command list to single command string for pexpect
        command = " ".join(self._shell_command_list)
        log.info(f"Starting shell with command '{command}'")

        try:
            # Set a very short timeout for spawn itself, as we'll manage read timeouts later
            self.child = pexpect.spawn(command, cwd=self.cwd, timeout=timeout)

            # Check if process started successfully
            if not self.child.isalive():
                raise RuntimeError("Failed to start shell process")

            # Read any initial prompt/output
            initial_output = self._read_available_output(timeout=0.1)
            self._current_buffer_content += initial_output

        except Exception as e:
            log.error(f"Error starting shell process: {e}")
            raise RuntimeError(f"Could not start shell process: {e}")

        log.info("Shell process started.")

    def _read_available_output(self, timeout: float = 1, consume: bool = True) -> str:
        """
        Reads all available output from the child process until a timeout occurs.
        If consume is False, it reads non-blockingly for a very short duration
        and does not wait for the full timeout, intended for peeking.
        """
        if not self.child:
            raise RuntimeError("Shell not started")

        accumulated_output = ""
        start_time = time.time()
        read_timeout = (
            timeout if consume else 0.05
        )  # Shorter timeout for non-consuming reads

        log.debug(
            f"Reading output for up to {read_timeout} seconds (consume={consume})..."
        )

        while True:
            try:
                # Read up to 64KB of available data
                data = self.child.read_nonblocking(
                    size=65536, timeout=0.01
                )  # Very short internal timeout
                if data:
                    accumulated_output += data.decode("utf-8", errors="replace")
                    log.debug(
                        f"Read {len(data)} bytes. Total: {len(accumulated_output)} bytes."
                    )
                else:
                    # No data immediately available, check if timeout elapsed
                    if time.time() - start_time > read_timeout:
                        log.debug(f"Timeout reached after {read_timeout} seconds.")
                        break
                    # Small sleep to prevent busy-waiting if no data is available
                    time.sleep(0.01)

            except pexpect.TIMEOUT:
                # This timeout is from read_nonblocking, meaning no data was available within its internal timeout
                if time.time() - start_time > read_timeout:
                    log.debug(
                        f"Timeout reached after {read_timeout} seconds (pexpect.TIMEOUT)."
                    )
                    break
                time.sleep(0.01)  # Still sleep to prevent busy-waiting
            except pexpect.EOF:
                log.warning("Shell process terminated unexpectedly (EOF during read).")
                accumulated_output += "\n[Shell process terminated unexpectedly]"
                break
            except Exception as e:
                log.error(f"Error during output reading: {e}")
                accumulated_output += f"\n[Error reading output: {e}]"
                break

            if time.time() - start_time > read_timeout:
                log.debug(f"Timeout reached after {read_timeout} seconds (loop end).")
                break

        log.debug(f"Finished reading. Total output length: {len(accumulated_output)}")
        return accumulated_output

    def run_command(self, command: str, timeout: float = 1) -> str:
        """Run a command and return the complete output after a timeout."""
        if not self.child or not self.child.isalive():
            raise RuntimeError("Shell not started or process has exited")

        log.info(f"Running command: '{command}'")

        # Clear the current buffer content before sending a new command
        # This ensures _current_buffer_content only holds output relevant to the *last* command
        self._current_buffer_content = ""

        # Send command
        self.child.sendline(command)

        # Read output until timeout, consuming it
        command_output = self._read_available_output(timeout=timeout, consume=True)
        self._current_buffer_content = (
            command_output.strip()
        )  # Store the full output of this command

        # The full output is simply what was accumulated
        full_output = self._current_buffer_content

        # Record the command in history
        timestamp = time.time()
        history_entry = CommandHistoryEntry(
            command=command,
            output=command_output,  # The raw output
            full_output=full_output,
            timestamp=timestamp,
        )
        self.command_history.append(history_entry)

        log.debug(f"OUTPUT: {full_output}")
        return full_output

    def peek_buffer(self, n_lines: int = 10) -> str:
        """
        Reads any new available output and returns the last n_lines of the accumulated buffer.
        """
        if not self.child or not self.child.isalive():
            return "[Shell not active]"

        # Read any new data that might have appeared since the last operation, without consuming it
        new_data = self._read_available_output(timeout=0.05, consume=False)
        self._current_buffer_content += new_data.strip()

        if not self._current_buffer_content:
            return "[Buffer is empty]"

        lines = self._current_buffer_content.splitlines()
        if len(lines) <= n_lines:
            return "\n".join(lines)
        else:
            return "\n".join(lines[-n_lines:])

    def get_command_history(self) -> List[CommandHistoryEntry]:
        """Get the complete command history in chronological order."""
        return self.command_history.copy()

    def get_last_command(self) -> Optional[CommandHistoryEntry]:
        """Get the most recently executed command and its output."""
        return self.command_history[-1] if self.command_history else None

    def clear_history(self) -> None:
        """Clear the command history."""
        self.command_history.clear()

    def close(self, exit_command: str = "exit"):
        """Close the shell process."""
        log.info("Closing shell")
        if self.child and self.child.isalive():
            try:
                # Attempt graceful exit
                self.child.sendline(exit_command)
                # Wait for EOF, indicating the process has exited
                self.child.expect(pexpect.EOF, timeout=1)
            except pexpect.TIMEOUT:
                log.warning(
                    "Shell did not exit gracefully within timeout, terminating."
                )
                self.child.terminate()
            except Exception as e:
                log.error(f"Error during graceful shell exit: {e}")
                if self.child.isalive():
                    self.child.terminate()
        log.info("Shell closed")
