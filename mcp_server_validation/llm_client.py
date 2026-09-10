"""
LLM Client Module
"""

import requests
from typing import Any, Dict


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
            print(f"Testing connection to: {url}")

            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )

            print(f"Response status: {response.status_code}")

            if response.status_code == 200:
                self.connected = True
                print(f"Successfully connected to LLM server at {self.server_url}")
                return True

            print(f"LLM connection failed: {response.status_code} - {response.text}")
            self.connected = False
            return False

        except requests.exceptions.Timeout:
            print("LLM connection timed out")
        except requests.exceptions.ConnectionError:
            print("Could not connect to LLM server")
        except requests.exceptions.RequestException as exc:
            print(f"LLM request failed: {exc}")

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
        """
        Send a prompt to the LLM and return the raw API response.
        The caller can extract:
            response["usage"]
        to obtain real token usage.
        """

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

            if response.status_code != 200:
                print(f"LLM server response: {response.text}")

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as exc:
            print(f"LLM generation failed: {exc}")
            raise RuntimeError(f"LLM generation failed: {exc}") from exc

    def get_usage(
        self,
        response: Dict[str, Any],
    ) -> Dict[str, int]:
        """
        Extract token usage from an API response.

        Returns zero values if the server does not provide usage.
        """

        usage = response.get("usage", {})

        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }

    def get_output_text(
        self,
        response: Dict[str, Any],
    ) -> str:
        """
        Extract generated text from the Responses API response.
        """

        if "output_text" in response:
            return response["output_text"]

        output = response.get("output", [])

        texts = []

        for item in output:
            content = item.get("content", [])

            for content_item in content:
                if content_item.get("type") == "output_text":
                    text = content_item.get("text", "")
                    if text:
                        texts.append(text)

        return "\n".join(texts)

    def get_connection_info(self) -> Dict[str, Any]:
        """Return non-sensitive connection information."""

        return {
            "connected": self.connected,
            "server_url": self.server_url,
            "model": self.model,
        }
