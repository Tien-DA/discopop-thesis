"""
LLM client for OpenAI-compatible APIs.
"""

from typing import Any, Dict

import requests

from utils.logger import setup_logger

logger = setup_logger(__name__)


class LLMClient:
    """Client for communicating with an OpenAI-compatible LLM server."""

    def __init__(self):
        self.server_url = ""
        self.api_key = ""
        self.model = ""
        self.session = requests.Session()
        self.connected = False

    def connect(
        self,
        server_url: str,
        api_key: str,
        model: str,
    ) -> bool:
        """Test and establish a connection to the LLM server."""

        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.model = model

        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

        payload = {
            "model": model,
            "input": "Hello, this is a test connection.",
        }

        url = f"{self.server_url}/responses"

        try:
            logger.info("Testing connection to: %s", url)

            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )

            logger.info("Response status: %s", response.status_code)

            if response.status_code == 200:
                self.connected = True
                logger.info(
                    "Successfully connected to LLM server at %s",
                    self.server_url,
                )
                return True

            logger.error(
                "LLM connection failed: %s - %s",
                response.status_code,
                response.text,
            )
            self.connected = False
            return False

        except requests.exceptions.Timeout:
            logger.error("LLM connection timed out")
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to LLM server")
        except requests.exceptions.RequestException as exc:
            logger.error("LLM request failed: %s", exc)

        self.connected = False
        return False

    def is_connected(self) -> bool:
        """Return whether the LLM client is connected."""

        return self.connected

    def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """Send a prompt to the LLM and return the raw API response."""

        if not self.connected:
            raise RuntimeError("LLM client is not connected")

        payload = {
            "model": self.model,
            "input": prompt,
            "max_output_tokens": max_tokens,
        }

        url = f"{self.server_url}/responses"

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=300,
            )

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as exc:
            logger.error("LLM generation failed: %s", exc)
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    def get_connection_info(self) -> Dict[str, Any]:
        """Return non-sensitive connection information."""

        return {
            "connected": self.connected,
            "server_url": self.server_url,
            "model": self.model,
        }