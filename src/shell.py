import pexpect
import re
import logging as log
import os
import shutil
from typing import Optional, List, NamedTuple
import time


# Configure logging for better debugging
log.basicConfig(level=log.ERROR, format="%(asctime)s][SHELL]%(levelname)s- %(message)s")


class InteractiveShell:
    COMMON_PROMPT_PATTERNS = [
        r"\r?\n[^\S\r\n]*[\$%#>] ",  # Newline, optional leading whitespace, then $,%,#,> and a space
        r"\r?\n[^\S\r\n]*[\$%#>]",  # Newline, optional leading whitespace, then $,%,#,> (no space)
        r"[\$%#>] $",  # $,%,#> at end of string with a space
        r"\r?\n>>>\s",  # $,%,#> at end of string with a space
    ]

    def __init__(
        self,
        shell_command: List[str],
        cwd: Optional[str] = None,
        prompt_patterns: Optional[List[str]] = None,
    ):
        self._shell_command_list = shell_command
        self.cwd = cwd
        self.child: Optional[pexpect.spawn] = None

        # Use provided prompt patterns or fall back to default patterns
        self.prompt_patterns = (
            prompt_patterns
            if prompt_patterns is not None
            else self.COMMON_PROMPT_PATTERNS
        )

        # Initialize command history
        self.command_history: List["InteractiveShell.CommandHistoryEntry"] = []

    class CommandHistoryEntry(NamedTuple):
        command: str
        output: str
        full_output: str
        timestamp: float

    def start(self, timeout: float = 10):
        """Start the interactive shell process."""
        # Convert command list to single command string for pexpect
        command = " ".join(self._shell_command_list)
        log.info(f"Starting shell with command '{command}'")

        try:
            self.child = pexpect.spawn(command, cwd=self.cwd, timeout=timeout)

            # Check if process started successfully
            if not self.child.isalive():
                raise RuntimeError(f"Failed to start shell process")

        except Exception as e:
            log.error(f"Error starting shell process: {e}")
            raise RuntimeError(f"Could not start shell process: {e}")

        log.info("Shell process started.")

        # Wait for the initial prompt
        _, _ = self._wait_for_prompt(initial_startup=True, timeout=timeout)
        log.info("Initial shell prompt detected.")

    def _wait_for_prompt(
        self, initial_startup: bool = False, timeout: float = 10
    ) -> tuple[str, str]:
        """Wait for a prompt-like pattern to appear. Returns (output, matched_prompt)."""
        if not self.child:
            raise RuntimeError("Shell not started")

        log.debug("Waiting for prompt...")
        try:
            # Expect any of the prompt patterns
            index = self.child.expect(self.prompt_patterns, timeout=timeout)
            log.debug(
                f"Prompt pattern {index} matched: '{self.prompt_patterns[index]}'"
            )

            # Get the output before the prompt
            output = (
                self.child.before.decode("utf-8", errors="ignore")
                if self.child.before
                else ""
            )

            # Get the matched prompt
            matched_prompt = (
                self.child.after.decode("utf-8", errors="ignore")
                if self.child.after
                else ""
            )

            return output.strip(), matched_prompt

        except pexpect.TIMEOUT:
            log.error(f"Timeout waiting for prompt. Last output: {self.child.before}")
            raise TimeoutError(f"Timed out waiting for prompt after {timeout} seconds")
        except pexpect.EOF:
            log.error("Shell process terminated unexpectedly")
            raise RuntimeError("Shell process terminated unexpectedly")

    def run_command(self, command: str, timeout: float = 10) -> str:
        """Run a command and return the complete output including prompt and command."""
        if not self.child or not self.child.isalive():
            raise RuntimeError("Shell not started or process has exited")

        if command[-1] != "\n":
            log.warning("Command does not end with newline. Appending it")
            command += "\n"
        log.info(f"Running command: '{command}'")

        # Send command
        self.child.sendline(command)

        # Wait for the prompt to reappear
        command_output, matched_prompt = self._wait_for_prompt(timeout=timeout)

        # The full output includes everything: command output + the prompt
        full_output = matched_prompt + command_output

        # For history, separate the command from its actual output
        # Remove the echoed command from the output for the history entry
        command_echo_pattern = re.escape(command) + r"\r?\n"
        match = re.search(command_echo_pattern, command_output)
        if match and match.start() == 0:
            cleaned_output = command_output[match.end() :]
        else:
            cleaned_output = command_output

        # Record the command in history with separated command and output
        timestamp = time.time()
        history_entry = self.CommandHistoryEntry(
            command=command,
            output=cleaned_output.strip(),
            full_output=full_output,
            timestamp=timestamp,
        )
        self.command_history.append(history_entry)

        # Return the complete output including prompt and command
        log.debug(f"OUTPUT: {full_output}")
        return full_output

    def get_command_history(self) -> List["InteractiveShell.CommandHistoryEntry"]:
        """Get the complete command history in chronological order."""
        return self.command_history.copy()

    def get_last_command(self) -> Optional["InteractiveShell.CommandHistoryEntry"]:
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
                self.child.expect(pexpect.EOF, timeout=5)
            except pexpect.TIMEOUT:
                log.warning("Shell did not exit gracefully, terminating")
                self.child.terminate()
            except Exception as e:
                log.error(f"Error during graceful shell exit: {e}")
                if self.child.isalive():
                    self.child.terminate()
        log.info("Shell closed")
