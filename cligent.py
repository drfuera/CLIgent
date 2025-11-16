#!/usr/bin/env python3
"""
CLIgent - AI-Powered Command Line Interface Assistant

A command-line tool that uses AI models (DeepSeek, ChatGPT, Claude) to help users
with command-line tasks, explanations, and troubleshooting.

Created by Andrej Fuera
GitHub: https://github.com/drfuera/CLIgent/

Features:
- Interactive command-line assistance using multiple AI providers
- Command execution with user confirmation
- Session logging and history
- Real-time API calls with loading indicators
- Error handling and recursion detection
- Markdown formatting cleanup for terminal display

Usage:
    python cligent.py [prompt]
    or
    ./cligent.py [prompt]

Comment:
	AI is lovely; But nobody loves like Jesus.
	All glory to the one true God, full of patience and mercy.

	Matt. 5:3
	Blessed are the poor in spirit: for theirs is the kingdom of heaven.

	Rom. 10:13
	For whosoever shall call upon the name of the Lord shall be saved.
"""

import json
import os
import re
import shutil
import signal
import subprocess
import sys
import termios
import threading
import time
import tty
from datetime import datetime

import requests


def extract_json_from_markdown(text):
    """Extract JSON content from markdown code blocks"""
    # Look for JSON code blocks first - match the entire content between ```json and ```
    json_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if json_match:
        return json_match.group(1).strip()

    # If no JSON code block found, try to extract any code block content
    code_match = re.search(r"```.*?\n(.*?)\n```", text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()

    # If no code blocks found, return original text
    return text


def clean_markdown_formatting(text):
    """Remove markdown formatting for better terminal display"""
    # Remove headers (###, ##, #)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove horizontal rules (---, ***)
    text = re.sub(r"^[-*]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove bold/italic (**text**, *text*)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)

    # Remove code blocks (```code```)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Remove inline code (`code`)
    text = re.sub(r"`(.*?)`", r"\1", text)

    # Clean up extra whitespace
    text = re.sub(r"\n\s*\n\s*\n", "\n\n", text)
    text = text.strip()

    return text


# Configuration
API_KEY = ""
API_URL = ""
# Model configurations will be loaded from config.json

# Provider API endpoints will be loaded from config.json

# Current model configuration
AGENT_MODEL = "deepseek-chat"
CURRENT_PROVIDER = "DeepSeek"  # Track which provider is active
AGENT_MODE = "WORK"  # "ASK" or "WORK"
TEMPERATURE = 0.0

# Model selector state
SELECTED_MODEL_INDEX = 0
MODEL_SELECTOR_ACTIVE = False

# State
history_blocks = []
stop_requested = False
HISTORY_VIEWER_ACTIVE = False
SELECTED_HISTORY_INDEX = 0
PROVIDERS_VIEWER_ACTIVE = False
SELECTED_PROVIDER_INDEX = 0


# Colors
class Color:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    RED = "\033[91m"
    WHITE = "\033[97m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"
    FG_DARK_GREEN = "\033[38;5;22m"  # Dark green foreground
    FG_DARKER_GREEN = "\033[38;5;23m"  # Darker green for bottom border
    FG_LIGHTER_GREEN = "\033[38;5;34m"  # Lighter green for top border
    BG_DARK_GREEN = "\033[48;5;22m"  # Dark green background
    BG_SELECTED = "\033[48;5;24m"  # Dark blue background for selected items
    BG_HISTORY_VIEWER = "\033[48;5;235m"  # Dark gray background for history viewer
    FG_GRAY = "\033[38;5;240m"  # Gray text for disabled items
    BG_ASK = "\033[48;5;34m"  # Light green background for ASK mode
    BG_WORK = "\033[48;5;124m"  # Red background for WORK mode


def show_history_viewer():
    """Display history entries in a table with selection"""
    global SELECTED_HISTORY_INDEX, HISTORY_VIEWER_ACTIVE

    while HISTORY_VIEWER_ACTIVE:
        clear_screen()
        terminal_width = get_terminal_width()

        # Info box
        info_text = "HISTORY VIEWER"
        controls_text = "↑↓: navigate • DEL: delete • BACKSPACE: exit"

        # Calculate box width (use the wider of the two texts + padding)
        box_width = max(len(info_text), len(controls_text)) + 4
        padding_left = (terminal_width - box_width) // 2

        # Top border
        top_border = " " * padding_left + "┌" + "─" * (box_width - 2) + "┐"
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}┌{'─' * (box_width - 2)}┐{Color.RESET}"
        )

        # Info line (centered)
        info_padding = (box_width - 2 - len(info_text)) // 2
        info_line = (
            " " * padding_left
            + "│"
            + " " * info_padding
            + info_text
            + " " * (box_width - 2 - len(info_text) - info_padding)
            + "│"
        )
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}│{' ' * info_padding}{info_text}{' ' * (box_width - 2 - len(info_text) - info_padding)}│{Color.RESET}"
        )

        # Separator
        separator_line = " " * padding_left + "├" + "─" * (box_width - 2) + "┤"
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}├{'─' * (box_width - 2)}┤{Color.RESET}"
        )

        # Controls line (centered)
        controls_padding = (box_width - 2 - len(controls_text)) // 2
        controls_line = (
            " " * padding_left
            + "│"
            + " " * controls_padding
            + controls_text
            + " " * (box_width - 2 - len(controls_text) - controls_padding)
            + "│"
        )
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}│{' ' * controls_padding}{controls_text}{' ' * (box_width - 2 - len(controls_text) - controls_padding)}│{Color.RESET}"
        )

        # Bottom border
        bottom_border = " " * padding_left + "└" + "─" * (box_width - 2) + "┘"
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}└{'─' * (box_width - 2)}┘{Color.RESET}"
        )
        print()

        if not history_blocks:
            print("No history entries found.")
            print()
            # Show status bar
            display_history_viewer_status()
            break

        # Calculate column widths
        max_tokens_width = 8
        max_date_width = 13
        max_mode_width = 6
        max_model_width = 17
        # Calculate exact width accounting for borders (6 vertical lines + 2 corners = 8 chars)
        available_width = (
            terminal_width
            - max_tokens_width
            - max_date_width
            - max_mode_width
            - max_model_width
            - 7
        )  # 7 for borders (││││││ + ┌┐)
        user_prompt_width = available_width // 2
        summary_width = available_width - user_prompt_width  # Use remaining width

        # Table header
        header_line = f"┌{'─' * max_tokens_width}┬{'─' * max_date_width}┬{'─' * max_mode_width}┬{'─' * max_model_width}┬{'─' * user_prompt_width}┬{'─' * summary_width}┐"
        print(header_line)

        header_row = f"│{' Tokens '.center(max_tokens_width)}│{' Date/Time '.center(max_date_width)}│{' Mode '.center(max_mode_width)}│{' Model '.center(max_model_width)}│{' User Prompt '.center(user_prompt_width)}│{' Summary '.center(summary_width)}│"
        print(header_row)

        separator_line = f"├{'─' * max_tokens_width}┼{'─' * max_date_width}┼{'─' * max_mode_width}┼{'─' * max_model_width}┼{'─' * user_prompt_width}┼{'─' * summary_width}┤"
        print(separator_line)

        # Table rows
        for i, block in enumerate(history_blocks):
            # Calculate token cost for this entry
            user_prompt = block.get("user_prompt", "")
            summary = block.get("summary", "")
            token_cost = max(1, len(user_prompt + summary) // 4)

            # Format date
            timestamp = block.get("timestamp", "")
            if timestamp:
                try:
                    # Parse timestamp and format as YYYY-MM-DD HH:MM
                    dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                    date_display = " " + dt.strftime("%m-%d %H:%M") + " "
                except:
                    # Fallback to original format if parsing fails
                    date_display = " " + timestamp.split()[0] + " "
            else:
                date_display = " Unknown "

            # Truncate text to fit columns
            user_display = (
                (" " + user_prompt[: user_prompt_width - 5] + "... ")
                if len(user_prompt) > user_prompt_width - 2
                else " " + user_prompt + " "
            )
            summary_display = (
                (" " + summary[: summary_width - 5] + "... ")
                if len(summary) > summary_width - 2
                else " " + summary + " "
            )

            # Apply selection background
            # Get mode and model
            mode = block.get("mode", "UNKNOWN")
            model = block.get("model", "UNKNOWN")

            # Truncate model name if too long
            model_display = (
                " " + model[: max_model_width - 4] + ".. "
                if len(model) > max_model_width - 2
                else " " + model + " "
            )

            mode_display = " " + mode + " "

            if i == SELECTED_HISTORY_INDEX:
                tokens_cell = f"{Color.BG_SELECTED}{(' ' + str(token_cost) + ' ').center(max_tokens_width)}{Color.RESET}"
                date_cell = f"{Color.BG_SELECTED}{date_display.center(max_date_width)}{Color.RESET}"
                mode_cell = f"{Color.BG_SELECTED}{mode_display.center(max_mode_width)}{Color.RESET}"
                model_cell = f"{Color.BG_SELECTED}{model_display.center(max_model_width)}{Color.RESET}"
                user_cell = f"{Color.BG_SELECTED}{user_display.ljust(user_prompt_width)}{Color.RESET}"
                summary_cell = f"{Color.BG_SELECTED}{summary_display.ljust(summary_width)}{Color.RESET}"
            else:
                tokens_cell = (" " + str(token_cost) + " ").center(max_tokens_width)
                date_cell = date_display.center(max_date_width)
                mode_cell = mode_display.center(max_mode_width)
                model_cell = model_display.center(max_model_width)
                user_cell = user_display.ljust(user_prompt_width)
                summary_cell = summary_display.ljust(summary_width)

            row = f"│{tokens_cell}│{date_cell}│{mode_cell}│{model_cell}│{user_cell}│{summary_cell}│"
            print(row)

        # Table footer
        footer_line = f"└{'─' * max_tokens_width}┴{'─' * max_date_width}┴{'─' * max_mode_width}┴{'─' * max_model_width}┴{'─' * user_prompt_width}┴{'─' * summary_width}┘"
        print(footer_line)
        print()

        # Show status bar
        display_history_viewer_status()

        # Handle input
        ch = read_char()
        if ch == "\x7f" or ch == "\x08":  # BACKSPACE
            HISTORY_VIEWER_ACTIVE = False
            break
        elif ch == "UP":  # Up arrow
            SELECTED_HISTORY_INDEX = max(0, SELECTED_HISTORY_INDEX - 1)
        elif ch == "DOWN":  # Down arrow
            SELECTED_HISTORY_INDEX = min(
                len(history_blocks) - 1, SELECTED_HISTORY_INDEX + 1
            )
        elif ch == "\x7f" or ch == "DEL":  # Delete key
            if 0 <= SELECTED_HISTORY_INDEX < len(history_blocks):
                del history_blocks[SELECTED_HISTORY_INDEX]
                save_state()
                # Adjust selection index
                if (
                    SELECTED_HISTORY_INDEX >= len(history_blocks)
                    and len(history_blocks) > 0
                ):
                    SELECTED_HISTORY_INDEX = len(history_blocks) - 1
                elif len(history_blocks) == 0:
                    HISTORY_VIEWER_ACTIVE = False
                    break


def display_history_viewer_status():
    """Display status bar for history viewer"""
    terminal_width = get_terminal_width()

    # Calculate prompt tokens
    prompt_tokens = 0
    system_info = get_system_info()

    # Base system prompt tokens (approximate)
    if AGENT_MODE == "ASK":
        base_prompt = """You are a helpful AI assistant. The user is asking a question and wants a detailed, informative answer.

System context:

Provide a comprehensive answer to the user's question. Be detailed and helpful.
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Use this format:
{
            "type": "answer",
    "message": "Your detailed answer to the user's question"
}"""
    else:  # WORK mode
        base_prompt = """You are a SYSTEM AGENT.
System:
User prompt:
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Evaluate if this is a QUESTION or a TASK.
- Question: User wants information (max 5 commands to gather info)
- Task: User wants you to perform actions

If the user is asking about our previous conversation (what we discussed before, previous questions, etc.), you can answer directly using the conversation history above without running commands. Use this format:
{
            "type": "direct",
    "message": "Your direct answer using the conversation history"
}

For QUESTION:
{
            "type": "query",
    "message": "Brief description of what you WILL DO to answer (not the answer itself!)",
    "run": [
        {
                "message": "Why we're running this command",
            "command": "the command",
            "confirm": false
        }
    ]
}

For TASK:
{
            "type": "task",
    "message": "Brief summary of the task plan",
    "run": [
        {
                "message": "What this step does",
            "command": "the command",
            "confirm": false
        }
    ]
}

IMPORTANT:
- For 'message': describe what you WILL DO, not the result (you don't know the result yet!)
- Use only CLI commands, never TUI (no htop, nano, mc, mysql_secure_installation, etc)
- Set 'confirm': true for dangerous/system-changing commands
- Escape JSON properly"""

    # Add system info and estimated user prompt (50 tokens ~200 chars)
    base_prompt += system_info
    base_tokens = max(1, len(base_prompt) // 4) + 50  # +50 for user prompt

    # Add history tokens
    if history_blocks:
        history_text = "For reference, this is our conversation history summarized. Do not interpret this as part of the user question or task.\n"
        history_text += "This is for you to understand what we've done already so that you can give better answers and solutions to questions and tasks.\n"
        history_text += "These history entries are added in chronological order, where 1 is oldest:\n"
        for i, block in enumerate(history_blocks, 1):
            user_prompt = block.get("user_prompt", "No user prompt")
            summary = block.get("summary", "No summary")
            history_text += f"{i}) User: {user_prompt}\n   Agent: {summary}\n"
        history_text += "\n"
        history_tokens = max(1, len(history_text) // 4)
        prompt_tokens = base_tokens + history_tokens
    else:
        prompt_tokens = base_tokens

    # Status bar
    print("_" * terminal_width)
    model_display = AGENT_MODEL
    # Apply different background colors for ASK and WORK modes
    mode_display = AGENT_MODE
    if AGENT_MODE == "ASK":
        mode_display = f"{Color.BG_ASK}{AGENT_MODE}{Color.BG_DARK_GREEN}"
    elif AGENT_MODE == "WORK":
        mode_display = f"{Color.BG_WORK}{AGENT_MODE}{Color.BG_DARK_GREEN}"

    # Build status text with adaptive content based on terminal width
    if terminal_width >= 150:
        # Full status for very wide terminals
        status_text = f"🤖 AGENT [{model_display.upper()}]: CTRL+T     PROVIDER: CTRL+W     MODE [{mode_display}]: CTRL+P     HISTORY [{len(history_blocks)}]: CTRL+H     QUIT: CTRL+C"
    elif terminal_width >= 120:
        # Wide status - remove some token details
        status_text = f"🤖 AGENT [{model_display.upper()}]: CTRL+T     PROVIDER: CTRL+W     MODE [{mode_display}]: CTRL+P     HISTORY [{len(history_blocks)}]: CTRL+H     QUIT: CTRL+C"
    elif terminal_width >= 100:
        # Medium status - remove token details
        status_text = f"🤖 AGENT [{model_display.upper()}]: T     PROVIDER: W     MODE [{mode_display}]: P     HISTORY [{len(history_blocks)}]: H     QUIT: C"
    elif terminal_width >= 80:
        # Compact status - keep only essential info
        status_text = f"🤖 AGENT [{model_display.upper()}]: T     MODE [{mode_display}]: P     HISTORY [{len(history_blocks)}]: H     QUIT: C"
    else:
        # Minimal status for very narrow terminals
        status_text = f"🤖 AGENT [{model_display.upper()}]: T     MODE [{mode_display}]: P     QUIT: C"

    # Fill the rest of the line with background color (subtract 1 to avoid wrapping)
    padding = " " * (terminal_width - visual_length(status_text) - 1)
    print(f"{Color.BG_DARK_GREEN}{status_text}{padding}{Color.RESET}")
    sys.stdout.write("‾" * terminal_width + "\n")
    sys.stdout.flush()


def show_providers_viewer():
    """Display providers viewer"""
    global SELECTED_PROVIDER_INDEX, PROVIDERS_VIEWER_ACTIVE
    while PROVIDERS_VIEWER_ACTIVE:
        clear_screen()
        terminal_width = get_terminal_width()

        # Load provider config
        config = load_provider_config()
        providers = config.get("providers", {})
        provider_names = ["DeepSeek", "ChatGPT", "Claude"]

        # Info box
        info_text = "PROVIDERS MANAGER"
        controls_text = "↑↓: navigate • ENTER: toggle • SPACE: models • BACKSPACE: exit"

        # Info box
        info_text = "PROVIDERS MANAGER"
        controls_text = "↑↓: navigate • ENTER: toggle • BACKSPACE: exit"

        # Calculate box width (use the wider of the two texts + padding)
        box_width = max(len(info_text), len(controls_text)) + 4
        padding_left = (terminal_width - box_width) // 2

        # Top border
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}┌{'─' * (box_width - 2)}┐{Color.RESET}"
        )

        # Info line (centered)
        info_padding = (box_width - 2 - len(info_text)) // 2
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}│{' ' * info_padding}{info_text}{' ' * (box_width - 2 - len(info_text) - info_padding)}│{Color.RESET}"
        )

        # Separator
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}├{'─' * (box_width - 2)}┤{Color.RESET}"
        )

        # Controls line (centered)
        controls_padding = (box_width - 2 - len(controls_text)) // 2
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}│{' ' * controls_padding}{controls_text}{' ' * (box_width - 2 - len(controls_text) - controls_padding)}│{Color.RESET}"
        )

        # Bottom border
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}└{'─' * (box_width - 2)}┘{Color.RESET}"
        )
        print()

        # Calculate column widths
        max_provider_width = 10
        max_status_width = 10  # Increased by 2
        max_api_key_width = 18  # Decreased by 2
        max_description_width = 36  # Increased by 2 more for spaces
        table_width = (
            max_provider_width
            + max_status_width
            + max_api_key_width
            + max_description_width
            + 5
        )

        # Center the table
        table_padding = (terminal_width - table_width) // 2

        # Table header
        header_line = (
            " " * table_padding
            + f"┌{'─' * max_provider_width}┬{'─' * max_status_width}┬{'─' * max_api_key_width}┬{'─' * max_description_width}┐"
        )
        print(header_line)

        header_row = (
            " " * table_padding
            + f"│{'Provider'.center(max_provider_width)}│{'Status'.center(max_status_width)}│{'API Key'.center(max_api_key_width)}│{'Description'.center(max_description_width)}│"
        )
        print(header_row)

        separator_line = (
            " " * table_padding
            + f"├{'─' * max_provider_width}┼{'─' * max_status_width}┼{'─' * max_api_key_width}┼{'─' * max_description_width}┤"
        )
        print(separator_line)

        # Table rows
        for i, provider_name in enumerate(provider_names):
            provider_config = providers.get(
                provider_name, {"enabled": False, "api_key": ""}
            )
            is_enabled = provider_config.get("enabled", False)

            # Status text and color
            status_text = "ENABLED" if is_enabled else "DISABLED"

            # Format API key for display (show first 6 and last 4 characters)
            api_key = provider_config.get("api_key", "")
            if api_key and len(api_key) > 10:
                api_key_display = f"{api_key[:6]}******{api_key[-4:]}"
            elif api_key:
                api_key_display = "******"
            else:
                api_key_display = ""

            # Provider descriptions with available models
            descriptions = {
                "DeepSeek": "deepseek-chat, deepseek-reasoner",
                "ChatGPT": "gpt-4o, gpt-4, gpt-3.5-turbo",
                "Claude": "claude-3-opus, claude-3-sonnet, claude-3-haiku",
            }
            description = descriptions.get(provider_name, "")
            # Truncate description if too long (account for spaces)
            available_width = max_description_width - 2  # Subtract 2 for spaces
            if len(description) > available_width:
                description = description[: available_width - 3] + "..."

            # Apply selection background and status color
            if i == SELECTED_PROVIDER_INDEX:
                provider_cell = f"{Color.BG_SELECTED} {provider_name.ljust(max_provider_width - 1)}{Color.RESET}"
                if is_enabled:
                    status_cell = f"{Color.BG_SELECTED}{Color.GREEN}{status_text.center(max_status_width)}{Color.RESET}"
                else:
                    status_cell = f"{Color.BG_SELECTED}{Color.FG_GRAY}{status_text.center(max_status_width)}{Color.RESET}"
                api_key_cell = f"{Color.BG_SELECTED}{api_key_display.center(max_api_key_width)}{Color.RESET}"
                desc_cell = f"{Color.BG_SELECTED} {description.ljust(max_description_width - 2)} {Color.RESET}"
            else:
                provider_cell = f" {provider_name.ljust(max_provider_width - 1)}"
                if is_enabled:
                    status_cell = f"{Color.GREEN}{status_text.center(max_status_width)}{Color.RESET}"
                else:
                    status_cell = f"{Color.FG_GRAY}{status_text.center(max_status_width)}{Color.RESET}"
                api_key_cell = api_key_display.center(max_api_key_width)
                desc_cell = f" {description.ljust(max_description_width - 2)} "

            row = (
                " " * table_padding
                + f"│{provider_cell}│{status_cell}│{api_key_cell}│{desc_cell}│"
            )
            print(row)

        # Table footer
        footer_line = (
            " " * table_padding
            + f"└{'─' * max_provider_width}┴{'─' * max_status_width}┴{'─' * max_api_key_width}┴{'─' * max_description_width}┘"
        )
        print(footer_line)
        print()

        # Handle input
        ch = read_char()
        if ch == "\x7f" or ch == "\x08":  # BACKSPACE
            # Check if any provider has an API key before allowing exit
            config = load_provider_config()
            providers = config.get("providers", {})
            has_api_key = any(
                provider.get("api_key", "") for provider in providers.values()
            )

            if has_api_key:
                # Update API configuration when exiting providers viewer
                global API_URL, API_KEY, CURRENT_PROVIDER, AGENT_MODEL
                config = load_provider_config()

                # Find the enabled provider
                enabled_providers = [
                    name
                    for name, config in providers.items()
                    if config.get("enabled", False)
                ]
                if enabled_providers:
                    CURRENT_PROVIDER = enabled_providers[0]
                    provider_config = providers.get(CURRENT_PROVIDER, {})

                    # Set AGENT_MODEL to first available model from the provider
                    models = provider_config.get("models", [])
                    if models:
                        # Use first enabled model, not just first model in list
                        disabled_models = provider_config.get("disabled_models", [])
                        enabled_models = [m for m in models if m not in disabled_models]
                        if enabled_models:
                            AGENT_MODEL = enabled_models[0]
                        else:
                            # Fallback to first model if all are disabled (shouldn't happen due to validation)
                            AGENT_MODEL = models[0]
                    else:
                        # No models available for this provider
                        AGENT_MODEL = "unknown-model"

                provider_config = config.get("providers", {}).get(CURRENT_PROVIDER, {})
                API_URL = provider_config.get("endpoint", "")
                API_KEY = provider_config.get("api_key", "")
                PROVIDERS_VIEWER_ACTIVE = False
                break
            else:
                # Keep user in providers menu until at least one API key is set
                clear_screen()
                print(
                    "You must configure at least one provider with an API key before continuing."
                )
                print("Press any key to continue...")
                read_char()
        elif ch == "UP":  # Up arrow
            SELECTED_PROVIDER_INDEX = max(0, SELECTED_PROVIDER_INDEX - 1)
        elif ch == "DOWN":  # Down arrow
            SELECTED_PROVIDER_INDEX = min(
                len(provider_names) - 1, SELECTED_PROVIDER_INDEX + 1
            )
        elif ch == " ":  # SPACE - Open model selector
            selected_provider = provider_names[SELECTED_PROVIDER_INDEX]
            provider_config = providers.get(
                selected_provider, {"enabled": False, "api_key": "", "models": []}
            )

            # Check if provider has models and is enabled
            if provider_config.get("enabled", False) and provider_config.get("models"):
                show_model_selector(selected_provider, provider_config, config)
                # Reload config after model selector
                config = load_provider_config()
                providers = config.get("providers", {})
        elif ch == "\r" or ch == "\n":  # ENTER
            selected_provider = provider_names[SELECTED_PROVIDER_INDEX]
            provider_config = providers.get(
                selected_provider, {"enabled": False, "api_key": ""}
            )

            if provider_config.get("enabled", False):
                # Disable provider - check if this is the only enabled provider
                enabled_providers = [
                    name
                    for name in provider_names
                    if providers.get(name, {}).get("enabled", False)
                ]
                if (
                    len(enabled_providers) == 1
                    and enabled_providers[0] == selected_provider
                ):
                    # This is the only enabled provider, cannot disable it
                    clear_screen()
                    print("Cannot disable the only enabled provider.")
                    print("You must enable another provider first.")
                    print("Press any key to continue...")
                    read_char()
                else:
                    # Disable this provider
                    provider_config["enabled"] = False
                    providers[selected_provider] = provider_config
                    config["providers"] = providers
                    save_provider_config(config)
            else:
                # Enable provider - always show prompt but use existing key if blank
                clear_screen()
                existing_api_key = provider_config.get("api_key", "")
                if existing_api_key:
                    print(
                        f"Enter API key for {selected_provider} (leave blank to use existing):"
                    )
                else:
                    print(f"Enter API key for {selected_provider}:")

                api_key = input().strip()

                if api_key:
                    # Use new API key - disable all other providers first
                    for provider_name in provider_names:
                        if provider_name != selected_provider:
                            other_provider_config = providers.get(
                                provider_name, {"enabled": False, "api_key": ""}
                            )
                            other_provider_config["enabled"] = False
                            providers[provider_name] = other_provider_config

                    # Fetch available models from the provider
                    print(f"Fetching available models from {selected_provider}...")
                    endpoint = provider_config.get("endpoint", "")
                    models = fetch_provider_models(selected_provider, api_key, endpoint)

                    provider_config["enabled"] = True
                    provider_config["api_key"] = api_key
                    provider_config["models"] = models
                    providers[selected_provider] = provider_config
                    config["providers"] = providers
                    save_provider_config(config)

                    if models:
                        print(f"Found {len(models)} models: {', '.join(models)}")
                    else:
                        print("No models found or failed to fetch models")
                    print("Press any key to continue...")
                    read_char()
                elif existing_api_key:
                    # Use existing API key - disable all other providers first
                    for provider_name in provider_names:
                        if provider_name != selected_provider:
                            other_provider_config = providers.get(
                                provider_name, {"enabled": False, "api_key": ""}
                            )
                            other_provider_config["enabled"] = False
                            providers[provider_name] = other_provider_config

                    # Fetch available models from the provider if not already fetched
                    if not provider_config.get("models"):
                        print(f"Fetching available models from {selected_provider}...")
                        endpoint = provider_config.get("endpoint", "")
                        models = fetch_provider_models(
                            selected_provider, existing_api_key, endpoint
                        )
                        provider_config["models"] = models

                        if models:
                            print(
                                f"Found {len(models)} models: {', '.join(models.keys())}"
                            )
                        else:
                            print("No models found or failed to fetch models")
                        print("Press any key to continue...")
                        read_char()

                    provider_config["enabled"] = True
                    providers[selected_provider] = provider_config
                    config["providers"] = providers
                    save_provider_config(config)
                else:
                    print("No API key provided. Provider remains disabled.")
                    print("Press any key to continue...")
                    read_char()


def log(text):
    """Write text to session.log"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, "session.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def log_print(*args, **kwargs):
    """Wrapper for print() that also logs to session.log"""
    import io

    output = io.StringIO()
    print(*args, file=output, **kwargs)
    printed_text = output.getvalue()

    # Log the printed text
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, "session.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(printed_text)

    # Call the original print
    print(*args, **kwargs)


def read_session_log():
    """Read and return the content of session.log"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(script_dir, "session.log")
        with open(log_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def clear_session_log():
    """Clear the session.log file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(script_dir, "session.log")
    open(log_path, "w", encoding="utf-8").close()


def strip_ansi_codes(text):
    """Remove ANSI color codes and clean up text for AI consumption"""
    import re

    # Remove ANSI escape sequences (colors, formatting)
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    cleaned = ansi_escape.sub("", text)

    # Remove common prefix symbols and extra whitespace
    cleaned = re.sub(r"^[█▶●⚙️✅🚫💡🤖👤]*\s*", "", cleaned)
    cleaned = cleaned.strip()

    return cleaned


def visual_length(text):
    """Calculate the visible length of text, excluding ANSI escape codes"""
    import re

    # Remove ANSI escape sequences (colors, formatting)
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    cleaned = ansi_escape.sub("", text)
    return len(cleaned)


def clear_screen():
    os.system("clear")


def get_system_info():
    try:
        os_name = subprocess.run(
            "uname -s", shell=True, capture_output=True, text=True
        ).stdout.strip()
        kernel = subprocess.run(
            "uname -r", shell=True, capture_output=True, text=True
        ).stdout.strip()
        distro_cmd = "lsb_release -ds 2>/dev/null || cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d'=' -f2 | tr -d '\"'"
        distro = (
            subprocess.run(
                distro_cmd, shell=True, capture_output=True, text=True
            ).stdout.strip()
            or "Unknown"
        )
        user = subprocess.run(
            "whoami", shell=True, capture_output=True, text=True
        ).stdout.strip()
        return f"OS: {os_name} | Kernel: {kernel} | Distro: {distro} | User: {user}"
    except:
        return "OS: Unknown"


def migrate_config_to_new_structure(config):
    """Migrate old config structure to new model configuration structure"""
    if "providers" not in config:
        return config

    providers = config["providers"]

    for provider_name, provider_config in providers.items():
        # Skip if already in new structure
        if "models" in provider_config and isinstance(provider_config["models"], dict):
            continue

        # Convert old structure to new
        old_models = provider_config.get("models", [])
        old_disabled_models = provider_config.get("disabled_models", [])

        new_models = {}

        # Add all models from old list with proper configuration
        for model_name in old_models:
            is_enabled = model_name not in old_disabled_models

            # Get known configuration or use defaults
            default_config = get_default_model_config(provider_name, model_name)
            max_tokens = default_config.get("max_tokens", 4096)

            new_models[model_name] = {
                "enabled": is_enabled,
                "max_tokens": max_tokens,
            }

        # Add default configuration for unknown models
        if new_models:
            new_models["default"] = {
                "enabled": False,
                "max_tokens": 4096,
            }

        # Update provider config
        provider_config["models"] = new_models

        # Remove old fields
        if "disabled_models" in provider_config:
            del provider_config["disabled_models"]

    return config


def get_default_model_config(provider_name, model_name):
    """Get default model configuration from known_models"""
    known_models = {
        "DeepSeek": {
            "deepseek-chat": {"max_tokens": 8096},
            "deepseek-reasoner": {"max_tokens": 64768},
        },
        "ChatGPT": {
            "gpt-3.5-turbo": {"max_tokens": 4096},
            "gpt-3.5-turbo-16k": {"max_tokens": 4096},
            "gpt-4": {"max_tokens": 4096},
            "gpt-4-turbo": {"max_tokens": 4096},
            "gpt-4o": {"max_tokens": 4096},
            "gpt-4.1": {"max_tokens": 32768},
            "gpt-4.1-mini": {"max_tokens": 32768},
            "gpt-4.1-nano": {"max_tokens": 32768},
            "o1": {"max_tokens": 100000},
            "o1-pro": {"max_tokens": 100000},
            "o3": {"max_tokens": 100000},
            "o3-mini": {"max_tokens": 100000},
            "o4-mini": {"max_tokens": 100000},
        },
        "Claude": {
            "claude-sonnet-4-5-20250929": {"max_tokens": 64000},
            "claude-sonnet-4-20250514": {"max_tokens": 64000},
            "claude-opus-4-1-20250805": {"max_tokens": 32000},
            "claude-opus-4-20250514": {"max_tokens": 32000},
            "claude-haiku-4-5-20251001": {"max_tokens": 16384},
            "claude-3-5-haiku-20241022": {"max_tokens": 8192},
            "claude-3-haiku-20240307": {"max_tokens": 4096},
        },
    }

    provider_models = known_models.get(provider_name, {})
    model_config = provider_models.get(model_name, {})
    return {"enabled": True, "max_tokens": model_config.get("max_tokens", 4096)}


def load_provider_config():
    """Load provider configuration from config.json"""
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "config.json")
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                config = json.load(f)
                # Migrate to new structure if needed
                return migrate_config_to_new_structure(config)
        else:
            # Return default config if file doesn't exist
            return {
                "providers": {
                    "DeepSeek": {
                        "enabled": False,
                        "api_key": "",
                        "endpoint": "https://api.deepseek.com/v1/chat/completions",
                        "models": {
                            "deepseek-chat": get_default_model_config(
                                "DeepSeek", "deepseek-chat"
                            ),
                            "deepseek-reasoner": get_default_model_config(
                                "DeepSeek", "deepseek-reasoner"
                            ),
                        },
                    },
                    "ChatGPT": {
                        "enabled": False,
                        "api_key": "",
                        "endpoint": "https://api.openai.com/v1/chat/completions",
                        "models": {},
                    },
                    "Claude": {
                        "enabled": False,
                        "api_key": "",
                        "endpoint": "https://api.anthropic.com/v1/messages",
                        "models": {},
                    },
                }
            }
    except:
        return {
            "providers": {
                "DeepSeek": {
                    "enabled": False,
                    "api_key": "",
                    "endpoint": "https://api.deepseek.com/v1/chat/completions",
                    "models": {},
                },
                "ChatGPT": {
                    "enabled": False,
                    "api_key": "",
                    "endpoint": "https://api.openai.com/v1/chat/completions",
                    "models": {},
                    "disabled_models": [],
                },
                "Claude": {
                    "enabled": False,
                    "api_key": "",
                    "endpoint": "https://api.anthropic.com/v1/messages",
                    "models": {},
                    "disabled_models": [],
                },
            }
        }


def save_provider_config(config):
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
    except:
        pass


def get_model_max_tokens(provider_name, model_name):
    """Get max_tokens configuration for a specific model"""
    config = load_provider_config()
    providers = config.get("providers", {})
    provider_config = providers.get(provider_name, {})
    models_config = provider_config.get("models", {})

    # Try to get the specific model config
    model_config = models_config.get(model_name)
    if model_config and "max_tokens" in model_config:
        return model_config["max_tokens"]

    # Try to get default config for the provider
    default_config = models_config.get("default")
    if default_config and "max_tokens" in default_config:
        return default_config["max_tokens"]

    # Fallback to global default
    return 4096


def fetch_provider_models(provider_name, api_key, endpoint):
    """Fetch available models from provider API"""
    try:
        import json as json_module
        import urllib.request

        # Use the provided endpoint to construct the models API URL
        # Convert chat completions endpoint to models endpoint
        if endpoint:
            # Convert from chat completions endpoint to models endpoint
            if "/chat/completions" in endpoint:
                url = endpoint.replace("/chat/completions", "/models")
            elif "/v1/messages" in endpoint:
                url = endpoint.replace("/v1/messages", "/v1/models")
            else:
                # Fallback: try to construct models URL from base endpoint
                url = endpoint.rstrip("/") + "/models"
        else:
            return []

        # Define headers for each provider
        if provider_name == "DeepSeek":
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        elif provider_name == "ChatGPT":
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        elif provider_name == "Claude":
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        else:
            return []

        # Make the API request
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json_module.loads(response.read().decode("utf-8"))

            # Parse models based on provider response format
            # Extract model names based on provider
            if provider_name == "DeepSeek":
                model_names = [model["id"] for model in data.get("data", [])]
            elif provider_name == "ChatGPT":
                model_names = [model["id"] for model in data.get("data", [])]
            elif provider_name == "Claude":
                model_names = [model["id"] for model in data.get("data", [])]
            else:
                model_names = []

            # Convert to new model structure with default values
            models = {}
            for model_name in model_names:
                models[model_name] = get_default_model_config(provider_name, model_name)

            return models

    except Exception as e:
        print(f"Error fetching models from {provider_name}: {e}")
        return []


def show_model_selector(provider_name, provider_config, config):
    """Display model selector for a provider with fixed 20-row height"""
    global SELECTED_MODEL_INDEX, MODEL_SELECTOR_ACTIVE, AGENT_MODEL, CURRENT_PROVIDER
    MODEL_SELECTOR_ACTIVE = True
    SELECTED_MODEL_INDEX = 0
    scroll_offset = 0

    # Get models and their disabled status from new structure
    models_config = provider_config.get("models", {})
    models = list(models_config.keys())
    disabled_models = [
        model_name
        for model_name, config in models_config.items()
        if not config.get("enabled", True)
    ]

    # Check if current AGENT_MODEL is disabled and switch if needed
    if CURRENT_PROVIDER == provider_name and AGENT_MODEL in disabled_models:
        # Current model is disabled, switch to first available model
        enabled_models = [m for m in models if m not in disabled_models]
        if enabled_models:
            AGENT_MODEL = enabled_models[0]

    while MODEL_SELECTOR_ACTIVE:
        clear_screen()
        terminal_width = get_terminal_width()

        # Info box
        info_text = f"MODEL SELECTOR - {provider_name}"
        controls_text = "↑↓: navigate • SPACE: toggle • BACKSPACE: back"

        # Calculate box width (use the wider of the two texts + padding)
        box_width = max(len(info_text), len(controls_text)) + 4
        padding_left = (terminal_width - box_width) // 2

        # Top border
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}┌{'─' * (box_width - 2)}┐{Color.RESET}"
        )

        # Info line (centered)
        info_padding = (box_width - 2 - len(info_text)) // 2
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}│{' ' * info_padding}{info_text}{' ' * (box_width - 2 - len(info_text) - info_padding)}│{Color.RESET}"
        )

        # Separator
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}├{'─' * (box_width - 2)}┤{Color.RESET}"
        )

        # Controls line (centered)
        controls_padding = (box_width - 2 - len(controls_text)) // 2
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}│{' ' * controls_padding}{controls_text}{' ' * (box_width - 2 - len(controls_text) - controls_padding)}│{Color.RESET}"
        )

        # Bottom border
        print(
            " " * padding_left
            + f"{Color.BG_HISTORY_VIEWER}└{'─' * (box_width - 2)}┘{Color.RESET}"
        )
        print()

        if not models:
            print("No models available for this provider.")
            print("Press any key to continue...")
            read_char()
            break

        # Fixed table height - 20 rows max
        max_visible_rows = 20
        total_rows = len(models)

        # Calculate scroll boundaries
        if SELECTED_MODEL_INDEX < scroll_offset:
            scroll_offset = SELECTED_MODEL_INDEX
        elif SELECTED_MODEL_INDEX >= scroll_offset + max_visible_rows:
            scroll_offset = SELECTED_MODEL_INDEX - max_visible_rows + 1

        # Calculate visible range
        start_idx = scroll_offset
        end_idx = min(start_idx + max_visible_rows, total_rows)
        visible_models = models[start_idx:end_idx]

        # Table header
        max_model_width = min(40, terminal_width - 30)
        max_token_width = 12
        table_width = max_model_width + 12 + max_token_width + 3
        table_padding = (terminal_width - table_width) // 2

        header_line = (
            " " * table_padding
            + f"┌{'─' * max_model_width}┬{'─' * 12}┬{'─' * max_token_width}┐"
        )
        print(header_line)

        header_row = (
            " " * table_padding
            + f"│{'Model Name'.center(max_model_width)}│{' Status '.center(12)}│{'Max Token'.center(max_token_width)}│"
        )
        print(header_row)

        separator_line = (
            " " * table_padding
            + f"├{'─' * max_model_width}┼{'─' * 12}┼{'─' * max_token_width}┤"
        )
        print(separator_line)

        # Table rows for visible models only
        for i, model_name in enumerate(visible_models):
            global_idx = start_idx + i
            is_disabled = model_name in disabled_models
            status_text = "DISABLED" if is_disabled else "ENABLED"

            # Get model config for additional info
            model_config = models_config.get(model_name, {})
            max_tokens = model_config.get("max_tokens", 4096)

            # Truncate model name if too long
            display_name = model_name
            if len(display_name) > max_model_width - 2:
                display_name = display_name[: max_model_width - 5] + "..."

            # Apply selection background and status color
            if global_idx == SELECTED_MODEL_INDEX:
                model_cell = f"{Color.BG_SELECTED} {display_name.ljust(max_model_width - 1)}{Color.RESET}"
                if is_disabled:
                    status_cell = f"{Color.BG_SELECTED}{Color.FG_GRAY}{status_text.center(12)}{Color.RESET}"
                else:
                    status_cell = f"{Color.BG_SELECTED}{Color.GREEN}{status_text.center(12)}{Color.RESET}"
            else:
                model_cell = f" {display_name.ljust(max_model_width - 1)}"
                if is_disabled:
                    status_cell = (
                        f"{Color.FG_GRAY}{status_text.center(12)}{Color.RESET}"
                    )
                else:
                    status_cell = f"{Color.GREEN}{status_text.center(12)}{Color.RESET}"

            # Format max_tokens cell
            max_token_cell = f"{max_tokens}".center(max_token_width)
            if global_idx == SELECTED_MODEL_INDEX:
                max_token_cell = f"{Color.BG_SELECTED}{max_token_cell}{Color.RESET}"

            row = " " * table_padding + f"│{model_cell}│{status_cell}│{max_token_cell}│"
            print(row)

        # Table footer
        footer_line = (
            " " * table_padding
            + f"└{'─' * max_model_width}┴{'─' * 12}┴{'─' * max_token_width}┘"
        )
        print(footer_line)

        # Show scroll indicator if needed
        if total_rows > max_visible_rows:
            scroll_info = f"Showing {start_idx + 1}-{end_idx} of {total_rows} models"
            print(f"{scroll_info.center(terminal_width)}")

        # Show current model info
        current_model_config = models_config.get(AGENT_MODEL, {})
        current_max_tokens = current_model_config.get("max_tokens", 4096)
        current_info = f"Current: {AGENT_MODEL} (max_tokens: {current_max_tokens})"
        print(f"{current_info.center(terminal_width)}")

        print()

        # Handle input
        ch = read_char()
        if ch == "\x7f" or ch == "\x08":  # BACKSPACE
            # Set AGENT_MODEL to the currently selected model when leaving, but only if it's enabled
            if 0 <= SELECTED_MODEL_INDEX < len(models):
                selected_model = models[SELECTED_MODEL_INDEX]
                if (
                    selected_model not in disabled_models
                    and CURRENT_PROVIDER == provider_name
                ):
                    AGENT_MODEL = selected_model
                else:
                    # If selected model is disabled, find first enabled model
                    enabled_models = [m for m in models if m not in disabled_models]
                    if enabled_models:
                        AGENT_MODEL = enabled_models[0]

            # Force save to ensure config is updated
            provider_config["disabled_models"] = disabled_models
            config["providers"][provider_name] = provider_config
            save_provider_config(config)

            MODEL_SELECTOR_ACTIVE = False

            # Force screen refresh to update status bar with new AGENT_MODEL
            clear_screen()
            display_screen()
            break
        elif ch == "UP":  # Up arrow
            SELECTED_MODEL_INDEX = max(0, SELECTED_MODEL_INDEX - 1)
        elif ch == "DOWN":  # Down arrow
            SELECTED_MODEL_INDEX = min(total_rows - 1, SELECTED_MODEL_INDEX + 1)
        elif ch == " ":  # SPACE - Toggle model status
            selected_model = models[SELECTED_MODEL_INDEX]

            # Check if this would disable the last enabled model
            enabled_count = len([m for m in models if m not in disabled_models])
            if selected_model not in disabled_models and enabled_count <= 1:
                # Cannot disable the last enabled model
                print("Cannot disable the last enabled model.")
                print("At least one model must remain enabled.")
                print("Press any key to continue...")
                read_char()
            else:
                if selected_model in disabled_models:
                    disabled_models.remove(selected_model)
                else:
                    disabled_models.append(selected_model)
        elif ch == "\r":  # ENTER - Edit max_tokens
            selected_model = models[SELECTED_MODEL_INDEX]
            current_config = models_config.get(selected_model, {})
            current_max_tokens = current_config.get("max_tokens", 4096)

            # Get default value from known_models
            default_config = get_default_model_config(provider_name, selected_model)
            default_max_tokens = default_config.get("max_tokens", 4096)

            # Show current and default values clearly
            print(f"Current max tokens: {current_max_tokens}")
            print(f"Default max tokens: {default_max_tokens}")
            user_input = input("SET MAX TOKENS> ").strip()

            if user_input == "":
                # Use default value from known_models if field is empty
                new_max_tokens = default_max_tokens
            else:
                try:
                    new_max_tokens = int(user_input)
                except ValueError:
                    print("Invalid input. Must be a number.")
                    print("Press any key to continue...")
                    read_char()
                    continue

            # Update the model configuration
            if selected_model not in models_config:
                models_config[selected_model] = {}
            models_config[selected_model]["max_tokens"] = new_max_tokens

            # Update provider config and save
            provider_config["models"] = models_config
            config["providers"][provider_name] = provider_config
            save_provider_config(config)

            print(f"Max tokens for {selected_model} set to {new_max_tokens}")
            print("Press any key to continue...")
            read_char()


def load_state():
    global AGENT_MODEL, AGENT_MODE, history_blocks, CURRENT_PROVIDER
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        session_path = os.path.join(script_dir, "session.json")
        if os.path.exists(session_path):
            with open(session_path, "r") as f:
                data = json.load(f)
                AGENT_MODEL = data.get("model", "deepseek-chat")
                AGENT_MODE = data.get("mode", "WORK")
                history_blocks = data.get("history_blocks", [])
                CURRENT_PROVIDER = data.get("provider", "DeepSeek")
    except:
        pass


def save_state():
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        session_path = os.path.join(script_dir, "session.json")
        with open(session_path, "w") as f:
            json.dump(
                {
                    "model": AGENT_MODEL,
                    "mode": AGENT_MODE,
                    "provider": CURRENT_PROVIDER,
                    "history_blocks": history_blocks,
                },
                f,
                indent=2,
            )
    except:
        pass


def log_api_call(prompt, response):
    try:
        with open("prompt.log", "a", encoding="utf-8") as f:
            f.write("-------\n")
            f.write(f"TIMESTAMP: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("FULL API PROMPT\n")
            f.write(json.dumps(prompt, indent=2, ensure_ascii=False))
            f.write("\n\nFULL API REPLY\n")
            f.write(json.dumps(response, indent=2, ensure_ascii=False))

            # Log the cleaned terminal history that was sent to AI
            if "messages" in prompt and len(prompt["messages"]) > 0:
                content = prompt["messages"][0].get("content", "")
                if "TERMINAL HISTORY" in content:
                    f.write("\n\nCLEANED TERMINAL HISTORY SENT TO AI:\n")
                    # Extract just the terminal history part
                    lines = content.split("\n")
                    in_history = False
                    history_lines = []
                    for line in lines:
                        if line.startswith("TERMINAL HISTORY"):
                            in_history = True
                            continue
                        if in_history and line.startswith(
                            "Evaluate if this is a QUESTION"
                        ):
                            break
                        if in_history:
                            history_lines.append(line)

                    if history_lines:
                        f.write("\n".join(history_lines))
                        f.write(f"\n\nTotal history lines sent: {len(history_lines)}\n")

            f.write("\n-------\n\n")
    except:
        pass


def spinner_animation(stop_event):
    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    idx = 0
    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    while not stop_event.is_set():
        # Overwrite PROMPT> line with spinner on same line
        sys.stdout.write(f"\r{spinner[idx % len(spinner)]} Processing...    ")
        sys.stdout.flush()
        idx += 1
        time.sleep(0.08)

    # Clear the spinner line completely, but stay on same line
    sys.stdout.write("\r" + " " * 30 + "\r")
    # Show cursor again
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()


def call_api(messages, terminal_history=None):
    # Start spinner with proper stop event
    stop_event = threading.Event()
    spinner_thread = threading.Thread(target=spinner_animation, args=(stop_event,))
    spinner_thread.start()

    try:
        import urllib.request

        import requests

        # Get max_tokens for the current model
        max_tokens = get_model_max_tokens(CURRENT_PROVIDER, AGENT_MODEL)

        # Completely separate handling for each provider
        if CURRENT_PROVIDER == "DeepSeek":
            # DeepSeek API call
            payload = {
                "model": AGENT_MODEL,
                "messages": messages,
                "temperature": TEMPERATURE,
                "max_tokens": max_tokens,
            }

            # Add terminal history if provided
            if terminal_history:
                payload["history"] = terminal_history

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            }

            # Make actual DeepSeek API call
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
            )

            with urllib.request.urlopen(req, timeout=None) as response:
                result = json.loads(response.read().decode("utf-8"))

        elif CURRENT_PROVIDER == "ChatGPT":
            # ChatGPT API call
            payload = {
                "model": AGENT_MODEL,
                "messages": messages,
                "temperature": TEMPERATURE,
                "max_tokens": max_tokens,
            }

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {API_KEY}",
            }

            # Make actual ChatGPT API call
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
            )

            with urllib.request.urlopen(req, timeout=None) as response:
                result = json.loads(response.read().decode("utf-8"))

        elif CURRENT_PROVIDER == "Claude":
            # Claude API call - completely different structure
            payload = {
                "model": AGENT_MODEL,
                "max_tokens": max_tokens,
                "messages": messages,
                "temperature": TEMPERATURE,
            }

            headers = {
                "Content-Type": "application/json",
                "x-api-key": API_KEY,
                "anthropic-version": "2023-06-01",
            }

            # Make actual Claude API call
            req = urllib.request.Request(
                API_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
            )

            with urllib.request.urlopen(req, timeout=None) as response:
                result = json.loads(response.read().decode("utf-8"))

        else:
            # Unknown provider - return error
            log(f"{Color.RED}Unknown provider: {CURRENT_PROVIDER}{Color.RESET}")
            return None

        # Stop spinner
        stop_event.set()
        spinner_thread.join()

        # Log the call
        log_api_call(payload, result)

        # Extract response content based on provider
        if CURRENT_PROVIDER == "Claude":
            return result["content"][0]["text"]
        else:
            return result["choices"][0]["message"]["content"]

    except Exception as e:
        stop_event.set()
        spinner_thread.join()
        log(f"{Color.RED}API Error: {str(e)}{Color.RESET}")
        return None


def print_border(text, color, depth=0):
    """Print text with colored border based on depth"""
    border = "█" * (depth + 1)
    lines = text.split("\n")
    for line in lines:
        log(f"{color}{border}{Color.RESET} {line}")


def run_command(cmd):
    global stop_requested
    try:
        process = subprocess.Popen(
            cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        stdout, stderr = process.communicate()

        if stop_requested:
            try:
                process.kill()
            except:
                pass
            return None, "Stopped by user"

        return stdout.strip(), stderr.strip() if stderr else None

    except Exception as e:
        return None, str(e)


def ask_user_confirmation(cmd):
    """Ask user to confirm dangerous command"""
    display_screen()
    print(f"\n{Color.YELLOW}⚠️  Dangerous command requires confirmation:{Color.RESET}")
    print(f"{Color.WHITE}{cmd}{Color.RESET}")
    print("Type 'yes' to continue or anything else to abort: ", end="", flush=True)

    answer = input().strip().lower()
    return answer == "yes"


def get_terminal_width():
    """Get the current terminal width, with fallback to 80"""
    try:
        columns, _ = shutil.get_terminal_size()
        return max(columns, 80)  # Minimum 80 columns
    except:
        return 80  # Fallback width


def display_screen():
    """Render the screen by reading from session.log"""
    clear_screen()

    # Read and display all content from session.log
    session_content = read_session_log()
    if session_content:
        print(session_content)

    # Calculate prompt tokens from system prompt + history + estimated user prompt
    prompt_tokens = 0
    system_info = get_system_info()

    # Base system prompt tokens (approximate)
    if AGENT_MODE == "ASK":
        base_prompt = """You are a helpful AI assistant. The user is asking a question and wants a detailed, informative answer.

System context:

Provide a comprehensive answer to the user's question. Be detailed and helpful.
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Use this format:
{
            "type": "answer",
    "message": "Your detailed answer to the user's question"
}"""
    else:  # WORK mode
        base_prompt = """You are a SYSTEM AGENT.
System:
User prompt:
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Evaluate if this is a QUESTION or a TASK.
- Question: User wants information (max 5 commands to gather info)
- Task: User wants you to perform actions

If the user is asking about our previous conversation (what we discussed before, previous questions, etc.), you can answer directly using the conversation history above without running commands. Use this format:
{
            "type": "direct",
    "message": "Your direct answer using the conversation history"
}

For QUESTION:
{
            "type": "query",
    "message": "Brief description of what you WILL DO to answer (not the answer itself!)",
    "run": [
        {
                "message": "Why we're running this command",
            "command": "the command",
            "confirm": false
        }
    ]
}

For TASK:
{
            "type": "task",
    "message": "Brief summary of the task plan",
    "run": [
        {
                "message": "What this step does",
            "command": "the command",
            "confirm": false
        }
    ]
}

IMPORTANT:
- For 'message': describe what you WILL DO, not the result (you don't know the result yet!)
- Use only CLI commands, never TUI (no htop, nano, mc, mysql_secure_installation, etc)
- Set 'confirm': true for dangerous/system-changing commands
- Escape JSON properly"""

    # Add system info and estimated user prompt (50 tokens ~200 chars)
    base_prompt += system_info
    base_tokens = max(1, len(base_prompt) // 4) + 50  # +50 for user prompt

    # Add history tokens
    if history_blocks:
        history_text = "For reference, this is our conversation history summarized. Do not interpret this as part of the user question or task.\n"
        history_text += "This is for you to understand what we've done already so that you can give better answers and solutions to questions and tasks.\n"
        history_text += "These history entries are added in chronological order, where 1 is oldest:\n"
        for i, block in enumerate(history_blocks, 1):
            user_prompt = block.get("user_prompt", "No user prompt")
            summary = block.get("summary", "No summary")
            history_text += f"{i}) User: {user_prompt}\n   Agent: {summary}\n"
        history_text += "\n"
        history_tokens = max(1, len(history_text) // 4)
        prompt_tokens = base_tokens + history_tokens
    else:
        prompt_tokens = base_tokens

    # Get terminal width
    terminal_width = get_terminal_width()

    # Print status bar with dynamic borders
    print(f"{Color.FG_LIGHTER_GREEN}_{Color.RESET}" * terminal_width)
    model_display = AGENT_MODEL
    # Apply different background colors for ASK and WORK modes
    mode_display = AGENT_MODE
    if AGENT_MODE == "ASK":
        mode_display = f"{Color.BG_ASK}{AGENT_MODE}{Color.BG_DARK_GREEN}"
    elif AGENT_MODE == "WORK":
        mode_display = f"{Color.BG_WORK}{AGENT_MODE}{Color.BG_DARK_GREEN}"

    # Build status text with adaptive content based on terminal width
    if terminal_width >= 150:
        # Full status for very wide terminals
        status_text = f"🤖 AGENT [{model_display.upper()}]: CTRL+T     PROVIDER: CTRL+W     MODE [{mode_display}]: CTRL+P     HISTORY [{len(history_blocks)}]: CTRL+H     QUIT: CTRL+C"
    elif terminal_width >= 120:
        # Wide status - remove some token details
        status_text = f"🤖 AGENT [{model_display.upper()}]: CTRL+T     PROVIDER: CTRL+W     MODE [{mode_display}]: CTRL+P     HISTORY [{len(history_blocks)}]: CTRL+H     QUIT: CTRL+C"
    elif terminal_width >= 100:
        # Medium status - remove token details
        status_text = f"🤖 AGENT [{model_display.upper()}]: T     PROVIDER: W     MODE [{mode_display}]: P     HISTORY [{len(history_blocks)}]: H     QUIT: C"
    elif terminal_width >= 80:
        # Compact status - keep only essential info
        status_text = f"🤖 AGENT [{model_display.upper()}]: T     MODE [{mode_display}]: P     HISTORY [{len(history_blocks)}]: H     QUIT: C"
    else:
        # Minimal status for very narrow terminals
        status_text = f"🤖 AGENT [{model_display.upper()}]: T     MODE [{mode_display}]: P     QUIT: C"

    # Fill the rest of the line with background color (subtract 1 to avoid wrapping)
    padding = " " * (terminal_width - visual_length(status_text) - 1)
    print(f"{Color.BG_DARK_GREEN}{status_text}{padding}{Color.RESET}")

    # Print closing bar but use write instead of print to control newline
    sys.stdout.write(f"{Color.FG_DARKER_GREEN}‾{Color.RESET}" * terminal_width + "\n")
    sys.stdout.flush()
    # Don't print PROMPT> here - it's handled in main loop


def handle_run_commands(run_list, color, depth, user_prompt, parent_data):
    """Execute a list of commands from AI response"""
    global stop_requested

    # Store all command results
    all_results = []

    for cmd_item in run_list:
        if stop_requested:
            log(f"{Color.RED}⚠️  Execution stopped by user{Color.RESET}")
            display_screen()
            return False

        message = cmd_item.get("message", "")
        command = cmd_item.get("command", "")
        confirm = cmd_item.get("confirm", False)

        # Print what we're doing
        log("")
        print_border(f"💡 {message}", color, depth)
        print_border(f"⚙️  {command}", color, depth)
        display_screen()  # Show progress immediately

        # Check if confirmation needed
        if confirm:
            if not ask_user_confirmation(command):
                log(f"{Color.RED}⚠️  Command aborted by user{Color.RESET}")
                display_screen()
                continue

        # Run the command
        stdout, stderr = run_command(command)

        if stop_requested:
            return False

        # Display result - show full stdout or stderr
        if stderr:
            # Show the actual stderr output
            stderr_lines = stderr.split("\n")
            for line in stderr_lines[:20]:  # Max 20 lines to avoid overflow
                print_border(f"🚫 {line}", color, depth)
            if len(stderr_lines) > 20:
                print_border(
                    f"🚫 ... ({len(stderr_lines) - 20} more lines)", color, depth
                )
            display_screen()  # Show error immediately

            # If this is a task or issue, we need to recurse
            if color in [Color.BLUE, Color.RED]:
                success = handle_error_recursion(
                    user_prompt, parent_data, command, stderr, stdout, depth
                )
                if not success:
                    return False
        else:
            # Show the actual stdout output
            if stdout:
                stdout_lines = stdout.split("\n")
                for line in stdout_lines[:20]:  # Max 20 lines to avoid overflow
                    print_border(f"✅ {line}", color, depth)
                if len(stdout_lines) > 20:
                    print_border(
                        f"✅ ... ({len(stdout_lines) - 20} more lines)", color, depth
                    )
            else:
                print_border(f"✅ (no output)", color, depth)
            display_screen()  # Show success immediately

        # Store result for final explanation
        all_results.append(
            {"command": command, "message": message, "stdout": stdout, "stderr": stderr}
        )

    # After ALL commands are done, get ONE final explanation
    if all_results and color == Color.GREEN:
        log("")
        explanation = get_final_explanation(user_prompt, all_results, parent_data)
        if explanation:
            print_border(f"🤖 {explanation}", Color.WHITE, depth)
            display_screen()  # Show final answer

    return True


def get_final_explanation(user_prompt, results, parent_data):
    """Get AI explanation of ALL command results together"""

    # Build results summary
    results_text = ""
    for r in results:
        results_text += f"\nCommand: {r['command']}\n"
        results_text += f"Purpose: {r['message']}\n"
        results_text += f"STDOUT: {r['stdout'] if r['stdout'] else '(empty)'}\n"
        results_text += f"STDERR: {r['stderr'] if r['stderr'] else '(none)'}\n"

    explain_prompt = f"""You are a SYSTEM AGENT.
User's question: {user_prompt}

You ran these commands and got these results:
{results_text}

Based on ALL the results above, provide a clear answer to the user's original question.
Be concise and direct. Use 2-4 sentences maximum.
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Use the command results above to provide your answer."""

    messages = [{"role": "user", "content": explain_prompt}]
    response = call_api(messages)

    return response if response else None


def handle_error_recursion(
    user_prompt, parent_data, failed_cmd, stderr, stdout, depth, issue_history=None
):
    """Handle recursive error resolution"""
    global stop_requested

    if depth >= 10:
        log("")
        log(f"{Color.RED}❌ Giving up after 10 recursive attempts...{Color.RESET}")
        return False

    if issue_history is None:
        issue_history = []

    system_info = get_system_info()

    # Build planned commands list
    planned_commands = "\n".join(
        [c.get("command", "") for c in parent_data.get("run", [])]
    )

    # Build previous attempts
    attempts_text = ""
    if issue_history:
        attempts_text = "Previous failed attempts:\n"
        for item in issue_history[-20:]:
            attempts_text += (
                f"- Command: {item['command']}\n  Error: {item['stderr']}\n"
            )

    # Create issue resolution prompt
    issue_prompt = f"""You are a SYSTEM AGENT.
This is the system: {system_info}
Your mission: {user_prompt}
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Planned commands to complete the mission:
{planned_commands}

Current problem:
Command: {failed_cmd}
Error: {stderr}

{attempts_text}

Analyze the error and provide a solution command to fix it.
Keep in mind you are an agent using only CLI, never TUI tools (no htop, nano, mc, etc).
For dangerous commands, set 'confirm' to true.

Respond ONLY with valid JSON:
{{
    "type": "issue",
    "message": "Brief explanation of the fix approach",
    "run": [
        {{
            "message": "What this command does",
            "command": "the actual command",
            "confirm": false
        }}
    ]
}}

Use the terminal history and previous attempts above to understand the context."""

    messages = [{"role": "user", "content": issue_prompt}]
    response = call_api(messages)

    if not response or stop_requested:
        return False

    # Parse response
    try:
        issue_data = json.loads(response)
    except:
        log(f"{Color.RED}Failed to parse AI response for error handling{Color.RESET}")
        return False

    # Print issue message
    log("")
    print_border(
        f"💡 {issue_data.get('message', 'Attempting to resolve error...')}",
        Color.RED,
        depth + 1,
    )

    # Execute issue resolution commands
    if "run" in issue_data:
        for cmd_item in issue_data["run"]:
            if stop_requested:
                return False

            message = cmd_item.get("message", "")
            command = cmd_item.get("command", "")
            confirm = cmd_item.get("confirm", False)

            log("")
            print_border(f"💡 {message}", Color.RED, depth + 1)
            print_border(f"⚙️  {command}", Color.RED, depth + 1)

            if confirm:
                if not ask_user_confirmation(command):
                    log(f"{Color.RED}⚠️  Resolution aborted by user{Color.RESET}")
                    return False

            stdout_new, stderr_new = run_command(command)

            if stderr_new:
                print_border(f"🚫 {stderr_new[:500]}", Color.RED, depth + 1)

                # Add to history and recurse deeper
                issue_history.append({"command": command, "stderr": stderr_new})

                return handle_error_recursion(
                    user_prompt,
                    parent_data,
                    command,
                    stderr_new,
                    stdout_new,
                    depth + 1,
                    issue_history,
                )
            else:
                output = stdout_new[:300] if stdout_new else "Success"
                print_border(f"✅ {output}", Color.RED, depth + 1)
                log("")
                print_border(
                    f"🤖 Issue resolved! Continuing...", Color.WHITE, depth + 1
                )
                return True

    return False


def process_user_prompt(user_prompt):
    """Main entry point for processing user input"""
    global stop_requested

    stop_requested = False

    system_info = get_system_info()

    # Build history from all previous blocks
    history_text = ""
    if history_blocks:
        history_text = "For reference, this is our conversation history summarized. Do not interpret this as part of the user question or task.\n"
        history_text += "This is for you to understand what we've done already so that you can give better answers and solutions to questions and tasks.\n"
        history_text += "These history entries are added in chronological order, where 1 is oldest:\n"
        for i, block in enumerate(history_blocks, 1):  # ALL blocks for context
            history_user_prompt = block.get("user_prompt", "No user prompt")
            summary = block.get("summary", "No summary")
            history_text += f"{i}) User: {history_user_prompt}\n   Agent: {summary}\n"
        history_text += "\n"

    # Main prompt to AI
    if AGENT_MODE == "ASK":
        main_prompt = f"""You are a helpful AI assistant. The user is asking a question and wants a detailed, informative answer.

System context: {system_info}
User question: {user_prompt}

{history_text}
Provide a comprehensive answer to the user's question. Be detailed and helpful.
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

Use this format:
{{
    "type": "answer",
    "message": "Your detailed answer to the user's question"
}}"""
    else:  # WORK mode
        main_prompt = f"""You are a SYSTEM AGENT.
System: {system_info}
User prompt: {user_prompt}
VERY IMPORTANT! You MUST respond in the same language as the User prompt.

{history_text}
Evaluate if this is a QUESTION or a TASK.
- Question: User wants information (max 5 commands to gather info)
- Task: User wants you to perform actions

For QUESTION:
{{
    "type": "query",
    "message": "Brief description of what you WILL DO to answer (not the answer itself!)",
    "run": [
        {{
            "message": "Why we're running this command",
            "command": "the command",
            "confirm": false
        }}
    ]
}}

For TASK:
{{
    "type": "task",
    "message": "Brief summary of the task plan",
    "run": [
        {{
            "message": "What this step does",
            "command": "the command",
            "confirm": false
        }}
    ]
}}

IMPORTANT:
- For 'message': describe what you WILL DO, not the result (you don't know the result yet!)
- Use only CLI commands, never TUI (no htop, nano, mc, mysql_secure_installation, etc)
- Set 'confirm': true for dangerous/system-changing commands
- Escape JSON properly"""

    messages = [{"role": "user", "content": main_prompt}]
    response = call_api(messages)

    if not response:
        log(f"{Color.RED}Failed to get AI response{Color.RESET}")
        return

    # Parse JSON response - first extract from markdown code blocks if needed
    try:
        clean_response = extract_json_from_markdown(response)
        data = json.loads(clean_response)
    except:
        log(f"{Color.RED}Failed to parse AI response{Color.RESET}")
        log(f"Raw: {response[:500]}")
        return

    response_type = data.get("type", "")
    message = data.get("message", "")

    # Determine color based on type
    if response_type == "query":
        color = Color.GREEN
    elif response_type == "task":
        color = Color.BLUE
    elif response_type == "direct":
        color = Color.CYAN
        # For direct responses, we don't need to run commands
        log(f"{color}🤖 {message}{Color.RESET}")
        return
    elif response_type == "knowledge":
        color = Color.YELLOW
        # For knowledge responses, we don't need to run commands
        log(f"{color}🤖 {message}{Color.RESET}")
        return
    elif response_type == "answer":
        color = Color.MAGENTA
        # For ASK mode answers, we don't need to run commands
        # Clean markdown formatting for better terminal display
        clean_message = clean_markdown_formatting(message)
        log(f"{color}🤖 {clean_message}{Color.RESET}")

        # Create history block for ASK mode responses too
        create_history_block(user_prompt, message)

        # Save state
        save_state()
        return
    else:
        color = Color.WHITE

    # Print AI's plan
    if message:
        print_border(f"🤖 {message}", Color.WHITE, 0)
        display_screen()  # Show plan immediately

    # Execute commands
    if "run" in data:
        handle_run_commands(data["run"], color, 0, user_prompt, data)

    # After execution is complete, create a history block
    create_history_block(user_prompt, message)

    # Save state
    save_state()


def summarize_block(block_text):
    """Use AI to summarize a block of terminal activity"""
    summary_prompt = f"""You are a SYSTEM AGENT. Analyze this terminal session block and provide a very concise one-line summary.

TERMINAL BLOCK:
{block_text}

Provide a one-line summary in the same language as the user, focusing on:
- What was done
- What the result was
- Key findings or issues

Keep it extremely brief (max 15 words)."""

    messages = [{"role": "user", "content": summary_prompt}]
    response = call_api(messages)

    if response:
        try:
            # Try to parse as JSON first, then fall back to raw text
            data = json.loads(response)
            return data.get("summary", response[:100])
        except:
            return response[:100]  # Truncate if too long
    return "No summary available"


def create_history_block(user_prompt, ai_message):
    """Create a summarized history block after prompt completion"""
    global history_blocks

    # Find the start of this block (last separator before current prompt)
    terminal_width = get_terminal_width()
    separator = "~" * terminal_width
    start_index = -1

    # Read from session.log and find the separator
    session_content = read_session_log()
    log_lines = session_content.split("\n")

    # Look backwards for the separator that marks the start of this session
    for i in range(len(log_lines) - 1, -1, -1):
        if separator in log_lines[i] and "USER PROMPT>" in log_lines[max(0, i - 1)]:
            start_index = i
            break

    if start_index == -1:
        # If no separator found, use last 50 lines as fallback
        block_lines = log_lines[-50:]
    else:
        # Extract everything from the separator to the end
        block_lines = log_lines[start_index:]

    # Clean the block text
    cleaned_block = []
    for line in block_lines:
        cleaned = strip_ansi_codes(line)
        if cleaned:
            cleaned_block.append(cleaned)

    block_text = "\n".join(cleaned_block)

    # Get AI summary of the block
    summary = summarize_block(block_text)

    # Create history block with mode and model information
    history_block = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "user_prompt": user_prompt,
        "ai_plan": ai_message,
        "summary": summary,
        "mode": AGENT_MODE,
        "model": AGENT_MODEL,
    }

    history_blocks.append(history_block)

    # Keep only last 50 blocks to prevent file from growing too large
    if len(history_blocks) > 50:
        history_blocks = history_blocks[-50:]

    # Save history to file
    save_state()


def read_char():
    """Read a single character without waiting for enter, handles arrow keys"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)

        # Handle escape sequences (arrow keys and delete)
        if ch == "\x1b":  # ESC character
            # Read the next two characters
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            if ch2 == "[":
                if ch3 == "A":  # Up arrow
                    return "UP"
                elif ch3 == "B":  # Down arrow
                    return "DOWN"
                elif ch3 == "C":  # Right arrow
                    return "RIGHT"
                elif ch3 == "D":  # Left arrow
                    return "LEFT"
                elif ch3 == "3":  # Delete key (part 1)
                    ch4 = sys.stdin.read(1)  # Read the ~ character
                    if ch4 == "~":
                        return "DEL"

        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    global \
        AGENT_MODEL, \
        stop_requested, \
        PROVIDERS_VIEWER_ACTIVE, \
        SELECTED_PROVIDER_INDEX, \
        CURRENT_PROVIDER, \
        HISTORY_VIEWER_ACTIVE, \
        SELECTED_HISTORY_INDEX, \
        MODEL_SELECTOR_ACTIVE, \
        SELECTED_MODEL_INDEX, \
        API_URL, \
        API_KEY

    # Set up signal handler to restore terminal on exit
    def signal_handler(sig, frame):
        # Restore terminal settings
        fd = sys.stdin.fileno()
        if hasattr(main, "original_termios"):
            termios.tcsetattr(fd, termios.TCSADRAIN, main.original_termios)
        print("\n\n👋 Exiting...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Save original terminal settings
    fd = sys.stdin.fileno()
    main.original_termios = termios.tcgetattr(fd)

    # Load previous session and history
    load_state()

    # Load config and set correct provider/model based on enabled providers
    config = load_provider_config()
    providers = config.get("providers", {})

    # Find the first enabled provider and its first enabled model
    enabled_providers = [
        name
        for name, provider_config in providers.items()
        if provider_config.get("enabled", False)
    ]

    if enabled_providers:
        # Use the first enabled provider
        CURRENT_PROVIDER = enabled_providers[0]
        provider_config = providers.get(CURRENT_PROVIDER, {})

        # Find first enabled model for this provider
        models = provider_config.get("models", [])
        disabled_models = provider_config.get("disabled_models", [])
        enabled_models = [m for m in models if m not in disabled_models]

        if enabled_models:
            AGENT_MODEL = enabled_models[0]
        else:
            # Fallback to first model if all are disabled (shouldn't happen due to validation)
            AGENT_MODEL = models[0] if models else "unknown-model"

    # Update API configuration based on selected provider
    provider_config = providers.get(CURRENT_PROVIDER, {})
    API_URL = provider_config.get("endpoint", "")
    API_KEY = provider_config.get("api_key", "")

    # Set up signal handler to restore terminal on exit
    def signal_handler(sig, frame):
        # Restore terminal settings
        fd = sys.stdin.fileno()
        if hasattr(main, "original_termios"):
            termios.tcsetattr(fd, termios.TCSADRAIN, main.original_termios)
        print("\n\n👋 Exiting...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Save original terminal settings
    fd = sys.stdin.fileno()
    main.original_termios = termios.tcgetattr(fd)

    # Load previous session and history
    load_state()

    # Load config and set correct provider/model based on enabled providers
    config = load_provider_config()
    providers = config.get("providers", {})

    # Find the first enabled provider and its first enabled model
    enabled_providers = [
        name
        for name, provider_config in providers.items()
        if provider_config.get("enabled", False)
    ]

    if enabled_providers:
        # Use the first enabled provider
        CURRENT_PROVIDER = enabled_providers[0]
        provider_config = providers.get(CURRENT_PROVIDER, {})

        # Find first enabled model for this provider
        models = provider_config.get("models", [])
        disabled_models = provider_config.get("disabled_models", [])
        enabled_models = [m for m in models if m not in disabled_models]

        if enabled_models:
            AGENT_MODEL = enabled_models[0]
        else:
            # Fallback to first model if all are disabled (shouldn't happen due to validation)
            AGENT_MODEL = models[0] if models else "unknown-model"

        # Update API configuration based on selected provider
        API_URL = provider_config.get("endpoint", "")
        API_KEY = provider_config.get("api_key", "")
    else:
        # No enabled providers, use defaults
        CURRENT_PROVIDER = "DeepSeek"
        AGENT_MODEL = "deepseek-chat"
        API_URL = ""
        API_KEY = ""

    # Create config.json if it doesn't exist
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, "config.json")
    if not os.path.exists(config_path):
        default_config = {
            "providers": {
                "DeepSeek": {
                    "enabled": False,
                    "api_key": "",
                    "endpoint": "https://api.deepseek.com/v1/chat/completions",
                    "models": [],
                    "disabled_models": [],
                },
                "ChatGPT": {
                    "enabled": False,
                    "api_key": "",
                    "endpoint": "https://api.openai.com/v1/chat/completions",
                    "models": [],
                    "disabled_models": [],
                },
                "Claude": {
                    "enabled": False,
                    "api_key": "",
                    "endpoint": "https://api.anthropic.com/v1/messages",
                    "models": [],
                    "disabled_models": [],
                },
            }
        }
        save_provider_config(default_config)

    # Check if any provider has an API key
    config = load_provider_config()
    providers = config.get("providers", {})
    has_api_key = any(provider.get("api_key", "") for provider in providers.values())

    # API configuration is already set from startup initialization

    # If no API key is set, force user to providers menu
    if not has_api_key:
        print("No API keys configured. Please set up at least one provider.")
        print("Press any key to continue to providers menu...")
        read_char()
        PROVIDERS_VIEWER_ACTIVE = True
        SELECTED_PROVIDER_INDEX = 0
        show_providers_viewer()

    # Initial display - session.log will be read and displayed in display_screen()
    display_screen()

    # Show initial PROMPT>
    prompt_text = f"{Color.GREEN}PROMPT>{Color.RESET} "
    sys.stdout.write(prompt_text)
    sys.stdout.flush()

    while True:
        try:
            # Show prompt
            # (PROMPT> is already showing from previous iteration or startup)

            # Read input with special key handling
            user_input = ""
            while True:
                ch = read_char()

                # Handle special key strings first
                if ch in ["UP", "DOWN", "LEFT", "RIGHT", "DEL"]:
                    # Ignore arrow keys and delete in prompt mode
                    continue

                # Ctrl+C
                elif isinstance(ch, str) and len(ch) == 1 and ord(ch) == 3:
                    print("\n\n👋 Exiting...")
                    sys.exit(0)

                # Ctrl+M
                elif (
                    isinstance(ch, str)
                    and len(ch) == 1
                    and ord(ch) == 13
                    and user_input == ""
                ):
                    # Empty enter - just newline
                    print()
                    break
                elif isinstance(ch, str) and len(ch) == 1 and ord(ch) == 13:
                    # Enter with content - DON'T print newline, just break
                    # The spinner will take over on the same line
                    break

                # Backspace
                elif isinstance(ch, str) and len(ch) == 1 and ord(ch) == 127:
                    if user_input:
                        user_input = user_input[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()

                # Ctrl+T (ASCII 20)
                elif (
                    isinstance(ch, str)
                    and len(ch) == 1
                    and ord(ch) == 20
                    and len(user_input) == 0
                ):
                    # Ctrl+T pressed - switch model immediately
                    user_input = "ctrl+t"  # Set to trigger model switch
                    break

                # Ctrl+P (ASCII 16)
                elif (
                    isinstance(ch, str)
                    and len(ch) == 1
                    and ord(ch) == 16
                    and len(user_input) == 0
                ):
                    # Ctrl+P pressed - switch mode immediately
                    user_input = "ctrl+p"  # Set to trigger mode switch
                    break

                # Ctrl+H (ASCII 8)
                elif (
                    isinstance(ch, str)
                    and len(ch) == 1
                    and ord(ch) == 8
                    and len(user_input) == 0
                ):
                    # Ctrl+H pressed - open history viewer immediately
                    user_input = "ctrl+h"  # Set to trigger history viewer
                    break

                # Ctrl+W (ASCII 23)
                elif (
                    isinstance(ch, str)
                    and len(ch) == 1
                    and ord(ch) == 23
                    and len(user_input) == 0
                ):
                    # Ctrl+W pressed - open providers viewer immediately
                    user_input = "ctrl+w"  # Set to trigger providers viewer
                    break

                # Regular character
                elif isinstance(ch, str) and len(ch) == 1 and ord(ch) >= 32:
                    sys.stdout.write(ch)
                    sys.stdout.flush()
                    user_input += ch

            # Check for model switch command (including Ctrl+T)
            if user_input.strip().lower() in ["t", "\\t", "ctrl+t", "ctrl-t"]:
                # Always load latest config to ensure we have the most recent state
                config = load_provider_config()
                providers = config.get("providers", {})

                # Get all available models from enabled providers
                all_models = []
                for provider_name, provider_config in providers.items():
                    if provider_config.get("enabled", False):
                        # Use models from config.json, fallback to empty dict
                        models_config = provider_config.get("models", {})
                        for model_name, model_config in models_config.items():
                            # Only include models that are enabled
                            if model_config.get("enabled", True):
                                all_models.append(f"{provider_name}: {model_name}")

                # If no enabled providers, no models available
                if not all_models:
                    all_models = [("NoProvider", "no-models-available")]

                # Find current model in the list - use the actual current provider from config
                current_model_index = -1
                for i, provider_model_str in enumerate(all_models):
                    if ":" in provider_model_str:
                        provider, model = provider_model_str.split(": ", 1)
                        if provider == CURRENT_PROVIDER and model == AGENT_MODEL:
                            current_model_index = i
                            break

                # If current model not found, set the first model in all_models as active
                if current_model_index == -1:
                    if all_models:
                        # Set the first model in the available list as active
                        CURRENT_PROVIDER, AGENT_MODEL = all_models[0]
                        current_model_index = 0
                    else:
                        current_model_index = 0
                else:
                    # Cycle to next model
                    current_model_index = (current_model_index + 1) % len(all_models)

                # Set new provider and model
                provider_model_str = all_models[current_model_index]
                if ":" in provider_model_str:
                    CURRENT_PROVIDER, AGENT_MODEL = provider_model_str.split(": ", 1)
                else:
                    # Fallback for "NoProvider: no-models-available"
                    CURRENT_PROVIDER = "NoProvider"
                    AGENT_MODEL = "no-models-available"

                # Update API configuration
                config = load_provider_config()
                provider_config = config.get("providers", {}).get(CURRENT_PROVIDER, {})
                API_URL = provider_config.get("endpoint", "")
                API_KEY = provider_config.get("api_key", "")

                save_state()

                display_screen()
                # Show PROMPT> again (no extra spacing)
                sys.stdout.write(f"{Color.GREEN}PROMPT>{Color.RESET} ")
                sys.stdout.flush()
                continue

            # Check for history viewer command (including Ctrl+H)
            if user_input.strip().lower() in ["h", "\\h", "ctrl+h", "ctrl-h"]:
                # Open history viewer
                HISTORY_VIEWER_ACTIVE = True
                SELECTED_HISTORY_INDEX = 0
                show_history_viewer()

                # Refresh display after exiting history viewer
                display_screen()
                # Show PROMPT> again (no extra spacing)
                sys.stdout.write(f"{Color.GREEN}PROMPT>{Color.RESET} ")
                sys.stdout.flush()
                continue

            # Check for providers viewer command (including Ctrl+W)
            if user_input.strip().lower() in ["w", "\\w", "ctrl+w", "ctrl-w"]:
                # Open providers viewer
                PROVIDERS_VIEWER_ACTIVE = True
                SELECTED_PROVIDER_INDEX = 0
                show_providers_viewer()

                # Refresh display after exiting providers viewer
                display_screen()
                # Show PROMPT> again (no extra spacing)
                sys.stdout.write(f"{Color.GREEN}PROMPT>{Color.RESET} ")
                sys.stdout.flush()
                continue

            # Check for mode switch command (including Ctrl+P)
            if user_input.strip().lower() in ["p", "\\p", "ctrl+p", "ctrl-p"]:
                # Toggle between modes
                global AGENT_MODE
                AGENT_MODE = "ASK" if AGENT_MODE == "WORK" else "WORK"

                save_state()

                display_screen()
                # Show PROMPT> again (no extra spacing)
                sys.stdout.write(f"{Color.GREEN}PROMPT>{Color.RESET} ")
                sys.stdout.flush()
                continue

            # Skip empty input
            if not user_input.strip():
                # For empty input, we need to print newline and redisplay
                print()
                display_screen()
                print()  # Add spacing
                # Show PROMPT> again
                prompt_text = f"{Color.GREEN}PROMPT>{Color.RESET} "
                sys.stdout.write(prompt_text)
                sys.stdout.flush()
                continue

            # Log user input (now we can print newline in the log)
            terminal_width = get_terminal_width()
            log("~" * terminal_width)
            log(f"{Color.GREEN}👤 USER PROMPT>{Color.RESET} {user_input}")
            log("")  # Add linebreak between prompt and response

            # Process the prompt (spinner will overwrite PROMPT> line)
            process_user_prompt(user_input.strip())

            # Refresh display (clears screen and shows all logs)
            display_screen()

            # Now show PROMPT> again for next input (no extra newline!)
            sys.stdout.write(f"{Color.GREEN}PROMPT>{Color.RESET} ")
            sys.stdout.flush()

        except KeyboardInterrupt:
            # Restore terminal settings
            fd = sys.stdin.fileno()
            if hasattr(main, "original_termios"):
                termios.tcsetattr(fd, termios.TCSADRAIN, main.original_termios)
            print("\n\n👋 Exiting...")
            break
        except Exception as e:
            log(f"{Color.RED}Error: {str(e)}{Color.RESET}")
            display_screen()


if __name__ == "__main__":
    main()
