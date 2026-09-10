"""
Ministry of Ayush – Smart MediKiosk
Main Flask Application Server
Government of India / Bharat • Clinical History Platform
"""

import os
from server import app, create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
