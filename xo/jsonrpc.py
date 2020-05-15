# Inspired by jsonrpc_websocket
import random
import asyncio
import aiohttp # websockets require python >= 3.6.1

class JsonRpc():
    def __init__(self, url: str):
        self._session = aiohttp.ClientSession()
        self._client = None
        self._url = url
        self._pending_messages = {}

    async def send(self, method: str, params: dict = {}):
        if self._client is None:
            raise ValueError('Client not connected.')

        msg_id = random.randint(1, 9007199254740991)
        message = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "id": msg_id
        }

        pending_message = PendingMessage()
        self._pending_messages[msg_id] = pending_message

        await self._client.send_json(message)

        response = await pending_message.wait()
        del self._pending_messages[msg_id]

        if "result" in response:
            return response["result"]
        else:
            raise ValueError("Error reply from RPC call:\n{}".format(response))

    async def connect(self):
        if self._client is not None:
            raise ValueError('Connection already open.')

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json-rpc",
        }

        self._client = await self._session.ws_connect(self._url, headers=headers)

        return asyncio.get_running_loop().create_task(self._loop())

    async def _loop(self):
        try:
            while True:
                data = await self._client.receive_json()
                if "id" not in data:
                    continue

                self._pending_messages[data['id']].set_response(data)
        finally:
            await self.close()

    async def close(self):
        if self._client is not None:
            await self._client.close()
            await self._session.close()
            self._client = None

class PendingMessage(object):
    def __init__(self):
        self._event = asyncio.Event()
        self.response = None

    async def wait(self):
        await self._event.wait()
        return self.response

    def set_response(self, value):
        self.response = value
        self._event.set()
