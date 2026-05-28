"""Auto-registration — batch tool definitions for all new features.

Returns lists of (name, description, parameters, handler, category) tuples
that agent.py imports and registers in one pass.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def _make_tool(name, description, params, handler, category="utility"):
    from backend.orchestrator.agent import Tool
    return Tool(name=name, description=description, parameters=params, handler=handler, category=category)


# ---------------------------------------------------------------------------
# Build all tool lists
# ---------------------------------------------------------------------------

def get_computer_control_tools():
    from backend.tools.computer_control import (
        system_settings_control, keyboard_shortcut_discover, multi_monitor_info,
        startup_program_list, startup_program_add, startup_program_remove,
        peripheral_list, accessibility_toggle, remote_desktop_start, remote_desktop_list_sessions,
        macro_record_start, macro_record_step, macro_record_stop, macro_run, macro_list, macro_delete,
        orchestrate_sequence,
    )
    return [
        _make_tool("system_settings_control", "Control system settings: volume, brightness, wifi, bluetooth, volume_mute", {"type": "object", "properties": {"setting": {"type": "string", "description": "Setting name: volume, brightness, wifi, bluetooth, volume_mute"}, "value": {"type": "string", "description": "Value to set"}}, "required": ["setting", "value"]}, system_settings_control, "system"),
        _make_tool("keyboard_shortcut_discover", "Discover Windows keyboard shortcuts for common actions", {"type": "object", "properties": {"query": {"type": "string", "description": "Optional search term to filter shortcuts"}}, "required": []}, keyboard_shortcut_discover, "system"),
        _make_tool("multi_monitor_info", "Detect and display information about connected monitors", {"type": "object", "properties": {}, "required": []}, multi_monitor_info, "system"),
        _make_tool("startup_program_list", "List programs configured to run at system startup", {"type": "object", "properties": {}, "required": []}, startup_program_list, "system"),
        _make_tool("startup_program_add", "Add a program to system startup", {"type": "object", "properties": {"name": {"type": "string", "description": "Display name for the startup entry"}, "path": {"type": "string", "description": "Full path to the executable"}}, "required": ["name", "path"]}, startup_program_add, "system"),
        _make_tool("startup_program_remove", "Remove a program from system startup", {"type": "object", "properties": {"name": {"type": "string", "description": "Name of the startup entry to remove"}}, "required": ["name"]}, startup_program_remove, "system"),
        _make_tool("peripheral_list", "List connected peripherals (keyboard, mouse, monitor, printer, USB, Bluetooth)", {"type": "object", "properties": {}, "required": []}, peripheral_list, "system"),
        _make_tool("accessibility_toggle", "Toggle Windows accessibility features: narrator, magnifier, high_contrast, sticky_keys", {"type": "object", "properties": {"feature": {"type": "string", "description": "Feature name: narrator, magnifier, high_contrast, sticky_keys"}, "enabled": {"type": "boolean", "description": "True to enable, False to disable"}}, "required": ["feature"]}, accessibility_toggle, "system"),
        _make_tool("remote_desktop_start", "Start a remote desktop or VNC session to another computer", {"type": "object", "properties": {"host": {"type": "string", "description": "Hostname or IP address"}, "port": {"type": "integer", "description": "Port: 3389 for RDP, 5900 for VNC"}, "password": {"type": "string", "description": "Optional password"}}, "required": []}, remote_desktop_start, "system"),
        _make_tool("remote_desktop_list_sessions", "List active remote desktop sessions on this machine", {"type": "object", "properties": {}, "required": []}, remote_desktop_list_sessions, "system"),
        _make_tool("macro_record_start", "Start recording a macro (sequence of mouse/keyboard actions)", {"type": "object", "properties": {"name": {"type": "string", "description": "Name for this macro"}}, "required": ["name"]}, macro_record_start, "system"),
        _make_tool("macro_record_step", "Record a step in the macro: mouse_move, mouse_click, keyboard_type, keyboard_hotkey, keyboard_press, delay", {"type": "object", "properties": {"action": {"type": "string", "description": "Action type"}, "params": {"type": "string", "description": "JSON params for the action"}}, "required": ["action", "params"]}, macro_record_step, "system"),
        _make_tool("macro_record_stop", "Stop recording and save the macro", {"type": "object", "properties": {"name": {"type": "string", "description": "Macro name to save under"}}, "required": ["name"]}, macro_record_stop, "system"),
        _make_tool("macro_run", "Execute a previously recorded macro", {"type": "object", "properties": {"name": {"type": "string", "description": "Macro name to run"}, "interval_ms": {"type": "integer", "description": "Delay between steps in ms (default 200)"}}, "required": ["name"]}, macro_run, "system"),
        _make_tool("macro_list", "List all saved macros with step counts and action previews", {"type": "object", "properties": {}, "required": []}, macro_list, "system"),
        _make_tool("macro_delete", "Delete a saved macro", {"type": "object", "properties": {"name": {"type": "string", "description": "Macro name to delete"}}, "required": ["name"]}, macro_delete, "system"),
        _make_tool("orchestrate_sequence", "Execute a sequence of computer control actions: mouse_move, mouse_click, keyboard_type, keyboard_hotkey, keyboard_press, mouse_scroll, delay, screenshot, window_activate, window_minimize", {"type": "object", "properties": {"actions_json": {"type": "string", "description": "JSON string: [{\"action\": \"mouse_move\", \"params\": {\"x\": 100, \"y\": 200}}]"}}, "required": ["actions_json"]}, orchestrate_sequence, "system"),
    ]


def get_context_optimizer_tools():
    from backend.tools.context_optimizer import (
        get_relevant_categories, compress_tool_list,
        compress_history, estimate_tokens, optimize_prompt,
        analyze_tool_conflicts, expand_categories, get_priority_categories,
    )
    return [
        _make_tool("get_relevant_categories", "Determine which tool categories are relevant based on query and intent", {"type": "object", "properties": {"query": {"type": "string", "description": "User query"}, "intent": {"type": "string", "description": "Optional detected intent"}}, "required": ["query"]}, get_relevant_categories, "utility"),
        _make_tool("compress_tool_list", "Generate a compressed tool description grouped by relevant categories", {"type": "object", "properties": {"categories": {"type": "string", "description": "Comma-separated category names"}, "tools": {"type": "string", "description": "Optional JSON-encoded tool list"}}, "required": ["categories"]}, compress_tool_list, "utility"),
        _make_tool("compress_history", "Compress conversation history: summarize old turns, keep recent verbatim", {"type": "object", "properties": {"history_json": {"type": "string", "description": "JSON-encoded conversation history"}, "keep_recent": {"type": "integer", "description": "Number of recent messages to keep verbatim (default 4)"}}, "required": ["history_json"]}, compress_history, "utility"),
        _make_tool("estimate_tokens", "Roughly estimate token count for a text string (~4 chars per token)", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to estimate tokens for"}}, "required": ["text"]}, estimate_tokens, "utility"),
        _make_tool("optimize_prompt", "Build an optimized system prompt with only relevant tools listed for the given query", {"type": "object", "properties": {"query": {"type": "string", "description": "User query"}, "intent": {"type": "string", "description": "Detected intent"}, "categories": {"type": "string", "description": "Optional comma-separated categories to include"}}, "required": ["query"]}, optimize_prompt, "utility"),
        _make_tool("analyze_tool_conflicts", "Analyze which tool categories match a query, detect conflicts, and suggest routing", {"type": "object", "properties": {"query": {"type": "string", "description": "User query"}, "intent": {"type": "string", "description": "Optional detected intent"}}, "required": ["query"]}, analyze_tool_conflicts, "utility"),
        _make_tool("expand_categories", "Expand a list of categories via co-occurrence and dependency rules", {"type": "object", "properties": {"categories": {"type": "array", "items": {"type": "string"}, "description": "List of category names"}}, "required": ["categories"]}, expand_categories, "utility"),
        _make_tool("get_priority_categories", "Get priority categories for a given intent", {"type": "object", "properties": {"intent": {"type": "string", "description": "Detected intent name"}}, "required": ["intent"]}, get_priority_categories, "utility"),
    ]


def get_audio_editor_tools():
    from backend.tools.audio_editor import (
        audio_trim, audio_concatenate, audio_split_by_silence, audio_effects_apply,
        audio_format_convert, audio_noise_reduce, audio_bookmark_add, audio_bookmark_list,
        audio_bookmark_remove, audio_bookmark_jump,
    )
    return [
        _make_tool("audio_trim", "Trim audio file from start_ms to end_ms", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "start_ms": {"type": "number", "description": "Start position in milliseconds"}, "end_ms": {"type": "number", "description": "End position in milliseconds (optional)"}}, "required": ["file_path", "start_ms"]}, audio_trim, "audio"),
        _make_tool("audio_concatenate", "Concatenate multiple audio files into one", {"type": "object", "properties": {"file_paths": {"type": "array", "items": {"type": "string"}, "description": "List of audio file paths to merge"}, "output_path": {"type": "string", "description": "Optional output path"}}, "required": ["file_paths"]}, audio_concatenate, "audio"),
        _make_tool("audio_split_by_silence", "Split audio file into segments at silence points", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "silence_thresh": {"type": "number", "description": "Silence threshold in dB (default -40)"}, "min_silence_ms": {"type": "number", "description": "Minimum silence length in ms (default 500)"}}, "required": ["file_path"]}, audio_split_by_silence, "audio"),
        _make_tool("audio_effects_apply", "Apply audio effects chain: eq, reverb, compression, limiter, delay, fade, reverse, speed, normalize", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "effects": {"type": "string", "description": "JSON array of effect objects: [{\"type\": \"reverb\", \"decay\": 0.5, \"delay_ms\": 100}]"}}, "required": ["file_path", "effects"]}, audio_effects_apply, "audio"),
        _make_tool("audio_format_convert", "Convert audio file to different format (wav, mp3, flac, ogg)", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "output_format": {"type": "string", "description": "Target format: wav, mp3, flac, ogg"}}, "required": ["file_path", "output_format"]}, audio_format_convert, "audio"),
        _make_tool("audio_noise_reduce", "Reduce background noise from audio file", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "strength": {"type": "number", "description": "Noise reduction strength 0.0-1.0 (default 0.5)"}}, "required": ["file_path"]}, audio_noise_reduce, "audio"),
        _make_tool("audio_bookmark_add", "Add a bookmark at a specific position in an audio file", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "position_ms": {"type": "number", "description": "Position in milliseconds"}, "label": {"type": "string", "description": "Optional label for the bookmark"}}, "required": ["file_path", "position_ms"]}, audio_bookmark_add, "audio"),
        _make_tool("audio_bookmark_list", "List all bookmarks for an audio file", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}}, "required": ["file_path"]}, audio_bookmark_list, "audio"),
        _make_tool("audio_bookmark_remove", "Remove a bookmark from an audio file", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "bookmark_id": {"type": "string", "description": "Bookmark ID to remove"}}, "required": ["file_path", "bookmark_id"]}, audio_bookmark_remove, "audio"),
        _make_tool("audio_bookmark_jump", "Get the position of a bookmark to seek to it", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to audio file"}, "bookmark_id": {"type": "string", "description": "Bookmark ID to jump to"}}, "required": ["file_path", "bookmark_id"]}, audio_bookmark_jump, "audio"),
    ]


def get_personality_tools():
    from backend.tools.personality_engine import (
        remember_topic, recall_topics, remember_preference, get_conversation_summary,
        detect_emotion, create_persona, delete_persona, communication_style_report,
        digital_twin_learn, digital_twin_profile, digital_twin_mimic,
        digital_twin_compare, digital_twin_list, digital_twin_delete,
    )
    return [
        _make_tool("remember_topic", "Store a topic discussed with the user for future reference", {"type": "object", "properties": {"topic": {"type": "string", "description": "Topic name"}, "details": {"type": "string", "description": "What was discussed or key details"}, "user_name": {"type": "string", "description": "Optional user name"}}, "required": ["topic", "details"]}, remember_topic, "memory"),
        _make_tool("recall_topics", "Retrieve frequently discussed topics from conversational memory", {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max number of topics to return (default 10)"}}, "required": []}, recall_topics, "memory"),
        _make_tool("remember_preference", "Store a user preference for personalization", {"type": "object", "properties": {"category": {"type": "string", "description": "Preference category (e.g., response_style, verbosity)"}, "value": {"type": "string", "description": "Preference value"}, "username": {"type": "string", "description": "Optional user name"}}, "required": ["category", "value"]}, remember_preference, "memory"),
        _make_tool("get_conversation_summary", "Get summary of conversational memory: topics, preferences, interactions", {"type": "object", "properties": {}, "required": []}, get_conversation_summary, "memory"),
        _make_tool("detect_emotion", "Analyze text to detect emotional state (frustration, excitement, confusion, urgency, sadness, anger, curiosity, satisfaction)", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to analyze for emotional cues"}}, "required": ["text"]}, detect_emotion, "utility"),
        _make_tool("create_persona", "Create a custom AI persona with defined tone and traits", {"type": "object", "properties": {"name": {"type": "string", "description": "Persona name"}, "tone": {"type": "string", "description": "Tone description (e.g., friendly, formal, technical)"}, "formality": {"type": "number", "description": "Formality level 0.0-1.0"}, "verbosity": {"type": "number", "description": "Verbosity level 0.0-1.0"}, "humor": {"type": "number", "description": "Humor level 0.0-1.0"}, "empathy": {"type": "number", "description": "Empathy level 0.0-1.0"}, "traits": {"type": "string", "description": "Comma-separated personality traits"}, "catchphrase": {"type": "string", "description": "Optional catchphrase"}, "rules": {"type": "string", "description": "Newline-separated behavioral rules"}}, "required": ["name"]}, create_persona, "utility"),
        _make_tool("delete_persona", "Delete a custom-created persona (cannot delete built-in personalities)", {"type": "object", "properties": {"name": {"type": "string", "description": "Name of custom persona to delete"}}, "required": ["name"]}, delete_persona, "utility"),
        _make_tool("communication_style_report", "Analyze communication style from a text sample: word count, sentence length, sentiment, suggestions", {"type": "object", "properties": {"conversation_text": {"type": "string", "description": "Text sample to analyze"}}, "required": ["conversation_text"]}, communication_style_report, "utility"),
        _make_tool("digital_twin_learn", "Analyze a user's writing samples to build their digital twin style profile", {"type": "object", "properties": {"username": {"type": "string", "description": "Username to build profile for"}, "text_sample": {"type": "string", "description": "Text sample from the user (at least 3 words)"}}, "required": ["username", "text_sample"]}, digital_twin_learn, "memory"),
        _make_tool("digital_twin_profile", "Retrieve the stored digital twin style profile for a user", {"type": "object", "properties": {"username": {"type": "string", "description": "Username to look up"}}, "required": ["username"]}, digital_twin_profile, "memory"),
        _make_tool("digital_twin_mimic", "Generate instructions for the AI to mimic a user's communication style", {"type": "object", "properties": {"username": {"type": "string", "description": "Username whose style to mimic"}, "custom_instructions": {"type": "string", "description": "Optional extra instructions to add"}}, "required": ["username"]}, digital_twin_mimic, "memory"),
        _make_tool("digital_twin_compare", "Compare communication styles between two users", {"type": "object", "properties": {"username_a": {"type": "string", "description": "First username"}, "username_b": {"type": "string", "description": "Second username"}}, "required": ["username_a", "username_b"]}, digital_twin_compare, "memory"),
        _make_tool("digital_twin_list", "List all stored digital twin profiles", {"type": "object", "properties": {}, "required": []}, digital_twin_list, "memory"),
        _make_tool("digital_twin_delete", "Delete a user's digital twin profile", {"type": "object", "properties": {"username": {"type": "string", "description": "Username to delete"}}, "required": ["username"]}, digital_twin_delete, "memory"),
    ]


def get_api_integration_tools():
    from backend.tools.api_integrations_v2 import (
        stripe_create_payment, stripe_list_transactions, stripe_refund,
        twilio_send_sms, twilio_make_call, twilio_conversation_history,
        slack_send_message, slack_channel_history, slack_list_channels,
        github_create_repo, github_list_repos, github_create_issue, github_create_pr,
        spotify_get_playback_state, spotify_search_and_play,
        fitbit_get_steps,
        plaid_get_accounts, notion_create_page, zapier_trigger, polygon_stock_price,
        huggingface_inference, runway_generate, replicate_run, tavily_search,
        firecrawl_scrape, discord_send_message, telegram_send_message,
        google_drive_list_files, dropbox_list_files, jira_create_issue,
        linear_create_issue, youtube_search, youtube_get_transcript,
    )
    return [
        _make_tool("stripe_create_payment", "Create a Stripe payment intent for processing", {"type": "object", "properties": {"amount": {"type": "number", "description": "Amount in dollars"}, "currency": {"type": "string", "description": "Currency code (default usd)"}, "description": {"type": "string", "description": "Payment description"}}, "required": ["amount"]}, stripe_create_payment, "finance"),
        _make_tool("stripe_list_transactions", "List recent Stripe payment transactions", {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max transactions (default 10)"}}, "required": []}, stripe_list_transactions, "finance"),
        _make_tool("stripe_refund", "Issue a refund for a Stripe payment", {"type": "object", "properties": {"payment_intent_id": {"type": "string", "description": "Payment intent ID to refund"}, "amount": {"type": "number", "description": "Optional partial refund amount"}}, "required": ["payment_intent_id"]}, stripe_refund, "finance"),
        _make_tool("twilio_send_sms", "Send an SMS message via Twilio", {"type": "object", "properties": {"to": {"type": "string", "description": "Recipient phone number"}, "message": {"type": "string", "description": "Message text"}}, "required": ["to", "message"]}, twilio_send_sms, "communication"),
        _make_tool("twilio_make_call", "Make a phone call via Twilio with text-to-speech message", {"type": "object", "properties": {"to": {"type": "string", "description": "Recipient phone number"}, "message": {"type": "string", "description": "Message to speak"}}, "required": ["to", "message"]}, twilio_make_call, "communication"),
        _make_tool("twilio_conversation_history", "Get recent Twilio SMS conversation history", {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max messages (default 20)"}}, "required": []}, twilio_conversation_history, "communication"),
        _make_tool("slack_send_message", "Send a message to a Slack channel", {"type": "object", "properties": {"channel": {"type": "string", "description": "Slack channel name or ID"}, "message": {"type": "string", "description": "Message text"}}, "required": ["channel", "message"]}, slack_send_message, "communication"),
        _make_tool("slack_channel_history", "Get message history from a Slack channel", {"type": "object", "properties": {"channel": {"type": "string", "description": "Channel name or ID"}, "limit": {"type": "integer", "description": "Max messages (default 10)"}}, "required": ["channel"]}, slack_channel_history, "communication"),
        _make_tool("slack_list_channels", "List all Slack channels (public and private)", {"type": "object", "properties": {}, "required": []}, slack_list_channels, "communication"),
        _make_tool("github_create_repo", "Create a new GitHub repository", {"type": "object", "properties": {"name": {"type": "string", "description": "Repository name"}, "description": {"type": "string", "description": "Repository description"}, "private": {"type": "boolean", "description": "Whether repo is private"}}, "required": ["name"]}, github_create_repo, "development"),
        _make_tool("github_list_repos", "List your GitHub repositories", {"type": "object", "properties": {}, "required": []}, github_list_repos, "development"),
        _make_tool("github_create_issue", "Create a GitHub issue on a repository", {"type": "object", "properties": {"repo_name": {"type": "string", "description": "Repository name"}, "title": {"type": "string", "description": "Issue title"}, "body": {"type": "string", "description": "Issue body"}}, "required": ["repo_name", "title"]}, github_create_issue, "development"),
        _make_tool("github_create_pr", "Create a GitHub pull request", {"type": "object", "properties": {"repo_name": {"type": "string", "description": "Repository name"}, "title": {"type": "string", "description": "PR title"}, "head": {"type": "string", "description": "Source branch"}, "base": {"type": "string", "description": "Target branch (default main)"}, "body": {"type": "string", "description": "PR description"}}, "required": ["repo_name", "title", "head"]}, github_create_pr, "development"),
        _make_tool("spotify_get_playback_state", "Get current Spotify playback state: track, artist, device, volume, progress", {"type": "object", "properties": {}, "required": []}, spotify_get_playback_state, "entertainment"),
        _make_tool("spotify_search_and_play", "Search Spotify for a track and start playing it", {"type": "object", "properties": {"query": {"type": "string", "description": "Search query (artist + track name)"}, "device_id": {"type": "string", "description": "Optional device ID to play on"}}, "required": ["query"]}, spotify_search_and_play, "entertainment"),
        _make_tool("fitbit_get_steps", "Get Fitbit step count for a date", {"type": "object", "properties": {"date": {"type": "string", "description": "Date in YYYY-MM-DD format or 'today'"}}, "required": []}, fitbit_get_steps, "health"),
        _make_tool("plaid_get_accounts", "Get linked Plaid bank accounts", {"type": "object", "properties": {}, "required": []}, plaid_get_accounts, "finance"),
        _make_tool("notion_create_page", "Create a page in Notion", {"type": "object", "properties": {"title": {"type": "string", "description": "Page title"}, "content": {"type": "string", "description": "Page content"}, "database_id": {"type": "string", "description": "Optional database ID to add page to"}}, "required": ["title"]}, notion_create_page, "productivity"),
        _make_tool("zapier_trigger", "Trigger a Zapier webhook URL with payload", {"type": "object", "properties": {"webhook_url": {"type": "string", "description": "Zapier webhook URL"}, "payload": {"type": "object", "description": "JSON payload to send"}}, "required": ["webhook_url", "payload"]}, zapier_trigger, "automation"),
        _make_tool("polygon_stock_price", "Get real-time stock price via Polygon.io", {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol (e.g., AAPL)"}}, "required": ["ticker"]}, polygon_stock_price, "finance"),
        _make_tool("huggingface_inference", "Run inference on a Hugging Face model", {"type": "object", "properties": {"model": {"type": "string", "description": "Model ID (e.g., gpt2, bert-base-uncased)"}, "inputs": {"type": "string", "description": "Input text for the model"}}, "required": ["model", "inputs"]}, huggingface_inference, "ai"),
        _make_tool("runway_generate", "Generate a video using RunwayML", {"type": "object", "properties": {"prompt": {"type": "string", "description": "Video generation prompt"}}, "required": ["prompt"]}, runway_generate, "creative"),
        _make_tool("replicate_run", "Run a model on Replicate cloud AI", {"type": "object", "properties": {"model": {"type": "string", "description": "Replicate model string (e.g., stability-ai/stable-diffusion)"}, "input_data": {"type": "object", "description": "Model input parameters as JSON object"}}, "required": ["model", "input_data"]}, replicate_run, "ai"),
        _make_tool("tavily_search", "AI-optimized web search via Tavily", {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "max_results": {"type": "integer", "description": "Max results (default 5)"}}, "required": ["query"]}, tavily_search, "search"),
        _make_tool("firecrawl_scrape", "Scrape a website using Firecrawl API", {"type": "object", "properties": {"url": {"type": "string", "description": "URL to scrape"}}, "required": ["url"]}, firecrawl_scrape, "search"),
        _make_tool("discord_send_message", "Send a message via Discord webhook", {"type": "object", "properties": {"webhook_url": {"type": "string", "description": "Discord webhook URL"}, "message": {"type": "string", "description": "Message content"}}, "required": ["webhook_url", "message"]}, discord_send_message, "communication"),
        _make_tool("telegram_send_message", "Send a message via Telegram bot", {"type": "object", "properties": {"chat_id": {"type": "string", "description": "Telegram chat ID"}, "message": {"type": "string", "description": "Message text"}}, "required": ["chat_id", "message"]}, telegram_send_message, "communication"),
        _make_tool("google_drive_list_files", "List files in Google Drive", {"type": "object", "properties": {"query": {"type": "string", "description": "Optional search query"}}, "required": []}, google_drive_list_files, "storage"),
        _make_tool("dropbox_list_files", "List files in Dropbox", {"type": "object", "properties": {"path": {"type": "string", "description": "Optional folder path"}}, "required": []}, dropbox_list_files, "storage"),
        _make_tool("jira_create_issue", "Create a Jira issue", {"type": "object", "properties": {"project": {"type": "string", "description": "Project key"}, "summary": {"type": "string", "description": "Issue summary"}, "description": {"type": "string", "description": "Issue description"}, "issue_type": {"type": "string", "description": "Issue type (Task, Bug, Story)"}}, "required": ["project", "summary"]}, jira_create_issue, "productivity"),
        _make_tool("linear_create_issue", "Create a Linear issue", {"type": "object", "properties": {"title": {"type": "string", "description": "Issue title"}, "description": {"type": "string", "description": "Issue description"}, "team_id": {"type": "string", "description": "Optional team ID"}}, "required": ["title"]}, linear_create_issue, "productivity"),
        _make_tool("youtube_search", "Search YouTube videos", {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "max_results": {"type": "integer", "description": "Max results (default 5)"}}, "required": ["query"]}, youtube_search, "entertainment"),
        _make_tool("youtube_get_transcript", "Get transcript of a YouTube video", {"type": "object", "properties": {"video_id": {"type": "string", "description": "YouTube video ID"}}, "required": ["video_id"]}, youtube_get_transcript, "entertainment"),
    ]


def get_security_tools():
    from backend.tools.security import (
        auth_create_token, auth_verify_token, permission_check, permission_list_roles,
        sanitize_input, audit_log, audit_get_log, session_create, session_validate, session_list,
    )
    return [
        _make_tool("auth_create_token", "Create a JWT authentication token for a user", {"type": "object", "properties": {"username": {"type": "string", "description": "Username"}, "role": {"type": "string", "description": "User role: admin, user, guest, developer"}, "expires_minutes": {"type": "integer", "description": "Token expiry in minutes"}}, "required": ["username"]}, auth_create_token, "system"),
        _make_tool("auth_verify_token", "Verify and decode a JWT token", {"type": "object", "properties": {"token": {"type": "string", "description": "JWT token to verify"}}, "required": ["token"]}, auth_verify_token, "system"),
        _make_tool("permission_check", "Check if a role has a specific permission", {"type": "object", "properties": {"role": {"type": "string", "description": "User role"}, "required_permission": {"type": "string", "description": "Permission to check (e.g., read, write, execute_code)"}}, "required": ["role", "required_permission"]}, permission_check, "system"),
        _make_tool("permission_list_roles", "List all available roles and their permissions", {"type": "object", "properties": {}, "required": []}, permission_list_roles, "system"),
        _make_tool("sanitize_input", "Sanitize user input for safety (blocks destructive commands, SQL injection, XSS)", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to sanitize"}}, "required": ["text"]}, sanitize_input, "system"),
        _make_tool("audit_log", "Log an audit entry for security-sensitive operations", {"type": "object", "properties": {"action": {"type": "string", "description": "Action performed"}, "username": {"type": "string", "description": "User who performed action"}, "details": {"type": "string", "description": "Details about the action"}, "severity": {"type": "string", "description": "Severity: info, warning, critical"}}, "required": ["action"]}, audit_log, "system"),
        _make_tool("audit_get_log", "Retrieve recent audit log entries", {"type": "object", "properties": {"limit": {"type": "integer", "description": "Max entries (default 50)"}, "severity": {"type": "string", "description": "Filter by severity level"}}, "required": []}, audit_get_log, "system"),
        _make_tool("session_create", "Create a new user session", {"type": "object", "properties": {"username": {"type": "string", "description": "Username"}, "ttl_seconds": {"type": "integer", "description": "Session TTL in seconds (default 3600)"}}, "required": ["username"]}, session_create, "system"),
        _make_tool("session_validate", "Validate a session ID", {"type": "object", "properties": {"session_id": {"type": "string", "description": "Session ID to validate"}}, "required": ["session_id"]}, session_validate, "system"),
        _make_tool("session_list", "List all active sessions", {"type": "object", "properties": {}, "required": []}, session_list, "system"),
    ]


def get_monitoring_tools():
    from backend.tools.monitoring import (
        metrics_get, metrics_track_llm_call, metrics_cost_summary,
        trace_start, trace_end, trace_summary, log_event, log_get, metrics_prometheus,
    )
    return [
        _make_tool("metrics_get", "Get JARVIS usage metrics: requests, tokens, LLM calls, errors, uptime", {"type": "object", "properties": {}, "required": []}, metrics_get, "system"),
        _make_tool("metrics_track_llm_call", "Track an LLM API call with token counts and cost estimation", {"type": "object", "properties": {"model": {"type": "string", "description": "Model name"}, "input_tokens": {"type": "integer", "description": "Input token count"}, "output_tokens": {"type": "integer", "description": "Output token count"}}, "required": ["model", "input_tokens", "output_tokens"]}, metrics_track_llm_call, "system"),
        _make_tool("metrics_cost_summary", "Get estimated total LLM cost summary", {"type": "object", "properties": {}, "required": []}, metrics_cost_summary, "system"),
        _make_tool("trace_start", "Start a performance trace for an operation", {"type": "object", "properties": {"operation": {"type": "string", "description": "Operation name"}, "metadata": {"type": "object", "description": "Optional metadata JSON"}}, "required": ["operation"]}, trace_start, "system"),
        _make_tool("trace_end", "End a performance trace and record duration", {"type": "object", "properties": {"span_id": {"type": "string", "description": "Span ID from trace_start"}}, "required": ["span_id"]}, trace_end, "system"),
        _make_tool("trace_summary", "Get performance trace summary with average durations by operation", {"type": "object", "properties": {}, "required": []}, trace_summary, "system"),
        _make_tool("log_event", "Log a structured event to the system log", {"type": "object", "properties": {"level": {"type": "string", "description": "Log level: debug, info, warning, error"}, "message": {"type": "string", "description": "Log message"}, "component": {"type": "string", "description": "Component name"}, "extra": {"type": "object", "description": "Optional extra data"}}, "required": ["level", "message"]}, log_event, "system"),
        _make_tool("log_get", "Retrieve recent structured log entries", {"type": "object", "properties": {"level": {"type": "string", "description": "Filter by level"}, "component": {"type": "string", "description": "Filter by component"}, "limit": {"type": "integer", "description": "Max entries (default 50)"}}, "required": []}, log_get, "system"),
        _make_tool("metrics_prometheus", "Get system metrics in Prometheus exposition format", {"type": "object", "properties": {}, "required": []}, metrics_prometheus, "system"),
    ]


def get_qol_tools():
    from backend.tools.qol_features import (
        suggest_followups, personalization_get, personalization_set,
        cache_get, cache_set, cache_clear, cache_stats,
        tool_analytics_track, tool_analytics_report,
        expand_abbreviations, tag_conversation, search_by_tag,
        daily_briefing, focus_mode_set, focus_mode_status,
        emergency_stop, emergency_resume, emergency_status,
        migration_create, migration_list, memory_backup, memory_restore,
        data_export, temp_cleanup, temp_register, detect_language, audio_mix_tracks,
    )
    return [
        _make_tool("suggest_followups", "Suggest follow-up questions based on conversation context", {"type": "object", "properties": {"context": {"type": "string", "description": "Context: general, code, research, planning"}}, "required": []}, suggest_followups, "utility"),
        _make_tool("personalization_get", "Get stored user preferences and personalization settings", {"type": "object", "properties": {"username": {"type": "string", "description": "Username"}}, "required": ["username"]}, personalization_get, "utility"),
        _make_tool("personalization_set", "Set user preferences for personalized responses", {"type": "object", "properties": {"username": {"type": "string", "description": "Username"}, "preferences": {"type": "string", "description": "JSON object with preference key/value pairs"}}, "required": ["username", "preferences"]}, personalization_set, "utility"),
        _make_tool("cache_get", "Get a cached response for a key", {"type": "object", "properties": {"key": {"type": "string", "description": "Cache key"}}, "required": ["key"]}, cache_get, "utility"),
        _make_tool("cache_set", "Cache a response for faster future retrieval", {"type": "object", "properties": {"key": {"type": "string", "description": "Cache key"}, "response": {"type": "string", "description": "Response to cache"}}, "required": ["key", "response"]}, cache_set, "utility"),
        _make_tool("cache_clear", "Clear all cached responses", {"type": "object", "properties": {}, "required": []}, cache_clear, "utility"),
        _make_tool("cache_stats", "Get response cache statistics", {"type": "object", "properties": {}, "required": []}, cache_stats, "utility"),
        _make_tool("tool_analytics_track", "Track a tool usage for analytics", {"type": "object", "properties": {"tool_name": {"type": "string", "description": "Tool name to track"}}, "required": ["tool_name"]}, tool_analytics_track, "utility"),
        _make_tool("tool_analytics_report", "Get tool usage analytics report sorted by call count", {"type": "object", "properties": {}, "required": []}, tool_analytics_report, "utility"),
        _make_tool("expand_abbreviations", "Expand common text abbreviations (idk, imo, tbh, btw, etc.)", {"type": "object", "properties": {"text": {"type": "string", "description": "Text with abbreviations"}}, "required": ["text"]}, expand_abbreviations, "utility"),
        _make_tool("tag_conversation", "Tag a conversation session for later retrieval", {"type": "object", "properties": {"session_id": {"type": "string", "description": "Session ID"}, "tags": {"type": "string", "description": "Comma-separated tags"}}, "required": ["session_id", "tags"]}, tag_conversation, "utility"),
        _make_tool("search_by_tag", "Find conversations by tag", {"type": "object", "properties": {"tag": {"type": "string", "description": "Tag to search for"}}, "required": ["tag"]}, search_by_tag, "utility"),
        _make_tool("daily_briefing", "Get a daily briefing summary", {"type": "object", "properties": {"time_of_day": {"type": "string", "description": "morning or evening"}, "username": {"type": "string", "description": "Your name"}}, "required": []}, daily_briefing, "utility"),
        _make_tool("focus_mode_set", "Enable or disable focus mode to block non-essential tools", {"type": "object", "properties": {"enabled": {"type": "boolean", "description": "True to enable focus mode"}, "blocked_tools": {"type": "string", "description": "Comma-separated tool names to block"}}, "required": ["enabled"]}, focus_mode_set, "utility"),
        _make_tool("focus_mode_status", "Check if focus mode is active and which tools are blocked", {"type": "object", "properties": {}, "required": []}, focus_mode_status, "utility"),
        _make_tool("emergency_stop", "Emergency stop — halt all non-critical operations", {"type": "object", "properties": {}, "required": []}, emergency_stop, "system"),
        _make_tool("emergency_resume", "Resume normal operations after emergency stop", {"type": "object", "properties": {}, "required": []}, emergency_resume, "system"),
        _make_tool("emergency_status", "Check if emergency stop is active", {"type": "object", "properties": {}, "required": []}, emergency_status, "system"),
        _make_tool("migration_create", "Create a new database migration script", {"type": "object", "properties": {"name": {"type": "string", "description": "Migration name"}, "sql_up": {"type": "string", "description": "SQL to apply migration"}, "sql_down": {"type": "string", "description": "SQL to revert migration"}}, "required": ["name", "sql_up", "sql_down"]}, migration_create, "database"),
        _make_tool("migration_list", "List all database migrations", {"type": "object", "properties": {}, "required": []}, migration_list, "database"),
        _make_tool("memory_backup", "Backup memory data to a JSON file", {"type": "object", "properties": {"backup_path": {"type": "string", "description": "Optional backup file path"}}, "required": []}, memory_backup, "memory"),
        _make_tool("memory_restore", "Restore memory data from a backup file", {"type": "object", "properties": {"backup_path": {"type": "string", "description": "Path to backup file"}}, "required": ["backup_path"]}, memory_restore, "memory"),
        _make_tool("data_export", "Export data to a file (json, csv, txt formats)", {"type": "object", "properties": {"data": {"type": "string", "description": "Data to export"}, "format": {"type": "string", "description": "Export format: json, csv, txt"}}, "required": ["data"]}, data_export, "utility"),
        _make_tool("temp_cleanup", "Clean up expired temporary files", {"type": "object", "properties": {"max_age_hours": {"type": "integer", "description": "Max file age in hours (default 24)"}}, "required": []}, temp_cleanup, "system"),
        _make_tool("temp_register", "Register a temporary file for automatic cleanup", {"type": "object", "properties": {"path": {"type": "string", "description": "File path to register"}}, "required": ["path"]}, temp_register, "system"),
        _make_tool("detect_language", "Detect the language of input text using greeting keywords", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to analyze"}}, "required": ["text"]}, detect_language, "utility"),
        _make_tool("audio_mix_tracks", "Mix multiple audio tracks into one file with volume control", {"type": "object", "properties": {"file_paths": {"type": "array", "items": {"type": "string"}, "description": "List of audio file paths"}, "output_path": {"type": "string", "description": "Optional output path"}, "volumes": {"type": "array", "items": {"type": "number"}, "description": "Optional volume levels per track (0.0-1.0)"}}, "required": ["file_paths"]}, audio_mix_tracks, "audio"),
    ]


def get_scifi_tools():
    from backend.tools.scifi_features import (
        predictive_analyze, predictive_suggest, desktop_pet_activate, desktop_pet_interact,
        desktop_pet_deactivate, emotion_companion_log, emotion_companion_report,
        swarm_create_agent, swarm_list_agents, swarm_execute_task,
        collaboration_send, collaboration_receive, collaboration_broadcast,
        meeting_assistant_join, meeting_assistant_note, meeting_assistant_action,
        meeting_assistant_summarize, cybersecurity_alert, cybersecurity_status,
        translate_text, holographic_ui_render,
        drone_connect, drone_arm, drone_takeoff, drone_move, drone_land, drone_status,
        bci_status, bci_simulate, bci_connect, bci_start_session, bci_read_data,
        os_layer_activate, os_layer_deactivate, os_layer_register_shortcut,
        os_layer_status, os_layer_execute,
    )
    return [
        _make_tool("predictive_analyze", "Analyze user action patterns to predict next steps", {"type": "object", "properties": {"user_actions": {"type": "string", "description": "Comma-separated list of recent user actions"}}, "required": ["user_actions"]}, predictive_analyze, "ai"),
        _make_tool("predictive_suggest", "Suggest actions based on current conversation context", {"type": "object", "properties": {"current_context": {"type": "string", "description": "Current context description"}}, "required": ["current_context"]}, predictive_suggest, "ai"),
        _make_tool("desktop_pet_activate", "Activate an AI desktop pet companion", {"type": "object", "properties": {"style": {"type": "string", "description": "Pet visual style (default)"}}, "required": []}, desktop_pet_activate, "fun"),
        _make_tool("desktop_pet_interact", "Interact with the desktop pet (pet, feed, play, sleep, wave)", {"type": "object", "properties": {"action": {"type": "string", "description": "Interaction: pet, feed, play, sleep, wave"}}, "required": []}, desktop_pet_interact, "fun"),
        _make_tool("desktop_pet_deactivate", "Deactivate the desktop pet companion", {"type": "object", "properties": {}, "required": []}, desktop_pet_deactivate, "fun"),
        _make_tool("emotion_companion_log", "Log user's emotional state for adaptive responses", {"type": "object", "properties": {"mood": {"type": "string", "description": "Mood: happy, sad, frustrated, excited, stressed, angry, calm"}, "intensity": {"type": "number", "description": "Intensity 0.0-1.0"}, "context": {"type": "string", "description": "Optional context"}}, "required": ["mood"]}, emotion_companion_log, "ai"),
        _make_tool("emotion_companion_report", "Get report of emotional trends over time", {"type": "object", "properties": {}, "required": []}, emotion_companion_report, "ai"),
        _make_tool("swarm_create_agent", "Create a new AI swarm agent for parallel task processing", {"type": "object", "properties": {"name": {"type": "string", "description": "Agent name"}, "task": {"type": "string", "description": "Task description"}, "model": {"type": "string", "description": "Model to use (auto for default)"}}, "required": ["name", "task"]}, swarm_create_agent, "ai"),
        _make_tool("swarm_list_agents", "List all active swarm agents and their status", {"type": "object", "properties": {}, "required": []}, swarm_list_agents, "ai"),
        _make_tool("swarm_execute_task", "Execute a task on a specific swarm agent", {"type": "object", "properties": {"agent_id": {"type": "string", "description": "Agent ID from swarm_create_agent"}, "input_data": {"type": "string", "description": "Input data for the task"}}, "required": ["agent_id", "input_data"]}, swarm_execute_task, "ai"),
        _make_tool("collaboration_send", "Send a message from one swarm agent to another", {"type": "object", "properties": {"agent_id": {"type": "string", "description": "Sending agent ID"}, "message": {"type": "string", "description": "Message content"}, "message_type": {"type": "string", "description": "Message type: task, result, broadcast"}}, "required": ["agent_id", "message"]}, collaboration_send, "ai"),
        _make_tool("collaboration_receive", "Receive pending messages for a swarm agent", {"type": "object", "properties": {"agent_id": {"type": "string", "description": "Receiving agent ID"}}, "required": ["agent_id"]}, collaboration_receive, "ai"),
        _make_tool("collaboration_broadcast", "Broadcast a message to all swarm agents", {"type": "object", "properties": {"message": {"type": "string", "description": "Message to broadcast"}, "exclude_agent": {"type": "string", "description": "Optional agent ID to exclude"}}, "required": ["message"]}, collaboration_broadcast, "ai"),
        _make_tool("meeting_assistant_join", "Join a meeting to take notes and capture action items", {"type": "object", "properties": {"meeting_title": {"type": "string", "description": "Meeting title"}, "platform": {"type": "string", "description": "Platform: generic, zoom, teams, meet"}}, "required": ["meeting_title"]}, meeting_assistant_join, "productivity"),
        _make_tool("meeting_assistant_note", "Take a note during an active meeting", {"type": "object", "properties": {"meeting_id": {"type": "string", "description": "Meeting ID from meeting_assistant_join"}, "note": {"type": "string", "description": "Note content"}}, "required": ["meeting_id", "note"]}, meeting_assistant_note, "productivity"),
        _make_tool("meeting_assistant_action", "Capture an action item during a meeting", {"type": "object", "properties": {"meeting_id": {"type": "string", "description": "Meeting ID"}, "action": {"type": "string", "description": "Action item description"}, "assignee": {"type": "string", "description": "Person assigned"}}, "required": ["meeting_id", "action"]}, meeting_assistant_action, "productivity"),
        _make_tool("meeting_assistant_summarize", "Generate meeting summary with action items and key points", {"type": "object", "properties": {"meeting_id": {"type": "string", "description": "Meeting ID to summarize"}}, "required": ["meeting_id"]}, meeting_assistant_summarize, "productivity"),
        _make_tool("cybersecurity_alert", "Log a cybersecurity alert event", {"type": "object", "properties": {"event_type": {"type": "string", "description": "Event type: intrusion, malware, phishing, data_exfil, unauthorized_access"}, "source": {"type": "string", "description": "Source of the event"}, "details": {"type": "string", "description": "Additional details"}}, "required": ["event_type"]}, cybersecurity_alert, "system"),
        _make_tool("cybersecurity_status", "Get cybersecurity status with recent alerts and recommendations", {"type": "object", "properties": {}, "required": []}, cybersecurity_status, "system"),
        _make_tool("translate_text", "Translate text between languages using LibreTranslate", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to translate"}, "target_language": {"type": "string", "description": "Target language code (default: en)"}, "source_language": {"type": "string", "description": "Source language code (default: auto)"}}, "required": ["text"]}, translate_text, "utility"),
        _make_tool("holographic_ui_render", "Render a holographic UI component concept (glass_panel, hud_display, holo_chart, floating_button, particle_bg, ring_menu)", {"type": "object", "properties": {"component_type": {"type": "string", "description": "Component type"}, "data": {"type": "string", "description": "JSON data for the component"}}, "required": ["component_type"]}, holographic_ui_render, "creative"),
        _make_tool("drone_connect", "Connect to a drone via MAVLink protocol", {"type": "object", "properties": {"protocol": {"type": "string", "description": "Protocol (default: mavlink)"}, "address": {"type": "string", "description": "Connection address (default: 127.0.0.1:14550)"}}, "required": []}, drone_connect, "system"),
        _make_tool("drone_arm", "Arm the connected drone for flight", {"type": "object", "properties": {}, "required": []}, drone_arm, "system"),
        _make_tool("drone_takeoff", "Command drone to take off to specified altitude", {"type": "object", "properties": {"altitude_m": {"type": "number", "description": "Altitude in meters (default 10)"}}, "required": []}, drone_takeoff, "system"),
        _make_tool("drone_move", "Move drone by relative coordinates", {"type": "object", "properties": {"x": {"type": "number", "description": "X movement in meters"}, "y": {"type": "number", "description": "Y movement in meters"}, "z": {"type": "number", "description": "Z movement in meters"}}, "required": []}, drone_move, "system"),
        _make_tool("drone_land", "Land the drone at current position", {"type": "object", "properties": {}, "required": []}, drone_land, "system"),
        _make_tool("drone_status", "Get drone status: connection, battery, position", {"type": "object", "properties": {}, "required": []}, drone_status, "system"),
        _make_tool("bci_status", "Check Brain-Computer Interface availability and supported protocols", {"type": "object", "properties": {}, "required": []}, bci_status, "system"),
        _make_tool("bci_simulate", "Simulate a BCI command for testing", {"type": "object", "properties": {"command": {"type": "string", "description": "Command: focus, relax, blink, left, right"}}, "required": []}, bci_simulate, "system"),
        _make_tool("bci_connect", "Connect to a BCI hardware device (muse, openbci, neurosky)", {"type": "object", "properties": {"device_type": {"type": "string", "description": "Device: muse, openbci, neurosky"}, "port": {"type": "string", "description": "Optional port/address"}}, "required": ["device_type"]}, bci_connect, "system"),
        _make_tool("bci_start_session", "Start a BCI EEG recording session", {"type": "object", "properties": {"duration_seconds": {"type": "integer", "description": "Duration in seconds (default 60)"}}, "required": []}, bci_start_session, "system"),
        _make_tool("bci_read_data", "Read EEG data from active BCI session", {"type": "object", "properties": {}, "required": []}, bci_read_data, "system"),
        _make_tool("os_layer_activate", "Activate the AI Operating System Layer for system-wide command listening", {"type": "object", "properties": {}, "required": []}, os_layer_activate, "system"),
        _make_tool("os_layer_deactivate", "Deactivate the AI OS Layer", {"type": "object", "properties": {}, "required": []}, os_layer_deactivate, "system"),
        _make_tool("os_layer_register_shortcut", "Register a global keyboard shortcut with an action", {"type": "object", "properties": {"keys": {"type": "string", "description": "Key combination (e.g., Ctrl+Shift+J)"}, "action": {"type": "string", "description": "Action to perform"}}, "required": ["keys", "action"]}, os_layer_register_shortcut, "system"),
        _make_tool("os_layer_status", "Get AI OS Layer status: active, shortcuts, watchers", {"type": "object", "properties": {}, "required": []}, os_layer_status, "system"),
        _make_tool("os_layer_execute", "Execute a system-level command through the AI OS Layer", {"type": "object", "properties": {"command": {"type": "string", "description": "Command like 'open browser', 'screenshot', 'lock', 'volume up'"}}, "required": ["command"]}, os_layer_execute, "system"),
    ]


# ---------------------------------------------------------------------------
# Master list — call this from agent.py
# ---------------------------------------------------------------------------


def get_info_scraper_tools():
    from backend.tools.info_scraper import (
        scrape_page, scrape_search, scrape_news, scrape_stock, scrape_weather,
        scrape_wikipedia, scrape_recipe, scrape_product, scrape_social_mentions,
        scrape_jobs, scrape_movie_info, scrape_lyrics, scrape_define,
        scrape_dictionary, scrape_translate, scrape_facts,
        search_information, ask_question,
    )
    return [
        _make_tool("scrape_page", "Extract content from any web page with optional JS rendering and structured extraction (tables, links, prices, images)", {"type": "object", "properties": {"url": {"type": "string", "description": "URL to scrape"}, "render_js": {"type": "boolean", "description": "Use Playwright JS rendering (default false)"}, "extract_links": {"type": "boolean", "description": "Extract links (default true)"}, "extract_tables": {"type": "boolean", "description": "Extract HTML tables"}, "extract_prices": {"type": "boolean", "description": "Extract prices (USD/EUR/GBP)"}, "use_readability": {"type": "boolean", "description": "Use readability algorithm for main content (default true)"}}, "required": ["url"]}, scrape_page, "web"),
        _make_tool("scrape_search", "Search the web using DuckDuckGo and return organic results with snippets", {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "site": {"type": "string", "description": "Restrict to a specific site (optional)"}, "max_results": {"type": "integer", "description": "Max results (default 10)"}}, "required": ["query"]}, scrape_search, "web"),
        _make_tool("scrape_news", "Fetch top news or search Google News for a topic", {"type": "object", "properties": {"query": {"type": "string", "description": "Optional topic to search for (empty = top stories)"}, "max_results": {"type": "integer", "description": "Max results (default 10)"}}, "required": []}, scrape_news, "web"),
        _make_tool("scrape_stock", "Look up real-time stock price, change, and company info via Google Finance", {"type": "object", "properties": {"ticker": {"type": "string", "description": "Stock ticker symbol (e.g., AAPL, GOOGL)"}, "exchange": {"type": "string", "description": "Optional exchange (e.g., NASDAQ, NYSE)"}}, "required": ["ticker"]}, scrape_stock, "web"),
        _make_tool("scrape_weather", "Get current weather conditions, temperature, humidity, wind for any location", {"type": "object", "properties": {"location": {"type": "string", "description": "City name or location"}}, "required": ["location"]}, scrape_weather, "web"),
        _make_tool("scrape_wikipedia", "Fetch Wikipedia summary and metadata for any topic", {"type": "object", "properties": {"query": {"type": "string", "description": "Topic to look up"}, "extract_sections": {"type": "boolean", "description": "Also extract table of contents sections"}}, "required": ["query"]}, scrape_wikipedia, "web"),
        _make_tool("scrape_recipe", "Search for recipes by ingredients or dish name", {"type": "object", "properties": {"query": {"type": "string", "description": "Recipe search query"}, "max_results": {"type": "integer", "description": "Max results (default 5)"}}, "required": ["query"]}, scrape_recipe, "web"),
        _make_tool("scrape_product", "Scrape product info by URL or search by product name", {"type": "object", "properties": {"url_or_query": {"type": "string", "description": "Product URL or search term"}, "max_results": {"type": "integer", "description": "Max results for search (default 5)"}}, "required": ["url_or_query"]}, scrape_product, "web"),
        _make_tool("scrape_social_mentions", "Search social platforms (reddit, hackernews) for mentions of a topic", {"type": "object", "properties": {"query": {"type": "string", "description": "Topic to search for"}, "platform": {"type": "string", "description": "Platform: reddit, hackernews (default reddit)"}, "max_results": {"type": "integer", "description": "Max results (default 10)"}}, "required": ["query"]}, scrape_social_mentions, "web"),
        _make_tool("scrape_jobs", "Search for job listings by keyword and location", {"type": "object", "properties": {"query": {"type": "string", "description": "Job title or keyword"}, "location": {"type": "string", "description": "City or location"}, "max_results": {"type": "integer", "description": "Max results (default 10)"}}, "required": ["query"]}, scrape_jobs, "web"),
        _make_tool("scrape_movie_info", "Get movie details: rating, description, director, cast, genre", {"type": "object", "properties": {"title": {"type": "string", "description": "Movie title"}}, "required": ["title"]}, scrape_movie_info, "web"),
        _make_tool("scrape_lyrics", "Find song lyrics by artist and song name", {"type": "object", "properties": {"artist": {"type": "string", "description": "Artist name"}, "song": {"type": "string", "description": "Song name"}}, "required": ["artist", "song"]}, scrape_lyrics, "web"),
        _make_tool("scrape_define", "Get word definition, phonetic transcription, and usage examples", {"type": "object", "properties": {"word": {"type": "string", "description": "Word to define"}}, "required": ["word"]}, scrape_define, "web"),
        _make_tool("scrape_dictionary", "Look up a word in the dictionary with definitions and examples", {"type": "object", "properties": {"search_term": {"type": "string", "description": "Word to look up"}, "lang": {"type": "string", "description": "Language code (default: en)"}}, "required": ["search_term"]}, scrape_dictionary, "web"),
        _make_tool("scrape_translate", "Translate text between languages using Google Translate", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to translate"}, "target_lang": {"type": "string", "description": "Target language code (e.g., es, fr, de, ja)"}}, "required": ["text", "target_lang"]}, scrape_translate, "web"),
        _make_tool("scrape_facts", "Fetch interesting facts or trivia on a topic", {"type": "object", "properties": {"query": {"type": "string", "description": "Optional topic for facts"}, "count": {"type": "integer", "description": "Number of facts (default 5)"}}, "required": []}, scrape_facts, "web"),
        _make_tool("search_information", "Search multiple sources (web, Wikipedia, news) and return best consolidated answer for any query", {"type": "object", "properties": {"query": {"type": "string", "description": "Search query"}, "max_sources": {"type": "integer", "description": "Max sources to query (default 3)"}}, "required": ["query"]}, search_information, "web"),
        _make_tool("ask_question", "Ask a direct question and get the best answer from web sources", {"type": "object", "properties": {"question": {"type": "string", "description": "Direct question to answer"}}, "required": ["question"]}, ask_question, "web"),
    ]


def get_multi_agent_tools():
    from backend.tools.multi_agent import (
        spawn_agent, list_agents, get_agent_result, cancel_agent, multi_agent_collaborate,
    )
    return [
        _make_tool("spawn_agent", "Spawn a sub-agent with a specific role (researcher, coder, reviewer, writer, analyst) to work on a task independently", {"type": "object", "properties": {"role": {"type": "string", "description": "Agent role: researcher, coder, reviewer, writer, analyst"}, "task": {"type": "string", "description": "The task description"}, "context": {"type": "string", "description": "Optional context from main conversation"}, "parent_session": {"type": "string", "description": "Session ID"}}, "required": ["role", "task"]}, spawn_agent, "ai"),
        _make_tool("list_agents", "List all spawned sub-agents with their status, optionally filtered by status or session", {"type": "object", "properties": {"status": {"type": "string", "description": "Filter by status: running, completed, failed, cancelled"}, "parent_session": {"type": "string", "description": "Filter by parent session"}}, "required": []}, list_agents, "ai"),
        _make_tool("get_agent_result", "Get the result of a completed sub-agent by agent_id", {"type": "object", "properties": {"agent_id": {"type": "string", "description": "The agent ID returned by spawn_agent"}}, "required": ["agent_id"]}, get_agent_result, "ai"),
        _make_tool("cancel_agent", "Cancel a running sub-agent", {"type": "object", "properties": {"agent_id": {"type": "string", "description": "The agent ID to cancel"}}, "required": ["agent_id"]}, cancel_agent, "ai"),
        _make_tool("multi_agent_collaborate", "Spawn multiple agents with different roles to collaborate on a complex task simultaneously", {"type": "object", "properties": {"primary_role": {"type": "string", "description": "Primary agent role"}, "supporting_roles": {"type": "string", "description": "Comma-separated supporting roles"}, "task": {"type": "string", "description": "The overall task description"}, "context": {"type": "string", "description": "Optional context"}, "parent_session": {"type": "string", "description": "Session ID"}}, "required": ["primary_role", "supporting_roles", "task"]}, multi_agent_collaborate, "ai"),
    ]


def get_pdf_tools():
    from backend.tools.pdf_tools import pdf_enhance_file, pdf_enhance_images
    return [
        _make_tool("pdf_enhance_file", "Enhance a scanned PDF — corrects skew, crops borders, improves contrast, produces clean output", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to the scanned PDF file"}, "output_path": {"type": "string", "description": "Optional output path (default: input_enhanced.pdf)"}, "dpi": {"type": "integer", "description": "Scan quality DPI 100-400 (default 200)"}}, "required": ["file_path"]}, pdf_enhance_file, "utility"),
        _make_tool("pdf_enhance_images", "Enhance scanned images and combine into a single clean PDF", {"type": "object", "properties": {"image_paths": {"type": "array", "items": {"type": "string"}, "description": "List of image file paths (JPG, PNG, BMP, TIFF)"}, "output_path": {"type": "string", "description": "Optional output PDF path (default: enhanced_output.pdf)"}, "dpi": {"type": "integer", "description": "Quality DPI 100-400 (default 200)"}}, "required": ["image_paths"]}, pdf_enhance_images, "utility"),
    ]


def get_health_tools():
    from backend.tools.health_tools import server_health
    return [
        _make_tool("server_health", "Check J.A.R.V.I.S. server health status — uptime, active sessions, token usage, memory status", {"type": "object", "properties": {}, "required": []}, server_health, "system"),
    ]


def get_file_tools():
    from backend.tools.file_tools import file_search, file_hash, file_diff, file_compress, file_decompress, file_type_detect
    return [
        _make_tool("file_search", "Search for files matching a glob pattern", {"type": "object", "properties": {"root_dir": {"type": "string", "description": "Root directory to search"}, "pattern": {"type": "string", "description": "Glob pattern (e.g. *.py, **/*.txt)"}, "max_results": {"type": "integer", "description": "Max results (default 50)"}}, "required": ["root_dir"]}, file_search, "utility"),
        _make_tool("file_hash", "Compute hash of a file (MD5, SHA1, SHA256, SHA512)", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to file"}, "algorithm": {"type": "string", "description": "Hash algorithm: md5, sha1, sha256, sha512 (default sha256)"}}, "required": ["file_path"]}, file_hash, "utility"),
        _make_tool("file_diff", "Show diff between two files", {"type": "object", "properties": {"file_a": {"type": "string", "description": "First file path"}, "file_b": {"type": "string", "description": "Second file path"}, "context_lines": {"type": "integer", "description": "Context lines (default 3)"}}, "required": ["file_a", "file_b"]}, file_diff, "utility"),
        _make_tool("file_compress", "Compress files/directories into zip or tar archive", {"type": "object", "properties": {"paths": {"type": "array", "items": {"type": "string"}, "description": "List of file/directory paths to compress"}, "output_path": {"type": "string", "description": "Output archive path"}, "format": {"type": "string", "description": "Archive format: zip or tar (default zip)"}}, "required": ["paths"]}, file_compress, "utility"),
        _make_tool("file_decompress", "Extract a zip or tar archive", {"type": "object", "properties": {"archive_path": {"type": "string", "description": "Path to archive file"}, "output_dir": {"type": "string", "description": "Output directory (default: archive basename)"}}, "required": ["archive_path"]}, file_decompress, "utility"),
        _make_tool("file_type_detect", "Detect file type, MIME, and size", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to file"}}, "required": ["file_path"]}, file_type_detect, "utility"),
    ]


def get_text_tools():
    from backend.tools.text_tools import text_analyze, regex_match, regex_replace, json_validate, json_transform, csv_parse, csv_to_json, markdown_to_html, date_format, timezone_convert, unit_convert
    return [
        _make_tool("text_analyze", "Analyze text: word count, character count, sentences, reading time", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to analyze"}}, "required": ["text"]}, text_analyze, "utility"),
        _make_tool("regex_match", "Test regex pattern against text and show matches", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to search"}, "pattern": {"type": "string", "description": "Regex pattern"}, "flags": {"type": "string", "description": "Regex flags: i=ignore case, m=multiline, s=dotall"}}, "required": ["text", "pattern"]}, regex_match, "utility"),
        _make_tool("regex_replace", "Find and replace text using regex", {"type": "object", "properties": {"text": {"type": "string", "description": "Input text"}, "pattern": {"type": "string", "description": "Regex pattern to find"}, "replacement": {"type": "string", "description": "Replacement text"}, "flags": {"type": "string", "description": "Regex flags: i=ignore case, m=multiline, s=dotall"}}, "required": ["text", "pattern", "replacement"]}, regex_replace, "utility"),
        _make_tool("json_validate", "Validate whether a string is valid JSON", {"type": "object", "properties": {"text": {"type": "string", "description": "JSON string to validate"}}, "required": ["text"]}, json_validate, "utility"),
        _make_tool("json_transform", "Query/filter JSON data using dot-notation path", {"type": "object", "properties": {"data": {"type": "string", "description": "JSON string"}, "query": {"type": "string", "description": "Optional dot-notation query (e.g., items.0.name)"}}, "required": ["data"]}, json_transform, "utility"),
        _make_tool("csv_parse", "Parse CSV content and show preview", {"type": "object", "properties": {"content": {"type": "string", "description": "CSV content as string"}, "delimiter": {"type": "string", "description": "Delimiter character (default comma)"}}, "required": ["content"]}, csv_parse, "utility"),
        _make_tool("csv_to_json", "Convert CSV content to JSON", {"type": "object", "properties": {"content": {"type": "string", "description": "CSV content as string"}, "delimiter": {"type": "string", "description": "Delimiter character (default comma)"}}, "required": ["content"]}, csv_to_json, "utility"),
        _make_tool("markdown_to_html", "Convert markdown text to HTML", {"type": "object", "properties": {"markdown_text": {"type": "string", "description": "Markdown content"}}, "required": ["markdown_text"]}, markdown_to_html, "utility"),
        _make_tool("date_format", "Format a date string into a different format", {"type": "object", "properties": {"date_str": {"type": "string", "description": "Date string to format"}, "input_format": {"type": "string", "description": "Input format (e.g. %%Y-%%m-%%d). Auto-detects ISO if empty"}, "output_format": {"type": "string", "description": "Output format (default %%Y-%%m-%%d %%H:%%M:%%S)"}}, "required": ["date_str"]}, date_format, "utility"),
        _make_tool("timezone_convert", "Convert datetime between timezones", {"type": "object", "properties": {"date_str": {"type": "string", "description": "Date string"}, "from_tz": {"type": "string", "description": "Source timezone (default UTC)"}, "to_tz": {"type": "string", "description": "Target timezone (default US/Eastern)"}, "input_format": {"type": "string", "description": "Input format (default %%Y-%%m-%%d %%H:%%M:%%S)"}}, "required": ["date_str"]}, timezone_convert, "utility"),
        _make_tool("unit_convert", "Convert between units (temperature, distance, weight, volume, length)", {"type": "object", "properties": {"value": {"type": "number", "description": "Numeric value to convert"}, "from_unit": {"type": "string", "description": "Source unit (c, f, km, mi, kg, lb, m, ft, l, gal)"}, "to_unit": {"type": "string", "description": "Target unit"}}, "required": ["value", "from_unit", "to_unit"]}, unit_convert, "utility"),
    ]


def get_crypto_tools():
    from backend.tools.crypto_tools import generate_uuid, generate_password, generate_hash, encrypt_text, decrypt_text, check_hash
    return [
        _make_tool("generate_uuid", "Generate a UUID (version 1, 4, or 7)", {"type": "object", "properties": {"version": {"type": "integer", "description": "UUID version: 1, 4 (default), or 7"}}, "required": []}, generate_uuid, "utility"),
        _make_tool("generate_password", "Generate a cryptographically secure random password", {"type": "object", "properties": {"length": {"type": "integer", "description": "Password length (default 16, min 4)"}, "include_digits": {"type": "boolean", "description": "Include digits (default true)"}, "include_symbols": {"type": "boolean", "description": "Include symbols (default true)"}}, "required": []}, generate_password, "utility"),
        _make_tool("generate_hash", "Generate hash of a text string (MD5, SHA1, SHA256, SHA512)", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to hash"}, "algorithm": {"type": "string", "description": "Algorithm: md5, sha1, sha256, sha512 (default sha256)"}}, "required": ["text"]}, generate_hash, "utility"),
        _make_tool("encrypt_text", "Encrypt text using Fernet symmetric encryption", {"type": "object", "properties": {"plaintext": {"type": "string", "description": "Text to encrypt"}, "key": {"type": "string", "description": "Optional encryption key (auto-generated if empty)"}}, "required": ["plaintext"]}, encrypt_text, "utility"),
        _make_tool("decrypt_text", "Decrypt Fernet-encrypted text using a key", {"type": "object", "properties": {"ciphertext": {"type": "string", "description": "Encrypted text"}, "key": {"type": "string", "description": "Encryption key"}}, "required": ["ciphertext", "key"]}, decrypt_text, "utility"),
        _make_tool("check_hash", "Check if text matches a given hash", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to verify"}, "hash_value": {"type": "string", "description": "Expected hash value"}, "algorithm": {"type": "string", "description": "Algorithm: md5, sha1, sha256, sha512 (default sha256)"}}, "required": ["text", "hash_value"]}, check_hash, "utility"),
    ]


def get_net_tools():
    from backend.tools.net_tools import ping_host, dns_lookup, whois_lookup, geoip_lookup
    return [
        _make_tool("ping_host", "Ping a host to check connectivity", {"type": "object", "properties": {"host": {"type": "string", "description": "Hostname or IP address"}, "count": {"type": "integer", "description": "Number of pings (default 4)"}}, "required": ["host"]}, ping_host, "utility"),
        _make_tool("dns_lookup", "Look up DNS A records for a hostname", {"type": "object", "properties": {"host": {"type": "string", "description": "Hostname to look up"}, "record_type": {"type": "string", "description": "Record type: A (default)"}}, "required": ["host"]}, dns_lookup, "utility"),
        _make_tool("whois_lookup", "Perform a WHOIS lookup for a domain", {"type": "object", "properties": {"domain": {"type": "string", "description": "Domain name to query"}}, "required": ["domain"]}, whois_lookup, "utility"),
        _make_tool("geoip_lookup", "Look up geolocation data for an IP address or hostname", {"type": "object", "properties": {"ip_or_host": {"type": "string", "description": "IP address or hostname"}}, "required": ["ip_or_host"]}, geoip_lookup, "utility"),
    ]


def get_misc_tools():
    from backend.tools.misc_tools import random_number, random_choice, color_convert, math_calculate, query_yesno
    return [
        _make_tool("random_number", "Generate a random number between min and max", {"type": "object", "properties": {"min_val": {"type": "number", "description": "Minimum value (default 0)"}, "max_val": {"type": "number", "description": "Maximum value (default 100)"}, "integer": {"type": "boolean", "description": "Return integer (default true)"}}, "required": []}, random_number, "utility"),
        _make_tool("random_choice", "Pick random item(s) from a list", {"type": "object", "properties": {"options": {"type": "array", "items": {"type": "string"}, "description": "List of options to choose from"}, "count": {"type": "integer", "description": "Number of items to pick (default 1)"}}, "required": ["options"]}, random_choice, "utility"),
        _make_tool("color_convert", "Convert between color formats (hex, rgb, hsl)", {"type": "object", "properties": {"color": {"type": "string", "description": "Color value"}, "from_format": {"type": "string", "description": "Source format: hex, rgb (default hex)"}, "to_format": {"type": "string", "description": "Target format: rgb, hex, hsl (default rgb)"}}, "required": ["color"]}, color_convert, "utility"),
        _make_tool("math_calculate", "Evaluate a simple arithmetic expression", {"type": "object", "properties": {"expression": {"type": "string", "description": "Arithmetic expression (numbers, +, -, *, /, %, parentheses)"}}, "required": ["expression"]}, math_calculate, "utility"),
        _make_tool("query_yesno", "Ask a yes/no question and get a random answer", {"type": "object", "properties": {"question": {"type": "string", "description": "Yes/no question to ask"}}, "required": ["question"]}, query_yesno, "utility"),
    ]


def get_code_tools():
    from backend.tools.code_tools import run_python, render_template
    return [
        _make_tool("run_python", "Execute Python code in a sandboxed environment", {"type": "object", "properties": {"code": {"type": "string", "description": "Python code to execute"}, "timeout": {"type": "integer", "description": "Execution timeout in seconds (default 5)"}}, "required": ["code"]}, run_python, "utility"),
        _make_tool("render_template", "Render a Jinja2 template with JSON data", {"type": "object", "properties": {"template_text": {"type": "string", "description": "Jinja2 template string"}, "data_json": {"type": "string", "description": "JSON data for template variables"}}, "required": ["template_text", "data_json"]}, render_template, "utility"),
    ]


def get_system_tools():
    from backend.tools.system_tools import system_info, disk_usage
    return [
        _make_tool("system_info", "Get system information: OS, hostname, Python, CPU, RAM, processes", {"type": "object", "properties": {}, "required": []}, system_info, "system"),
        _make_tool("disk_usage", "Check disk usage for a path", {"type": "object", "properties": {"path": {"type": "string", "description": "Path to check (default current directory)"}}, "required": []}, disk_usage, "system"),
    ]


def get_webhook_tools():
    from backend.tools.webhook_tools import webhook_register, webhook_trigger, webhook_list, webhook_delete
    return [
        _make_tool("webhook_register", "Register an HTTP webhook endpoint", {"type": "object", "properties": {"name": {"type": "string", "description": "Webhook name"}, "url": {"type": "string", "description": "Webhook URL"}, "secret": {"type": "string", "description": "Optional secret for HMAC signing"}, "events": {"type": "string", "description": "Comma-separated event types to subscribe to"}}, "required": ["name", "url"]}, webhook_register, "system"),
        _make_tool("webhook_trigger", "Trigger a registered webhook with a JSON payload", {"type": "object", "properties": {"name": {"type": "string", "description": "Webhook name"}, "payload_json": {"type": "string", "description": "JSON payload (default {})"}}, "required": ["name"]}, webhook_trigger, "system"),
        _make_tool("webhook_list", "List all registered webhooks", {"type": "object", "properties": {}, "required": []}, webhook_list, "system"),
        _make_tool("webhook_delete", "Delete a registered webhook", {"type": "object", "properties": {"name": {"type": "string", "description": "Webhook name to delete"}}, "required": ["name"]}, webhook_delete, "system"),
    ]


def get_all_tool_batches():
    """Returns list of lists, each containing Tool objects for one category."""
    return [
        get_computer_control_tools(),
        get_audio_editor_tools(),
        get_personality_tools(),
        get_api_integration_tools(),
        get_security_tools(),
        get_monitoring_tools(),
        get_qol_tools(),
        get_scifi_tools(),
        get_info_scraper_tools(),
        get_context_optimizer_tools(),
        get_multi_agent_tools(),
        get_pdf_tools(),
        get_health_tools(),
        get_file_tools(),
        get_text_tools(),
        get_crypto_tools(),
        get_net_tools(),
        get_misc_tools(),
        get_code_tools(),
        get_system_tools(),
        get_webhook_tools(),
        get_data_tools_from_data(),
        get_media_tools(),
        get_advanced_tools(),
        get_color_emotion_tools(),
    ]


def get_data_tools_from_data():
    from backend.tools.data_tools import get_data_tools
    return get_data_tools()


def get_media_tools():
    from backend.tools.media_tools import get_media_tools as _gmt
    return _gmt()


def get_advanced_tools():
    from backend.tools.advanced_tools import get_advanced_tools as _gat
    return _gat()


def get_color_emotion_tools():
    from backend.tools.color_emotion_tools import (
        extract_dominant_colors, color_name_from_rgb, color_name_from_hex,
        color_palette_generate, color_analyze_image_url, color_analyze_local_image,
        detect_emotion_face, detect_emotion_text, detect_faces_image,
        analyze_face_attributes, compare_faces, analyze_emotion_realtime,
    )
    return [
        _make_tool("extract_dominant_colors", "Extract dominant colors from a list of [R,G,B] pixel arrays — returns hex, name, and percentage for each", {"type": "object", "properties": {"pixels": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "List of [r,g,b] pixel arrays"}, "num_colors": {"type": "integer", "description": "Number of dominant colors to extract (default 5)"}}, "required": ["pixels"]}, extract_dominant_colors, "vision"),
        _make_tool("color_name_from_rgb", "Map RGB values (0-255) to the nearest named color — returns hex, name", {"type": "object", "properties": {"r": {"type": "integer", "description": "Red 0-255"}, "g": {"type": "integer", "description": "Green 0-255"}, "b": {"type": "integer", "description": "Blue 0-255"}}, "required": ["r", "g", "b"]}, color_name_from_rgb, "vision"),
        _make_tool("color_name_from_hex", "Map a hex color string (e.g. #ff5733) to the nearest named color", {"type": "object", "properties": {"hex_color": {"type": "string", "description": "Hex color string (e.g. #ff5733)"}}, "required": ["hex_color"]}, color_name_from_hex, "vision"),
        _make_tool("color_palette_generate", "Generate a monochromatic color palette from a base hex color", {"type": "object", "properties": {"base_color": {"type": "string", "description": "Base hex color (e.g. #3498db)"}, "num_shades": {"type": "integer", "description": "Number of shades to generate (default 5)"}}, "required": ["base_color"]}, color_palette_generate, "vision"),
        _make_tool("color_analyze_image_url", "Download an image from URL and extract its dominant color palette (hex, name, percentage)", {"type": "object", "properties": {"image_url": {"type": "string", "description": "URL of the image to analyze"}}, "required": ["image_url"]}, color_analyze_image_url, "vision"),
        _make_tool("color_analyze_local_image", "Analyze a local image file and return dominant color palette", {"type": "object", "properties": {"file_path": {"type": "string", "description": "Path to local image file"}}, "required": ["file_path"]}, color_analyze_local_image, "vision"),
        _make_tool("detect_emotion_face", "Detect emotion from a face image using DeepFace — returns emotion scores, age, gender, race", {"type": "object", "properties": {"image_path": {"type": "string", "description": "Path to image file"}}, "required": ["image_path"]}, detect_emotion_face, "vision"),
        _make_tool("detect_emotion_text", "Analyze text for emotional sentiment using BERT emotion classifier — returns dominant emotion with scores", {"type": "object", "properties": {"text": {"type": "string", "description": "Text to analyze for emotional content"}}, "required": ["text"]}, detect_emotion_text, "vision"),
        _make_tool("detect_faces_image", "Detect faces in an image using OpenCV Haar Cascade — returns count and bounding boxes", {"type": "object", "properties": {"image_path": {"type": "string", "description": "Path to image file"}}, "required": ["image_path"]}, detect_faces_image, "vision"),
        _make_tool("analyze_face_attributes", "Analyze age, gender, emotion, and race from a face image using DeepFace", {"type": "object", "properties": {"image_path": {"type": "string", "description": "Path to image file"}}, "required": ["image_path"]}, analyze_face_attributes, "vision"),
        _make_tool("compare_faces", "Compare two face images and return similarity score and verification result using DeepFace", {"type": "object", "properties": {"image1_path": {"type": "string", "description": "Path to first face image"}, "image2_path": {"type": "string", "description": "Path to second face image"}}, "required": ["image1_path", "image2_path"]}, compare_faces, "vision"),
        _make_tool("analyze_emotion_realtime", "Capture and analyze emotion from real-time camera frame (pass base64-encoded frame pixels)", {"type": "object", "properties": {"face_frame_pixels": {"type": "string", "description": "Base64-encoded frame pixel data"}}, "required": []}, analyze_emotion_realtime, "vision"),
    ]
