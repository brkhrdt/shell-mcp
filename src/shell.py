import pexpect
import logging as log
from typing import Optional, List
import time
import re


# Configure logging for better debugging
log.basicConfig(level=log.DEBUG, format="%(asctime)s][SHELL]%(levelname)s- %(message)s")

# ANSI escape code pattern (from https://stackoverflow.com/questions/14693701/how-can-i-remove-the-ansi-escape-sequences-from-a-string-in-python)
# This regex matches common ANSI escape sequences.
ANSI_ESCAPE_PATTERN = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


class InteractiveShell:
    def __init__(
        self,
        shell_command: List[str],
        cwd: Optional[str] = None,
    ):
        self._shell_command_list = shell_command
        self.cwd = cwd
        self.child: Optional[pexpect.spawn] = None

        # Buffer to hold ALL output from the shell session
        self._full_session_buffer: str = ""

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
            self._full_session_buffer += initial_output  # Append to the full buffer

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
                    decoded_data = data.decode("utf-8", errors="replace")
                    # Strip ANSI escape codes from the decoded data
                    cleaned_data = ANSI_ESCAPE_PATTERN.sub('', decoded_data)

                    accumulated_output += cleaned_data
                    if consume:  # Only append to full buffer if consuming
                        self._full_session_buffer += cleaned_data
                    log.debug(
                        f"Read {len(data)} bytes. Cleaned: {len(cleaned_data)} bytes. Total: {len(accumulated_output)} bytes."
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
                eof_message = "\n[Shell process terminated unexpectedly]"
                # Clean EOF message as well
                cleaned_eof_message = ANSI_ESCAPE_PATTERN.sub('', eof_message)
                accumulated_output += cleaned_eof_message
                if consume:  # Only append to full buffer if consuming
                    self._full_session_buffer += cleaned_eof_message
                break
            except Exception as e:
                log.error(f"Error during output reading: {e}")
                error_message = f"\n[Error reading output: {e}]"
                # Clean error message as well
                cleaned_error_message = ANSI_ESCAPE_PATTERN.sub('', error_message)
                accumulated_output += cleaned_error_message
                if consume:  # Only append to full buffer if consuming
                    self._full_session_buffer += cleaned_error_message
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

        # Send command
        self.child.sendline(command)

        # Read output until timeout, consuming it. The output is automatically added to _full_session_buffer
        command_output = self._read_available_output(timeout=timeout, consume=True)

        # The full output for this specific command is what was just read
        return command_output.strip()

    def peek_buffer(self, n_lines: int = 10) -> str:
        """
        Reads any new available output and returns the last n_lines of the accumulated buffer.
        """
        if not self.child or not self.child.isalive():
            return "[Shell not active]"

        # Read any new data that might have appeared since the last operation.
        # This data will be automatically appended to _full_session_buffer by _read_available_output
        self._read_available_output(timeout=0.05, consume=True)

        if not self._full_session_buffer:
            return "[Buffer is empty]"

        lines = self._full_session_buffer.splitlines()
        if len(lines) <= n_lines:
            return "\n".join(lines)
        else:
            return "\n".join(lines[-n_lines:])

    def close(self, exit_command: str = "exit"):
        """Close the shell process."""
        log.info("Closing shell")
        if self.child and self.child.isalive():
            try:
                # Attempt graceful exit
                self.child.sendline(exit_command)
                # Wait for EOF, indicating the process has exited
                self.child.expect(pexpect.EOF, timeout=1)
                # Read any remaining output before closing
                self._read_available_output(timeout=0.1, consume=True)
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

