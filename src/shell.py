import asyncio
import subprocess
import re
import logging as log
from typing import Optional

class InteractiveShell:
    def __init__(self, command: str, prompt: str, cwd: Optional[str] = None):
        self.command = command
        self.prompt = prompt
        self.cwd = cwd
        self.process: Optional[subprocess.Popen] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._output_buffer = ""
        
    async def start(self):
        """Start the interactive shell process."""
        log.info(f"Starting shell with command '{self.command}'")
        self.process = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=self.cwd,
            shell=True
        )
        
        # Start reading output in background
        self._reader_task = asyncio.create_task(self._read_output())
        log.info("Shell started successfully")
        
    async def _read_output(self):
        """Background task to read process output."""
        if not self.process:
            return
            
        while True:
            try:
                # Read all available data, not just one line
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self.process.stdout.read, 1
                )
                if not data:
                    break
                self._output_buffer += data
                log.debug(f"Received data: {repr(data)}")
            except Exception as e:
                log.debug(f"Error reading output: {e}")
                break
                
    async def run_command(self, command: str) -> str:
        """Run a command and wait for prompt."""
        if not self.process:
            raise RuntimeError("Shell not started")
            
        log.info(f"Running command: '{command}'")
        
        # Send command
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        
        # Wait for prompt
        while True:
            # Use regex search instead of string matching
            if re.search(self.prompt, self._output_buffer):
                # Extract output up to and including the prompt
                lines = self._output_buffer.split('\n')
                result_lines = []
                for line in lines:
                    result_lines.append(line)
                    if re.search(self.prompt, line):
                        break
                output = '\n'.join(result_lines)
                # Remove from buffer
                self._output_buffer = self._output_buffer[len(output):]
                log.debug(f"Command output: {repr(output)}")
                return output
                
            # Small delay to prevent busy waiting
            await asyncio.sleep(0.01)
            
    async def close(self):
        """Close the shell process."""
        log.info("Closing shell")
        if self.process:
            self.process.stdin.write("exit\n")
            self.process.stdin.flush()
            self.process.wait()
            
        if self._reader_task:
            self._reader_task.cancel()
        log.info("Shell closed")
