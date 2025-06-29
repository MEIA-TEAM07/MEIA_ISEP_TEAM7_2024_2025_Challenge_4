import os
from datetime import datetime
LOG_DIR = os.path.join(os.getcwd(), 'logs')


# ANSI color codes
AGENT_COLORS = {
    "central": "\033[94m",    # Blue
    "vigilant": "\033[92m",   # Green
    "payload": "\033[93m",  # Yellow
    "field": "\033[91m",      # Red
    "default": "\033[0m",     # Reset
}

BORDER_COLOR = "\033[90m"    # Grey for borders
RESET = "\033[0m"

def get_color(agent_name: str) -> str:
    if agent_name.startswith("central"):
        return AGENT_COLORS["central"]
    elif agent_name.startswith("vigilant"):
        return AGENT_COLORS["vigilant"]
    elif agent_name.startswith("payload"):
        return AGENT_COLORS["payload"]
    elif agent_name.startswith("field"):
        return AGENT_COLORS["field"]
    else:
        return AGENT_COLORS["default"]

def print_agent_header(agent_name: str):
    color = get_color(agent_name)
    line = f"{BORDER_COLOR}{'─' * 40}{RESET}"
    print(line)
    print(f"{color}🛰️  AGENT [{agent_name.upper()}] is starting...{RESET}")
    print(line)

# def print_log(agent_name: str, message: str):
#     color = get_color(agent_name)
#     now = datetime.now().strftime("%H:%M:%S")
#     border = f"{BORDER_COLOR}[{agent_name.upper()} @ {now}]{RESET}"
#     print(f"{border} {color}{message}{RESET}")


def print_log(agent_name: str, message: str):
    """
    Logs a message for the given agent to a file named <agent_name>.log in the '../logs' directory.
    Creates the file on first use, appends on subsequent uses.

    :param agent_name: Name of the agent, used for the log filename.
    :param message: The message to log.
    """
    # Ensure the logs directory exists
    os.makedirs(LOG_DIR, exist_ok=True)

    # Construct the log file path
    filename = os.path.join(LOG_DIR, f"{agent_name}.log")

    # Timestamp for this entry
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{agent_name.upper()} @ {now}] {message}\n"

    # Append the entry to the log file (creates file if it doesn't exist)
    with open(filename, 'a', encoding='utf-8') as log_file:
        log_file.write(log_entry)