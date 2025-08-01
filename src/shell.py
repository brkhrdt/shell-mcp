import asyncio
import subprocess # Still need this for Popen.DEVNULL etc.
import re
import logging as log
import os
import shutil # For shutil.which
from typing import Optional, List

# Configure logging for better debugging
log.basicConfig(level=log.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class GenericInteractiveShell:
    COMMON_PROMPT_PATTERNS = [
        r'\r?\n[^\S\r\n]*[\$%#>] ', # Newline, optional leading whitespace, then $,%,#,> and a space
        r'\r?\n[^\S\r\n]*[\$%#>]',   # Newline, optional leading whitespace, then $,%,#,> (no space)
        r'[\$%#>] $'                 # $,%,#> at end of string with a space
    ]

    def __init__(self, shell_command: str | List[str], cwd: Optional[str] = None, prompt_patterns: Optional[List[str]] = None):
        if isinstance(shell_command, str):
            # Use shlex.split for robust parsing of shell commands
            self._shell_command_list = shlex.split(shell_command)
        else:
            self._shell_command_list = shell_command

        self.cwd = cwd
        self.process: Optional[asyncio.Process] = None # Change type hint to asyncio.Process
        self._reader_task: Optional[asyncio.Task] = None
        self._output_buffer = ""
        self.prompt_detected = False 

        # Use provided prompt patterns or fall back to default patterns
        patterns = prompt_patterns if prompt_patterns is not None else self.COMMON_PROMPT_PATTERNS
        self._prompt_regexes = [re.compile(p, re.MULTILINE) for p in patterns]

    async def start(self):
        """Start the interactive shell process."""
        log.info(f"Starting generic shell with command '{' '.join(self._shell_command_list)}'")
        
        self.process = await asyncio.create_subprocess_exec( # <<< KEY CHANGE HERE
            *self._shell_command_list, # Unpack the list of command arguments
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT, # Direct stderr to stdout for simpler reading
            # text=True is the default for StreamReader/StreamWriter
            # bufsize is not directly applicable here as asyncio manages buffering
            cwd=self.cwd,
            # shell=False (default for create_subprocess_exec)
        )
        
        # Start reading output in background
        self._reader_task = asyncio.create_task(self._read_output())
        log.info("Shell process started.")
        
        # Wait for the initial prompt, which signifies the shell is ready
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
                # Read whatever is available. A small buffer size for readline/read is good
                # asyncio.StreamReader.read() with no argument reads until EOF.
                # Use read(n) to read up to n bytes, or readline() for lines.
                # For an interactive shell, readline() is often more appropriate for line-by-line processing
                # but since we're accumulating into a buffer for regex search, read(4096) is fine.
                data = await self.process.stdout.read(4096) # <<< KEY CHANGE HERE - directly await StreamReader.read()
                
                if not data: # EOF reached, process exited
                    log.info("Shell stdout stream closed (EOF). Reader stopping.")
                    break
                
                # Decode the bytes to text if not already handled by 'text=True'
                # asyncio.create_subprocess_exec does not have a 'text' argument for pipe decoding
                # You'd typically decode it here. However, by default, asyncio streams are byte streams.
                # To get 'text=True' behavior, you need to use `StreamReader.read(n).decode()`
                # OR use the higher-level `asyncio.StreamReader.readline()` or `asyncio.StreamReader.read()`
                # which implicitly decode if the 'protocol' is set up for text.
                # For simplicity, let's assume `data` is bytes and handle decoding.
                # If your shell outputs non-UTF-8, you'll need to specify encoding.
                
                # The issue is that Popen has 'text=True', but create_subprocess_exec's streams are bytes.
                # We need to explicitly decode.
                self._output_buffer += data.decode('utf-8', errors='ignore') # Decode to string
                
                log.debug(f"Buffer updated. Current buffer len: {len(self._output_buffer)}. New data: {repr(data.decode('utf-8', errors='ignore'))}")
                
        except asyncio.CancelledError:
            log.info("Reader task cancelled.")
        except Exception as e:
            if self.process and self.process.returncode is not None:
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
                raise TimeoutError(f"Timed out waiting for prompt after {timeout} seconds. Current buffer: {repr(self._output_buffer)}")

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
                self._output_buffer = self._output_buffer[match.start():]
                
                log.debug(f"Output before prompt:\n{repr(output_before_prompt)}")
                return output_before_prompt.strip()
            
            # If no prompt pattern found, wait a bit before checking again
            # Allow the _read_output task to populate the buffer
            await asyncio.sleep(0.05) 

    async def run_command(self, command: str, timeout: float = 10) -> str:
        """Run a command and wait for prompt."""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Shell not started or stdin not available.")
        if self.process.returncode is not None: # Check returncode for asyncio.Process
            raise RuntimeError(f"Shell process has exited with code {self.process.returncode}.")
            
        log.info(f"Running command: '{command}'")
        
        # Clear buffer *before* sending command to ensure we only capture this command's output
        self._output_buffer = "" 

        # Send command and flush (stdin.write expects bytes)
        self.process.stdin.write((command + "\n").encode('utf-8')) # Encode to bytes
        try:
            await self.process.stdin.drain() # Drain ensures the data is written
        except BrokenPipeError:
            log.error("Stdin pipe broken. Shell likely exited.")
            raise RuntimeError("Shell process exited prematurely.")
        
        # Wait for the prompt to reappear, signifying the command is done.
        command_output = await self._wait_for_prompt(timeout=timeout)
        
        # Post-processing: remove the echoed command from the output if it exists
        command_echo_pattern = re.escape(command) + r'\r?\n'
        match = re.search(command_echo_pattern, command_output)
        if match and match.start() == 0:
            cleaned_output = command_output[match.end():]
            return cleaned_output.strip()
        
        return command_output.strip()

    async def close(self):
        """Close the shell process."""
        log.info("Closing shell")
        if self.process and self.process.returncode is None: # Check if still running
            try:
                # Attempt graceful exit
                self.process.stdin.write(b"exit\n") # Send bytes
                await self.process.stdin.drain()
                # Give it a moment to exit gracefully
                await asyncio.wait_for(self.process.wait(), timeout=5) # Await process.wait()
            except BrokenPipeError:
                log.warning("Stdin pipe broken during exit, shell likely already exited.")
            except asyncio.TimeoutError:
                log.warning("Shell did not exit gracefully within timeout, terminating.")
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except Exception as e:
                log.error(f"Error during graceful shell exit: {e}")
            finally:
                if self.process.returncode is None: # If still running, kill
                    log.error("Shell still running after terminate, killing.")
                    self.process.kill()

        if self._reader_task:
            if not self._reader_task.done():
                self._reader_task.cancel()
                try:
                    await self._reader_task # Wait for it to actually cancel
                except asyncio.CancelledError:
                    log.info("Reader task successfully cancelled.")
                except Exception as e:
                    log.error(f"Error awaiting cancelled reader task: {e}")
            else:
                log.info("Reader task already done.")
        log.info("Shell closed")

# --- Example Usage ---
async def main():
    import shlex
    
    # Example 1: Linux/macOS Bash (requires bash in PATH)
    if os.name == 'posix':
        log.info("\n--- Running Generic Bash Example (asyncio.Process) ---")
        bash_path = shutil.which("bash")
        if bash_path:
            # Pass 'bash -i' to ensure it's interactive
            bash_shell = GenericInteractiveShell(shell_command=shlex.split(f"{bash_path} -i")) 
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
        else:
            log.error("Bash executable not found in PATH for POSIX example.")

    # Example 2: Windows Command Prompt (requires cmd.exe in PATH)
    if os.name == 'nt':
        log.info("\n--- Running Generic CMD.exe Example (asyncio.Process) ---")
        # For cmd.exe, just "cmd.exe" usually starts an interactive session.
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

if __name__ == "__main__":
    import shutil # For shutil.which
    asyncio.run(main())
