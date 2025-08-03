import pexpect
import re
import logging as log
import os
import shutil
from typing import Optional, List

# Configure logging for better debugging
log.basicConfig(level=log.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class InteractiveShell:
    COMMON_PROMPT_PATTERNS = [
        r'\r?\n[^\S\r\n]*[\$%#>] ',  # Newline, optional leading whitespace, then $,%,#,> and a space
        r'\r?\n[^\S\r\n]*[\$%#>]',   # Newline, optional leading whitespace, then $,%,#,> (no space)
        r'[\$%#>] $'                 # $,%,#> at end of string with a space
    ]

    def __init__(self, shell_command: List[str], cwd: Optional[str] = None, prompt_patterns: Optional[List[str]] = None):
        self._shell_command_list = shell_command
        self.cwd = cwd
        self.child: Optional[pexpect.spawn] = None
        
        # Use provided prompt patterns or fall back to default patterns
        self.prompt_patterns = prompt_patterns if prompt_patterns is not None else self.COMMON_PROMPT_PATTERNS

    def start(self, timeout: float = 10):
        """Start the interactive shell process."""
        # Convert command list to single command string for pexpect
        command = ' '.join(self._shell_command_list)
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
        self._wait_for_prompt(initial_startup=True, timeout=timeout)
        log.info("Initial shell prompt detected.")

    def _wait_for_prompt(self, initial_startup: bool = False, timeout: float = 10) -> str:
        """Wait for a prompt-like pattern to appear."""
        if not self.child:
            raise RuntimeError("Shell not started")
            
        try:
            # Expect any of the prompt patterns
            index = self.child.expect(self.prompt_patterns, timeout=timeout)
            log.debug(f"Prompt pattern {index} matched: '{self.prompt_patterns[index]}'")
            
            # Return the output before the prompt
            output = self.child.before.decode('utf-8', errors='ignore') if self.child.before else ""
            return output.strip()
            
        except pexpect.TIMEOUT:
            log.error(f"Timeout waiting for prompt. Last output: {self.child.before}")
            raise TimeoutError(f"Timed out waiting for prompt after {timeout} seconds")
        except pexpect.EOF:
            log.error("Shell process terminated unexpectedly")
            raise RuntimeError("Shell process terminated unexpectedly")

    def run_command(self, command: str, timeout: float = 10) -> str:
        """Run a command and wait for prompt."""
        if not self.child or not self.child.isalive():
            raise RuntimeError("Shell not started or process has exited")
            
        log.info(f"Running command: '{command}'")
        
        # Send command
        self.child.sendline(command)
        
        # Wait for the prompt to reappear
        command_output = self._wait_for_prompt(timeout=timeout)
        
        # Post-processing: remove the echoed command from the output if it exists
        command_echo_pattern = re.escape(command) + r'\r?\n'
        match = re.search(command_echo_pattern, command_output)
        if match and match.start() == 0:
            cleaned_output = command_output[match.end():]
            return cleaned_output.strip()
        
        return command_output.strip()

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
