import subprocess
import asyncio
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
    
    try:
        # Start tclsh process if not already running
        if _tcl_process is None:
            _tcl_process = subprocess.Popen(
                ["tclsh"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
        
        # Send command to tclsh process
        _tcl_process.stdin.write(command + "\n")
        _tcl_process.stdin.flush()
        
        # Read the output (we need to read until we get a prompt or timeout)
        output = ""
        try:
            # Try to read output with timeout
            while True:
                line = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, _tcl_process.stdout.readline),
                    timeout=5.0
                )
                if not line:
                    break
                output += line
                # Check if we have a prompt (simple check)
                if line.strip().endswith("> "):
                    break
        except asyncio.TimeoutError:
            pass
            
        # Remove the last newline and any trailing whitespace
        return output.strip()
        
    except Exception as e:
        return f"Error executing Tcl command: {str(e)}"

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
