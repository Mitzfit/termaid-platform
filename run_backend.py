import uvicorn
import sys
import os

if __name__ == "__main__":
    # Ensure the root directory is in the path
    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        
    print("Starting TermAId backend server...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
