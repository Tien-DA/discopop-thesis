"""
LLM Client Module.

This class is responsible only for communicating with and testing
the OpenAI-compatible LLM server.

The actual coding agent is OpenCode.
"""

from __future__ import annotations

from typing import Any

import requests


class LLMClient:
    """Client for communicating with an OpenAI-compatible LLM server."""

    def __init__(self) -> None:
        self.server_url = ""
        self.api_key = ""
        self.model = ""

        self.session = requests.Session()

        self.connected = False

    # ==============================================================
    # CONNECTION
    # ==============================================================

    def connect(
        self,
        server_url: str,
        api_key: str,
        model: str,
    ) -> bool:
        """
        Test and establish a connection to the LLM server.
        """

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
            "input": "Hello, this is a tests connection.",
        }

        url = f"{self.server_url}/responses"

        try:
            print()
            print(
                f"Testing connection to: {url}"
            )

            response = self.session.post(
                url,
                json=payload,
                timeout=30,
            )

            print(
                f"Response status: {response.status_code}"
            )

            if response.status_code == 200:
                self.connected = True

                print(
                    f"Successfully connected to LLM server "
                    f"at {self.server_url}"
                )

                return True

            print(
                "LLM connection failed:"
            )

            print(
                f"  Status: {response.status_code}"
            )

            print(
                f"  Response: {response.text}"
            )

            self.connected = False

            return False

        except requests.exceptions.Timeout:
            print(
                "LLM connection timed out."
            )

        except requests.exceptions.ConnectionError:
            print(
                "Could not connect to LLM server."
            )

        except requests.exceptions.RequestException as exc:
            print(
                f"LLM request failed: {exc}"
            )

        self.connected = False

        return False

    # ==============================================================
    # STATUS
    # ==============================================================

    def is_connected(self) -> bool:
        """Return whether the LLM client is connected."""

        return self.connected

    # ==============================================================
    # DIRECT GENERATION
    # ==============================================================

    def generate(
        self,
        prompt: str,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        """
        Send a direct request to the LLM.

        NOTE:
        The benchmark does NOT use this method as its coding agent.

        OpenCode is responsible for coding-agent execution.
        """

        if not self.connected:
            raise RuntimeError(
                "LLM client is not connected."
            )

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
                print(
                    "LLM server response:"
                )

                print(
                    response.text
                )

            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as exc:
            print(
                f"LLM generation failed: {exc}"
            )

            raise RuntimeError(
                f"LLM generation failed: {exc}"
            ) from exc

    # ==============================================================
    # TOKEN USAGE
    # ==============================================================

    def get_usage(
        self,
        response: dict[str, Any],
    ) -> dict[str, int]:
        """
        Extract token usage from a Responses API response.
        """

        usage = response.get(
            "usage",
            {},
        )

        return {
            "input_tokens": int(
                usage.get(
                    "input_tokens",
                    0,
                )
                or 0
            ),
            "output_tokens": int(
                usage.get(
                    "output_tokens",
                    0,
                )
                or 0
            ),
            "total_tokens": int(
                usage.get(
                    "total_tokens",
                    0,
                )
                or 0
            ),
        }

    # ==============================================================
    # OUTPUT TEXT
    # ==============================================================

    def get_output_text(
        self,
        response: dict[str, Any],
    ) -> str:
        """
        Extract generated text from a Responses API response.
        """

        if "output_text" in response:
            return response["output_text"]

        output = response.get(
            "output",
            [],
        )

        texts: list[str] = []

        for item in output:
            content = item.get(
                "content",
                [],
            )

            for content_item in content:

                if content_item.get(
                    "type"
                ) != "output_text":
                    continue

                text = content_item.get(
                    "text",
                    "",
                )

                if text:
                    texts.append(text)

        return "\n".join(texts)

    # ==============================================================
    # CONNECTION INFORMATION
    # ==============================================================

    def get_connection_info(
        self,
    ) -> dict[str, Any]:
        """
        Return non-sensitive connection information.
        """

        return {
            "connected": self.connected,
            "server_url": self.server_url,
            "model": self.model,
        }