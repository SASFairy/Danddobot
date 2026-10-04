import asyncio
import json
import os
import tempfile
import unittest
from types import SimpleNamespace

from src.bot_settings import BotSettingsController
from src.config import AppConfig
from src.llm_client import GroqClient, LLMClientFactory, OllamaClient
from src.state_manager import StateManager


class LocalOpenAIServer:
    def __init__(self, statuses):
        self.statuses = statuses
        self.requests = []
        self.server = None

    async def __aenter__(self):
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.server.close()
        await self.server.wait_closed()

    async def _handle(self, reader, writer):
        request_head = await reader.readuntil(b"\r\n\r\n")
        header_text = request_head.decode("utf-8")
        lines = header_text.split("\r\n")
        method, path, _ = lines[0].split(" ", 2)
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.lower()] = value.strip()

        content_length = int(headers.get("content-length", 0))
        if content_length:
            await reader.readexactly(content_length)

        authorization = headers.get("authorization")
        self.requests.append((method, path, authorization))
        status = self.statuses.get(authorization, 200)
        if path == "/v1/models" and status == 200:
            payload = {"data": [{"id": "test-model"}]}
        elif status == 200:
            payload = {"choices": [{"message": {"content": "ok"}}]}
        else:
            payload = {"error": {"message": f"status {status}"}}

        body = json.dumps(payload).encode("utf-8")
        reasons = {200: "OK", 400: "Bad Request", 401: "Unauthorized", 429: "Too Many Requests", 500: "Internal Server Error"}
        response = (
            f"HTTP/1.1 {status} {reasons[status]}\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n"
        ).encode("utf-8") + body
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()


class GroqClientTests(unittest.IsolatedAsyncioTestCase):
    def test_config_uses_groq_defaults_and_keys(self):
        original_environment = os.environ.copy()
        try:
            os.environ.update({
                "LLM_PROVIDER": "groq",
                "LLM_API_URL": "http://local-llm:11434",
                "GROQ_API_KEY": "first-key,second-key",
            })
            os.environ.pop("GROQ_API_URL", None)
            with tempfile.TemporaryDirectory() as directory:
                state_manager = StateManager(os.path.join(directory, "state.json"))
                config = AppConfig(state_manager)

            self.assertEqual(config.llm_provider, "GROQ")
            self.assertEqual(config.llm_api_url, "https://api.groq.com/openai")
            self.assertEqual(config.groq_api_key, "first-key,second-key")
        finally:
            os.environ.clear()
            os.environ.update(original_environment)

    async def test_factory_builds_groq_client_with_trimmed_keys(self):
        client = LLMClientFactory.get_client(
            provider="GROQ",
            api_url="",
            model="test-model",
            api_key=" first-key, second-key ",
        )
        self.addAsyncCleanup(client.close)

        self.assertIsInstance(client, GroqClient)
        self.assertEqual(client.api_url, "https://api.groq.com/openai")
        self.assertEqual(client.api_keys, ["first-key", "second-key"])

    async def test_rate_limit_rotates_to_next_key_and_keeps_it_active(self):
        statuses = {"Bearer first-key": 429, "Bearer second-key": 200}
        async with LocalOpenAIServer(statuses) as server:
            client = GroqClient(server.base_url, "test-model", "first-key,second-key")
            self.addAsyncCleanup(client.close)

            result = await client.generate_response("hello")

            self.assertEqual(result, "ok")
            self.assertEqual(client.current_key_index, 1)
            self.assertEqual(
                [authorization for _, _, authorization in server.requests],
                ["Bearer first-key", "Bearer second-key"],
            )

    async def test_runtime_provider_switch_passes_groq_keys(self):
        async with LocalOpenAIServer({"Bearer first-key": 200}) as server:
            with tempfile.TemporaryDirectory() as directory:
                state_manager = StateManager(os.path.join(directory, "state.json"))
                old_client = OllamaClient("http://127.0.0.1:1", "old-model")
                client = SimpleNamespace(
                    state_manager=state_manager,
                    provider_urls={"GROQ": server.base_url},
                    provider_api_keys={"GROQ": "first-key,second-key"},
                    llm_client=old_client,
                    available_models=[],
                )

                await BotSettingsController(client).update_llm_provider("GROQ")
                self.addAsyncCleanup(client.llm_client.close)

                self.assertIsInstance(client.llm_client, GroqClient)
                self.assertEqual(client.llm_client.api_keys, ["first-key", "second-key"])
                self.assertEqual(client.available_models, ["test-model"])
                self.assertEqual(state_manager.get_value("llm_provider"), "GROQ")

    async def test_bad_request_does_not_rotate_keys(self):
        statuses = {"Bearer first-key": 400, "Bearer second-key": 200}
        async with LocalOpenAIServer(statuses) as server:
            client = GroqClient(server.base_url, "test-model", "first-key,second-key")
            self.addAsyncCleanup(client.close)

            with self.assertRaisesRegex(RuntimeError, "HTTP 400"):
                await client.generate_response("hello")

            self.assertEqual(client.current_key_index, 0)
            self.assertEqual(len(server.requests), 1)

    async def test_model_fetch_rotates_on_authentication_failure(self):
        statuses = {"Bearer first-key": 401, "Bearer second-key": 200}
        async with LocalOpenAIServer(statuses) as server:
            client = GroqClient(server.base_url, "test-model", "first-key,second-key")
            self.addAsyncCleanup(client.close)

            models = await client.get_available_models()

            self.assertEqual(models, ["test-model"])
            self.assertEqual(client.current_key_index, 1)

    async def test_all_retryable_key_failures_raise_after_one_attempt_each(self):
        statuses = {"Bearer first-key": 429, "Bearer second-key": 500}
        async with LocalOpenAIServer(statuses) as server:
            client = GroqClient(server.base_url, "test-model", "first-key,second-key")
            self.addAsyncCleanup(client.close)

            with self.assertRaisesRegex(RuntimeError, "모든 등록된 Groq API 키"):
                await client.generate_response("hello")

            self.assertEqual(len(server.requests), 2)



    async def test_missing_keys_fails_before_network_request(self):
        client = GroqClient("http://127.0.0.1:1", "test-model", "")
        self.addAsyncCleanup(client.close)

        with self.assertRaisesRegex(RuntimeError, "Groq API 키"):
            await client.generate_response("hello")


if __name__ == "__main__":
    unittest.main()
