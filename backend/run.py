import os
import sys
from dotenv import load_dotenv

# 确保工作目录为 backend/
os.chdir(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("FLASK_PORT", 5001))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug)
