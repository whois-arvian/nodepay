import asyncio
import math
import time
import uuid
import cloudscraper
from loguru import logger
from fake_useragent import UserAgent

# Constants
PING_INTERVAL = 30
RETRIES = 30

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": "http://nw.nodepay.ai/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

# Session variables will now be re-initialized for each batch
status_connect = CONNECTION_STATES["NONE_CONNECTION"]
last_ping_time = {}  # Store ping times for each token

def show_warning():
    confirm = input("By using this tool means you understand the risks. do it at your own risk! \nPress Enter to continue or Ctrl+C to cancel... ")

    if confirm.strip() == "":
        print("Continuing...")
    else:
        print("Exiting...")
        exit()

def uuidv4():
    return str(uuid.uuid4())
    
def valid_resp(resp):
    if not resp or "code" not in resp or resp["code"] < 0:
        raise ValueError("Invalid response")
    return resp

async def render_profile_info(token):
    global status_connect, last_ping_time

    # Initialize session variables locally
    browser_id = uuidv4()
    account_info = {}

    try:
        np_session_info = load_session_info()

        if not np_session_info:
            # Generate new browser_id
            response = await call_api(DOMAIN_API["SESSION"], {}, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(account_info)
                await start_ping(token, browser_id, account_info)
            else:
                handle_logout()
        else:
            account_info = np_session_info
            await start_ping(token, browser_id, account_info)
    except Exception as e:
        logger.error(f"Error in render_profile_info: {e}")
        error_message = str(e)
        if any(phrase in error_message for phrase in [
            "sent 1011 (internal error) keepalive ping timeout; no close frame received",
            "500 Internal Server Error"
        ]):
            logger.info(f"Encountered an error, retrying...")
            return None
        else:
            logger.error(f"Connection error: {e}")
            return None

async def call_api(url, data, token):
    user_agent = UserAgent(os=['windows', 'macos', 'linux'], browsers='chrome')
    random_user_agent = user_agent.random
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": random_user_agent,
        "Content-Type": "application/json",
        "Origin": "chrome-extension://lgmpfmgeabnnlemejacfljbmonaomfmm",
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        scraper = cloudscraper.create_scraper()

        response = scraper.post(url, json=data, headers=headers, timeout=30)

        response.raise_for_status()
        return valid_resp(response.json())
    except Exception as e:
        logger.error(f"Error during API call: {e}")
        raise ValueError(f"Failed API call to {url}")

async def start_ping(token, browser_id, account_info):
    try:
        while True:
            await ping(token, browser_id, account_info)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"Ping task was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping: {e}")
        
async def ping(token, browser_id, account_info):
    global last_ping_time, RETRIES, status_connect

    current_time = time.time()

    # Check if the token has a separate last ping time and if enough time has passed
    if token in last_ping_time and (current_time - last_ping_time[token]) < PING_INTERVAL:
        logger.info(f"Skipping ping for token {token}, not enough time elapsed")
        return

    last_ping_time[token] = current_time  # Update the last ping time for this token

    try:
        data = {
            "id": account_info.get("uid"),
            "browser_id": browser_id,  
            "timestamp": int(time.time()),
            "version": "2.2.7"
        }

        response = await call_api(DOMAIN_API["PING"], data, token)
        if response["code"] == 0:
            logger.info(f"Ping successful for token {token}: {response}")
            RETRIES = 0
            status_connect = CONNECTION_STATES["CONNECTED"]
        else:
            handle_ping_fail(response)
    except Exception as e:
        logger.error(f"Ping failed for token {token}: {e}")
        handle_ping_fail(None)

def handle_ping_fail(response):
    global RETRIES, status_connect

    RETRIES += 1
    if response and response.get("code") == 403:
        handle_logout()
    elif RETRIES < 2:
        status_connect = CONNECTION_STATES["DISCONNECTED"]
    else:
        status_connect = CONNECTION_STATES["DISCONNECTED"]

def handle_logout():
    global status_connect

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    logger.info(f"Logged out and cleared session info")

def save_session_info(data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": data.get("browser_id")  
    }
    pass

def load_session_info():
    return {}  # Placeholder for loading session info

async def run_with_token(token):
    # Move session variables inside run_with_token
    browser_id = uuidv4()
    account_info = {}

    tasks = {}

    tasks[asyncio.create_task(render_profile_info(token))] = token

    done, pending = await asyncio.wait(tasks.keys(), return_when=asyncio.FIRST_COMPLETED)
    for task in done:
        failed_token = tasks[task]
        if task.result() is None:
            logger.info(f"Failed for token {failed_token}, retrying...")
        tasks.pop(task)

    await asyncio.sleep(3)

async def process_batch(batch_tokens):
    tasks = [run_with_token(token) for token in batch_tokens]
    await asyncio.gather(*tasks)

async def main():
    # Load tokens from the file
    try:
        with open('token_list.txt', 'r') as file:
            tokens = file.read().splitlines()
    except Exception as e:
        logger.error(f"Error reading token list: {e}")
        return

    if not tokens:
        print("No tokens found. Exiting.")
        return

    # Membagi tokens menjadi batch
    BATCH_SIZE = 20  # Ukuran batch dapat disesuaikan
    total_batches = math.ceil(len(tokens) / BATCH_SIZE)
    logger.info(f"Total tokens: {len(tokens)}, Batch size: {BATCH_SIZE}, Total batches: {total_batches}")

    for batch_index in range(total_batches):
        batch_tokens = tokens[batch_index * BATCH_SIZE:(batch_index + 1) * BATCH_SIZE]
        logger.info(f"Processing batch {batch_index + 1}/{total_batches} with {len(batch_tokens)} tokens")

        await process_batch(batch_tokens)

        logger.info(f"Batch {batch_index + 1} completed.")

    logger.info("All batches processed successfully. Restarting...")  # After all batches are processed, restart the loop.

if __name__ == '__main__':
    show_warning()
    print("\nAlright, we here! The tool will now use multiple tokens without proxies.")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
