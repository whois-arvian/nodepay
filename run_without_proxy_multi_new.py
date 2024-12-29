import asyncio
import time
import uuid
import cloudscraper
from loguru import logger
from fake_useragent import UserAgent

# Constants
PING_INTERVAL = 60
RETRIES = 60
MAX_CONCURRENT_REQUESTS = 20  # Set to process only 20 tokens concurrently
BACKOFF_FACTOR = 1.5  # Backoff for retries
BATCH_SIZE = 20  # Size of each batch to process at a time

DOMAIN_API = {
    "SESSION": "http://api.nodepay.ai/api/auth/session",
    "PING": "http://nw.nodepay.ai/api/network/ping"
}

CONNECTION_STATES = {
    "CONNECTED": 1,
    "DISCONNECTED": 2,
    "NONE_CONNECTION": 3
}

status_connect = CONNECTION_STATES["NONE_CONNECTION"]
browser_id = None
account_info = {}
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
    global browser_id, account_info

    try:
        np_session_info = load_session_info()

        if not np_session_info:
            # Generate new browser_id
            browser_id = uuidv4()
            response = await call_api_with_retry(DOMAIN_API["SESSION"], {}, token)
            valid_resp(response)
            account_info = response["data"]
            if account_info.get("uid"):
                save_session_info(account_info)
                await start_ping(token)
            else:
                handle_logout()
        else:
            account_info = np_session_info
            await start_ping(token)
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

async def call_api_with_retry(url, data, token, retries=5, backoff_factor=BACKOFF_FACTOR):
    attempt = 0
    while attempt < retries:
        try:
            return await call_api(url, data, token)
        except ValueError as e:
            logger.warning(f"Attempt {attempt + 1} failed for {token}: {e}")
            if attempt < retries - 1:
                wait_time = backoff_factor ** attempt
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            attempt += 1
    logger.error(f"All retries failed for {token}. Giving up.")
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

async def start_ping(token):
    try:
        while True:
            await ping(token)
            await asyncio.sleep(PING_INTERVAL)
    except asyncio.CancelledError:
        logger.info(f"Ping task was cancelled")
    except Exception as e:
        logger.error(f"Error in start_ping: {e}")

async def ping(token):
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

        response = await call_api_with_retry(DOMAIN_API["PING"], data, token)
        if response and response.get("code") == 0:
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
    global status_connect, account_info

    status_connect = CONNECTION_STATES["NONE_CONNECTION"]
    account_info = {}
    logger.info(f"Logged out and cleared session info")

def save_session_info(data):
    data_to_save = {
        "uid": data.get("uid"),
        "browser_id": browser_id  
    }
    pass

def load_session_info():
    return {}  # Placeholder for loading session info

async def process_batch(tokens_batch):
    tasks = []
    logger.info(f"Processing batch of {len(tokens_batch)} tokens")

    for token in tokens_batch:
        tasks.append(run_with_token(token))
    
    # Process the batch concurrently
    await asyncio.gather(*tasks)

async def run_with_token(token):
    await render_profile_info(token)

async def main():
    try:
        with open('token_list.txt', 'r') as file:
            tokens = file.read().splitlines()
    except Exception as e:
        logger.error(f"Error reading token list: {e}")
        return

    if not tokens:
        print("No tokens found. Exiting.")
        return

    # Process tokens in batches of BATCH_SIZE
    for i in range(0, len(tokens), BATCH_SIZE):
        batch = tokens[i:i + BATCH_SIZE]
        await process_batch(batch)

if __name__ == '__main__':
    show_warning()
    print("\nAlright, we here! The tool will now use multiple tokens without proxies.")
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Program terminated by user.")
