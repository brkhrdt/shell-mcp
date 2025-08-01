import subprocess
import asyncio
from typing import Any
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("tcl")

@mcp.tool()
async def run_tcl(command: str) -> str:
    """Execute a Tcl command and return the result.
    
    Args:
        command: Tcl command to execute
        
    Returns:
        Command output or error message
    """
    try:
        # Execute the Tcl command using tclsh
        result = subprocess.run(
            ["tclsh", "-c", command],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return f"Error executing Tcl command: {result.stderr.strip()}"
            
    except subprocess.TimeoutExpired:
        return "Error: Tcl command timed out"
    except FileNotFoundError:
        return "Error: Tcl interpreter (tclsh) not found"
    except Exception as e:
        return f"Error executing Tcl command: {str(e)}"

if __name__ == "__main__":
    # Initialize and run the server
    mcp.run(transport='stdio')
