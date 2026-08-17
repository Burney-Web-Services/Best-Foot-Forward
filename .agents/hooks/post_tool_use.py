#!/usr/bin/env python3
import sys
import json
import subprocess
from pathlib import Path

def main():
    # If stdin is a TTY, don't read to avoid hanging
    if sys.stdin.isatty():
        print(json.dumps({}))
        sys.exit(0)

    try:
        # Read from stdin
        payload = json.loads(sys.stdin.read())
    except Exception:
        # Fallback to allow if JSON parsing fails
        print(json.dumps({}))
        sys.exit(0)

    # Get toolCall info
    tool_call = payload.get("toolCall", {})
    tool_name = tool_call.get("name")
    
    if tool_name == "run_command":
        args = tool_call.get("args", {})
        command_line = args.get("CommandLine", "")
        
        # Match python3 src/best_foot_forward/utils/generate_resume.py*
        if "src/best_foot_forward/utils/generate_resume.py" in command_line:
            # Run the post-tool use hook: track_application.py
            # We want to run it from the workspace root directory (which is parent of .agents)
            workspace_root = Path(__file__).resolve().parent.parent.parent
            subprocess.run(
                [sys.executable or "python3", "src/best_foot_forward/utils/track_application.py"],
                cwd=str(workspace_root),
                check=False
            )
            
    # Always exit 0 and print empty JSON object
    print(json.dumps({}))
    sys.exit(0)

if __name__ == "__main__":
    main()
