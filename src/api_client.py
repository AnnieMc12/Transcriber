"""Mistral Audio Transcriptions API client."""

import requests

API_URL = "https://api.mistral.ai/v1/audio/transcriptions"
MODEL = "voxtral-mini-latest"
TIMEOUT_SECONDS = 600  # 10 minutes per chunk


class TranscriptionError(Exception):
    """Raised when the API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def transcribe_file(file_path: str, api_key: str) -> dict:
    """Send an audio file to the Mistral transcription API.

    Returns the parsed JSON response containing 'text' and 'segments'.
    Raises TranscriptionError on failure.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    data = {
        "model": MODEL,
        "diarize": "true",
        "timestamp_granularities": "segment",
    }

    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.split("/")[-1].split("\\")[-1], f)}
            response = requests.post(
                API_URL,
                headers=headers,
                data=data,
                files=files,
                timeout=TIMEOUT_SECONDS,
            )
    except requests.exceptions.Timeout:
        raise TranscriptionError(
            "Request timed out. The audio file may be too large for a single "
            "request. Try a smaller file or ensure chunking is enabled."
        )
    except requests.exceptions.ConnectionError:
        raise TranscriptionError(
            "Could not connect to the Mistral API. Check your internet connection."
        )
    except requests.exceptions.RequestException as e:
        raise TranscriptionError(f"Network error: {e}")

    if response.status_code == 401:
        raise TranscriptionError(
            "Authentication failed. Please check your API key.", 401
        )
    if response.status_code == 429:
        raise TranscriptionError(
            "Rate limit exceeded. Please wait a moment and try again.", 429
        )
    if response.status_code != 200:
        try:
            detail = response.json().get("message", response.text)
        except Exception:
            detail = response.text
        raise TranscriptionError(
            f"API error (HTTP {response.status_code}): {detail}",
            response.status_code,
        )

    return response.json()
