from api.db import init_db
import asyncio
from dotenv import load_dotenv

load_dotenv() 

if __name__ == "__main__":
    asyncio.run(init_db())
