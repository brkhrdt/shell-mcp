import subprocess
import asyncio
import logging as log
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("tcl")

# Global variable to store the persistent tclsh process
_tcl_process = None

@mcp.tool()
async def run_tcl(command: str) -> str:
    """Execute a Tcl command in a persistent Tcl shell.
    
    Args:
        command: Tcl command to execute
        
    Returns:
        Command output or error message
    """
    global _tcl_process
    
    log.debug(f"Executing Tcl command: {command}")
    
    try:
        # Start tclsh process if not already running
        if _tcl_process is None:
            log.debug("Starting new tclsh process")
            _tcl_process = subprocess.Popen(
                ["tclsh"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Redirect stderr to stdout
                text=True,
                bufsize=1
            )
        
        # Send command to tclsh process
        log.debug(f"Sending command to tclsh: {command}")
        _tcl_process.stdin.write(command + "\n")
        _tcl_process.stdin.flush()
        
        # Read the output with a simple timeout approach
        try:
            # Read all available output
            output = ""
            
            # Read until we get a prompt or timeout (simple approach)
            for _ in range(10):  # Try up to 10 times
                try:
                    line = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, _tcl_process.stdout.readline),
                        timeout=0.5
                    )
                    if not line:
                        break
                    output += line
                    log.debug(f"Received from tclsh: {repr(line)}")
                    
                    # Check if this looks like a prompt (Tcl typically ends with newline)
                    if line.strip() and not line.startswith("tclsh"):
                        break
                        
                except asyncio.TimeoutError:
                    # No more output available, but continue to check if process is alive
                    pass
                    
            result = output.strip()
            log.debug(f"Final result: {repr(result)}")
            return result
            
        except Exception as e:
            log.debug(f"Error reading from tclsh: {e}")
            return ""
        
    except Exception as e:
        error_msg = f"Error executing Tcl command: {str(e)}"
        log.debug(error_msg)
        return error_msg

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
