from datetime import datetime

# ANSI color codes
AGENT_COLORS = {
    "central": "\033[94m",    # Blue
    "vigilant": "\033[92m",   # Green
    "treatment": "\033[91m",  # Red
    "field": "\033[93m",      # Yellow
    "default": "\033[0m",     # Reset
}

BORDER_COLOR = "\033[90m"    # Grey for borders
RESET = "\033[0m"

def get_color(agent_name: str) -> str:
    if agent_name.startswith("central"):
        return AGENT_COLORS["central"]
    elif agent_name.startswith("vigilant"):
        return AGENT_COLORS["vigilant"]
    elif agent_name.startswith("treatment"):
        return AGENT_COLORS["treatment"]
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

def print_log(agent_name: str, message: str):
    color = get_color(agent_name)
    now = datetime.now().strftime("%H:%M:%S")
    border = f"{BORDER_COLOR}[{agent_name.upper()} @ {now}]{RESET}"
    print(f"{border} {color}{message}{RESET}")