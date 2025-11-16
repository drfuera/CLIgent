# CLIgent - AI-Powered Command Line Interface Assistant

CLIgent is a powerful command-line assistant that leverages AI models (DeepSeek, ChatGPT, Claude) to assist users with command-line tasks, explanations, and troubleshooting. It acts as an intelligent agent capable of interpreting user input, generating relevant commands, executing them (with user confirmation when necessary), and summarizing the results.

## Features

*   **AI Assistance**: Interactive help with command-line tasks using multiple AI providers.
*   **Command Execution**: Safe execution of AI-suggested commands with user confirmation for potentially dangerous operations.
*   **Session Logging and History**: Ensures traceability and the ability to review previous sessions and AI interactions.
*   **Real-time API Calls**: With visual indicators (spinner) during AI response waits.
*   **Error Handling and Recursion**: AI can attempt to resolve issues occurring during command execution by generating new solutions.
*   **Markdown Cleaning**: AI responses are cleaned of unnecessary markdown formatting for better terminal display.
*   **Model and Provider Selection**: Easy switching between different AI models and providers (DeepSeek, ChatGPT, Claude).
*   **Work/Ask Modes**: Choose between `WORK` mode (for performing tasks) and `ASK` mode (for asking questions).
*   **History Viewer**: Browse and review previous AI interactions in a table view.
*   **Configurable Settings**: Configuration file (`config.json`) for API keys, provider settings, and model management.

## Screenshot

![CLIgent Screencap](screencap.gif)
*Example screenshot showing CLIgent in action, displaying AI response and command execution in the terminal.*

## Prerequisites

*   Python 3.x
*   The following Python packages (can be installed via `pip` if not already available via the system):
    *   `requests`
    *   (Other modules like `urllib`, `json`, `subprocess` etc. are built into Python and also required)

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/drfuera/CLIgent.git
    cd CLIgent
    ```

2.  (Optional but recommended) Create a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  Make the script executable (Linux/macOS):
    ```bash
    chmod +x cligent.py
    ```

## Configuration

On the first run of `cligent.py` without configured API keys, you will be redirected to the provider settings.

1.  **Start CLIgent**:
    ```bash
    python cligent.py
    ```
    (or `./cligent.py` if executable)

2.  **Configure Provider**: You will be prompted to configure at least one provider.
    *   Press `T` or `Ctrl+W` to open the provider settings.
    *   Use arrow keys (`↑`/`↓`) to navigate between providers (DeepSeek, ChatGPT, Claude).
    *   Press `Enter` on a provider to enable it. You will be prompted to enter your API key for that provider. If you enter an empty key but have one saved, the saved key will be used.
    *   Press `Space` to open the model selector for an enabled provider.
    *   Press `Backspace` to leave the provider settings. You must have at least one provider enabled with an API key to proceed.

3.  **Configuration File**: Settings are automatically saved in `config.json` in the same directory as the script.

## Usage

*   **Start**: `python cligent.py` or `./cligent.py`
*   **Use**: Type your question or describe your task after the `PROMPT>` prompt.
*   **AI Response**: CLIgent interprets your input, communicates with AI, and displays its plan and/or executes commands in the terminal.
*   **Stop**: Press `Ctrl+C` at any time to quit.
*   **Controls during runtime** (from the `PROMPT>` prompt):
    *   `Ctrl+T` or `T`: Switch between available AI models.
    *   `Ctrl+P` or `P`: Switch between `WORK` and `ASK` modes.
    *   `Ctrl+H` or `H`: Open the history view.
    *   `Ctrl+W` or `W`: Open the provider settings.

## Status Bar

A status bar at the bottom of the interface displays:
*   Current AI model
*   Active provider (if applicable)
*   Current mode (WORK/ASK)
*   Number of history entries
*   Shortcuts for various functions

## Session and History

*   All activity is logged to `session.log`.
*   Summary history entries are saved in `session.json`.
*   The history view (`Ctrl+H`) shows previous interactions in a table, allowing navigation and deletion of entries.

## Model Selector

*   When a provider is enabled, you can use the model selector (`Ctrl+T` or from provider settings) to enable/disable models and manage settings per model (e.g., `max_tokens`).

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

MIT

## Acknowledgements / Creator's Comments

*   Developed by Andrej Fuera.
*   AI is lovely; But nobody loves like Jesus.
*   All glory to the one true God, full of patience and mercy.
*   Matt. 5:3
*   Blessed are the poor in spirit: for theirs is the kingdom of heaven.
*   Rom. 10:13
*   For whosoever shall call upon the name of the Lord shall be saved.
