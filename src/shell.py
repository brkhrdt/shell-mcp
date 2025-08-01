import asyncio
import subprocess
import re
import logging as log
import os
from typing import Optional

# Configure logging for better debugging
log.basicConfig(level=log.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class GenericInteractiveShell:
    # A list of common prompt patterns to try and detect.
    # These are regex patterns. More specific ones first.
    # (r'\$ $'): Matches "$ " at the end of a line (common bash/sh)
    # (r'# $'): Matches "# " at the end of a line (common root/sh)
    # (r'> $'): Matches "> " at the end of a line (common cmd.exe, PowerShell)
    # (r'^\s*[\$%#>]'): Matches a line starting with whitespace, then $, %, #, or >
    # This is a less reliable heuristic than setting a custom prompt,
    # but more general.
    COMMON_PROMPT_PATTERNS = [
        r'\r?\n[^\S\r\n]*[\$%#>] ', # Newline, optional leading whitespace, then $,%,#,> and a space
        r'\r?\n[^\S\r\n]*[\$%#>]',   # Newline, optional leading whitespace, then $,%,#,> (no space)
        r'[\$%#>] $'                 # $,%,#> at end of string with a space
    ]

    def __init__(self, shell_command: str, cwd: Optional[str] = None):
        """
        Initializes the generic interactive shell.
        
        Args:
            shell_command: The exact command to start the interactive shell (e.g., "bash", "cmd.exe").
                           This command *must* start an interactive, persistent shell.
            cwd: The working directory for the shell process.
        """
        self.shell_command = shell_command
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._output_buffer = ""
        self.prompt_detected = False # Flag to indicate if a prompt has been seen

        # Pre-compile regex patterns for efficiency
        self._prompt_regexes = [re.compile(p, re.MULTILINE) for p in self.COMMON_PROMPT_PATTERNS]

    async def start(self):
        """Start the interactive shell process."""
        log.info(f"Starting generic shell with command '{self.shell_command}'")
        
        # Ensure the command is split if it's a single string (e.g., "bash -i")
        # Popen's first argument should be a list for better security and clarity.
        # However, for 'shell=False' the command itself must be executable.
        # If 'shell_command' is meant to be a simple executable name (like 'bash' or 'cmd.exe'),
        # it's fine. If it's something like "bash -i", it must be split.
        if isinstance(self.shell_command, str):
            cmd_list = self.shell_command.split() # Simple split, might need shlex.split for complex args
        else:
            cmd_list = self.shell_command

        self.process = subprocess.Popen(
            cmd_list,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Direct stderr to stdout for simpler reading
            text=True,
            bufsize=1, # Line-buffered output for better responsiveness
            cwd=self.cwd,
            # shell=False (default): Essential for directly controlling the specific shell executable
            # and avoiding an intermediate shell that might exit.
        )
        
        # Start reading output in background
        self._reader_task = asyncio.create_task(self._read_output())
        log.info("Shell process started.")
        
        # Wait for the initial prompt, which signifies the shell is ready
        # This will consume initial messages and leave the buffer ready for commands.
        await self._wait_for_prompt(initial_startup=True)
        self.prompt_detected = True
        log.info("Initial shell prompt or readiness detected.")
        
    async def _read_output(self):
        """Background task to read process output."""
        if not self.process or not self.process.stdout:
            log.error("Process or stdout not available for reading.")
            return
            
        try:
            while True:
                # Read a small chunk of data. Use process.stdout.read(1) for maximum responsiveness
                # This will block the executor thread until 1 char is available or EOF.
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdout.read, 1
                )
                
                if not data: # EOF reached, process exited
                    log.info("Shell stdout stream closed (EOF). Reader stopping.")
                    break
                
                self._output_buffer += data
                log.debug(f"Buffer updated. Current buffer len: {len(self._output_buffer)}. New data: {repr(data)}")
                
        except Exception as e:
            # Handle cases where the process might terminate unexpectedly
            if self.process and self.process.poll() is not None:
                log.info(f"Shell process terminated while reading: {e}")
            else:
                log.error(f"Error reading output: {e}")

    async def _wait_for_prompt(self, timeout: float = 10, initial_startup: bool = False) -> str:
        """
        Waits for a prompt-like pattern to appear in the output buffer.
        Returns the output collected until the assumed prompt.
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # Check for timeout
            if asyncio.get_event_loop().time() - start_time > timeout:
                log.error(f"Timeout waiting for prompt pattern. Last 500 chars of buffer:\n{repr(self._output_buffer[-500:])}")
                raise TimeoutError(f"Timed out waiting for prompt after {timeout} seconds.")

            # Attempt to find a prompt pattern
            match = None
            for regex in self._prompt_regexes:
                match = regex.search(self._output_buffer)
                if match:
                    log.debug(f"Prompt pattern '{regex.pattern}' matched.")
                    break
            
            if match:
                # Extract output up to the point where the prompt was detected
                output_before_prompt = self._output_buffer[:match.start()]
                
                # Update buffer: remove the processed output up to the prompt's start
                # We keep the prompt itself in the buffer for the next _wait_for_prompt to catch
                # if it's a persistent prompt.
                self._output_buffer = self._output_buffer[match.start():]
                
                log.debug(f"Output before prompt:\n{repr(output_before_prompt)}")
                return output_before_prompt.strip()
            
            # If no prompt pattern found, wait a bit before checking again
            await asyncio.sleep(0.05) 

    async def run_command(self, command: str, timeout: float = 10) -> str:
        """Run a command and wait for prompt."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Shell not started or stdin not available.")
        if self.process.poll() is not None:
            raise RuntimeError("Shell process has exited.")
            
        log.info(f"Running command: '{command}'")
        
        # Clear buffer *before* sending command to ensure we only capture this command's output
        self._output_buffer = "" 

        # Send command and flush
        self.process.stdin.write(command + "\n")
        try:
            self.process.stdin.flush()
        except BrokenPipeError:
            log.error("Stdin pipe broken. Shell likely exited.")
            raise RuntimeError("Shell process exited prematurely.")
        
        # Wait for the prompt to reappear, signifying the command is done.
        # This function will return the output *before* the prompt.
        command_output = await self._wait_for_prompt(timeout=timeout)
        
        # Post-processing: remove the echoed command from the output if it exists
        # This is a common behavior of interactive shells.
        command_echo_pattern = re.escape(command) + r'\r?\n'
        match = re.search(command_echo_pattern, command_output)
        if match and match.start() == 0: # Ensure it's at the beginning of the collected output
            # Strip the echoed command from the output
            cleaned_output = command_output[match.end():]
            return cleaned_output.strip()
        
        return command_output.strip()

    async def close(self):
        """Close the shell process."""
        log.info("Closing shell")
        if self.process and self.process.poll() is None:
            try:
                # Attempt graceful exit
                self.process.stdin.write("exit\n")
                self.process.stdin.flush()
                # Give it a moment to exit gracefully
                await asyncio.get_event_loop().run_in_executor(
                    None, self.process.wait, 5 # Wait up to 5 seconds
                )
            except BrokenPipeError:
                log.warning("Stdin pipe broken during exit, shell likely already exited.")
            except Exception as e:
                log.error(f"Error during graceful shell exit: {e}")
            finally:
                if self.process.poll() is None: # If still running, force terminate
                    log.warning("Shell did not exit gracefully, terminating.")
                    self.process.terminate()
                    await asyncio.get_event_loop().run_in_executor(
                        None, self.process.wait, 5
                    )
                if self.process.poll() is None: # If still running, kill
                    log.error("Shell still running after terminate, killing.")
                    self.process.kill()

        if self._reader_task:
            if not self._reader_task.done():
                self._reader_task.cancel()
                try:
                    await self._reader_task # Wait for it to actually cancel
                except asyncio.CancelledError:
                    pass
        log.info("Shell closed")

# --- Example Usage ---
async def main():
    # Example 1: Linux/macOS Bash (requires bash in PATH)
    if os.name == 'posix':
        log.info("\n--- Running Generic Bash Example ---")
        # Ensure 'bash' starts an interactive session. Sometimes 'sh' is symlinked.
        # If 'bash' doesn't work, try a full path like '/bin/bash' or adjust.
        shell_cmd = "bash"
        if not os.path.exists("/bin/bash") and shutil.which("bash"): # check if bash exists
            shell_cmd = shutil.which("bash")

        bash_shell = GenericInteractiveShell(shell_command=shell_cmd)
        try:
            await bash_shell.start()
            
            log.info("\n--- Testing 'pwd' ---")
            pwd_output = await bash_shell.run_command("pwd")
            log.info(f"PWD Output: '{pwd_output}'")

            log.info("\n--- Testing 'echo hello world' ---")
            output1 = await bash_shell.run_command("echo hello world")
            log.info(f"Echo Output: '{output1}'")

            log.info("\n--- Testing 'ls -l /tmp' ---")
            ls_output = await bash_shell.run_command("ls -l /tmp")
            log.info(f"LS Output:\n{ls_output}")

        except TimeoutError as te:
            log.error(f"Operation timed out: {te}")
        except RuntimeError as re:
            log.error(f"Runtime error: {re}")
        except Exception as e:
            log.error(f"An unexpected error occurred: {e}", exc_info=True)
        finally:
            await bash_shell.close()

    # Example 2: Windows Command Prompt (requires cmd.exe in PATH)
    if os.name == 'nt':
        log.info("\n--- Running Generic CMD.exe Example ---")
        cmd_shell = GenericInteractiveShell(shell_command="cmd.exe")
        try:
            await cmd_shell.start()

            log.info("\n--- Testing 'echo hello world' (Windows) ---")
            output_win1 = await cmd_shell.run_command("echo hello world")
            log.info(f"Echo Output (Win): '{output_win1}'")

            log.info("\n--- Testing 'dir' (Windows) ---")
            dir_output = await cmd_shell.run_command("dir")
            log.info(f"DIR Output (Win):\n{dir_output}")

            log.info("\n--- Testing 'set USERNAME' (Windows environment var) ---")
            set_output = await cmd_shell.run_command("set USERNAME")
            log.info(f"SET USERNAME Output (Win): '{set_output}'")


        except TimeoutError as te:
            log.error(f"Operation timed out: {te}")
        except RuntimeError as re:
            log.error(f"Runtime error: {re}")
        except Exception as e:
            log.error(f"An unexpected error occurred: {e}", exc_info=True)
        finally:
            await cmd_shell.close()

    # Example 3: If you have Python installed and callable as 'python'
    # This often doesn't give a "prompt" in the same way, but shows how you'd interact
    # with a non-shell interactive process.
    # log.info("\n--- Running Generic Python Interpreter Example ---")
    # try:
    #     # Python interactive interpreter
    #     python_shell = GenericInteractiveShell(shell_command="python")
    #     await python_shell.start() # Will wait for >>> prompt
    #     
    #     print_output = await python_shell.run_command("print('Hello from Python interpreter!')")
    #     log.info(f"Python print output: '{print_output}'")

    #     eval_output = await python_shell.run_command("1 + 1")
    #     log.info(f"Python eval output: '{eval_output}'")
    #     
    # finally:
    #     await python_shell.close()


if __name__ == "__main__":
    import shutil # For shutil.which
    asyncio.run(main())
