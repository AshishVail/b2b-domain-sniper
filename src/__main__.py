
"""
B2B Domain Sniper
Apify Actor entry point.

Starts the application through: python -m src
"""

import asyncio

from .main import main


if __name__ == "__main__":
    asyncio.run(main())
  
