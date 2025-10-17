# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Whisper-Input is a voice-to-text application that provides real-time speech transcription and translation using keyboard shortcuts. It supports two main ASR services:
- **Groq** (Whisper Large V3 Turbo)
- **SiliconFlow** (FunAudioLLM/SenseVoiceSmall - faster with built-in punctuation)

The application runs in the background and responds to keyboard shortcuts:
- Hold Option/Alt key for voice transcription
- Hold Shift + Option/Alt for voice translation (to English)

## Architecture

### Core Components

- **main.py**: Application entry point that initializes the VoiceAssistant
- **src/audio/recorder.py**: AudioRecorder class for capturing microphone input
- **src/keyboard/listener.py**: KeyboardManager class for handling keyboard shortcuts
- **src/transcription/**: Audio processing services
  - `whisper.py`: WhisperProcessor for Groq API
  - `senseVoiceSmall.py`: SenseVoiceSmallProcessor for SiliconFlow API
- **src/llm/**: Text processing utilities
  - `symbol.py`: SymbolProcessor for adding punctuation
  - `translate.py`: TranslateProcessor for translation services
- **src/utils/logger.py**: Logging utilities

### Application Flow

1. KeyboardManager listens for Option/Alt key combinations
2. When triggered (after 0.5s delay), it starts AudioRecorder
3. Upon key release, audio is sent to the configured processor
4. Processed text is automatically typed at current cursor position
5. Results are copied to clipboard (configurable)

### State Management

The application uses an InputState enum with states:
- IDLE, RECORDING, RECORDING_TRANSLATE, PROCESSING, TRANSLATING, ERROR, WARNING

## Development Commands

### Setup and Installation

```bash
# Clone repository
git clone git@github.com:ErlichLiu/Whisper-Input.git

# Create virtual environment
python -m venv venv

# Activate virtual environment
# macOS/Linux
source venv/bin/activate
# Windows
.\venv\Scripts\activate

# Install dependencies
pip install pip-tools
pip-compile requirements.in
pip install -r requirements.txt
```

### Running the Application

```bash
# Main entry point
python main.py

# Alternative commands from package.json
npm start
npm run voice
```

### Environment Configuration

Required `.env` file (copy from `.env.example` if available):

For Groq:
```
SERVICE_PLATFORM=groq
GROQ_API_KEY=your_groq_api_key
```

For SiliconFlow (recommended):
```
SERVICE_PLATFORM=siliconflow
SILICONFLOW_API_KEY=your_siliconflow_api_key
```

Optional configuration:
```
CONVERT_TO_SIMPLIFIED=true/false
ADD_SYMBOL=true/false
OPTIMIZE_RESULT=true/false
KEEP_ORIGINAL_CLIPBOARD=true/false
SYSTEM_PLATFORM=win/mac (auto-detected)
TRANSCRIPTIONS_BUTTON=alt
TRANSLATIONS_BUTTON=shift
```

## Platform-Specific Notes

### macOS Requirements
- Accessibility permissions for keyboard monitoring
- Microphone permissions for audio recording
- Requires Terminal to be granted both permissions

### Windows Support
- Configures to use Ctrl instead of Cmd for keyboard shortcuts
- Same functionality as macOS with different key mappings

## Key Implementation Details

### Timeout Handling
Both processors use a timeout_decorator (10 seconds) to prevent hanging API calls.

### Audio Processing
- Audio is captured as bytes buffer in WAV format
- Sample rate automatically adjusts to device capabilities
- Minimum recording duration: 1 second

### Keyboard Shortcuts
- 0.5 second delay before triggering to prevent accidental activation
- State-based UI feedback shows current operation status
- Automatic cleanup of temporary text and clipboard restoration

## Common Issues

1. **Permission Errors**: Ensure accessibility and microphone permissions are granted
2. **API Timeouts**: Default 20-second timeout, can be modified in processor classes
3. **Audio Device Issues**: Application auto-detects device changes and logs information

## Logging

The application uses colorlog for colored console output. All major operations are logged with timestamps and status information.