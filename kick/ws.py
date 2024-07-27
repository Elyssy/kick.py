from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aiohttp import ClientWebSocketResponse as WebSocketResponse

from .livestream import PartialLivestream, LivestreamEnd
from .message import Message

if TYPE_CHECKING:
    from .http import HTTPClient

from datetime import datetime

__all__ = ()


class PusherWebSocket:
    def __init__(self, ws: WebSocketResponse, *, http: HTTPClient):
        self.ws = ws
        self.http = http
        self.send_json = ws.send_json
        self.close = ws.close

    async def poll_event(self) -> None:
        raw_msg = await self.ws.receive()
        raw_data = raw_msg.json()
        data = json.loads(raw_data["data"])

        self.http.client.dispatch("payload_receive", raw_data["event"], data)
        self.http.client.dispatch("raw_payload_receive", raw_data)

        match raw_data["event"]:
            case "App\\Events\\ChatMessageEvent":
                msg = Message(data=data, http=self.http)
                self.http.client.dispatch("message", msg)
            case "App\\Events\\StreamerIsLive":
                livestream = PartialLivestream(data=data["livestream"], http=self.http)
                self.http.client.dispatch("livestream_start", livestream)
            case "App\\Events\\FollowersUpdated":
                user = self.http.client._watched_users[data["channel_id"]]
                if data["followed"] is True:
                    event = "follow"
                    user._data["followers_count"] += 1
                else:
                    event = "unfollow"
                    user._data["followers_count"] -= 1

                self.http.client.dispatch(event, user)
            case "App\\Events\\StopStreamBroadcast":
                livestream = LivestreamEnd(data=data["livestream"], http=self.http)
                self.http.client.dispatch("livestream_end", livestream)
            case "App\\Events\\UserBannedEvent":
                user = self.http.client.get_partial_user(username=data['user']['username'], id=data['user']['id'])
                chatroom = self.http.client.get_chatroom(int(raw_data['channel'].lstrip('chatrooms.').rstrip('.v2')))
                banned_by = await self.http.client.get_partial_chatter(chatter_name=data['banned_by']['username'], streamer_name=chatroom.streamer.username).to_user()

                match data['permanent']:
                    case False:
                        self.http.client.dispatch("timeout", user, chatroom, banned_by, datetime.fromisoformat(data['expires_at']))
                    case True:
                        self.http.client.dispatch("ban", user, chatroom, banned_by)
            case "App\\Events\\UserUnbannedEvent":
                user = self.http.client.get_partial_user(username=data['user']['username'], id=data['user']['id'])
                chatroom = self.http.client.get_chatroom(int(raw_data['channel'].lstrip('chatrooms.').rstrip('.v2')))
                unbanned_by = await self.http.client.get_partial_chatter(chatter_name=data['unbanned_by']['username'], streamer_name=chatroom.streamer.username).to_user()

                match data['permanent']:
                    case False:
                        self.http.client.dispatch("untimeout", user, chatroom, unbanned_by)
                    case True:
                        self.http.client.dispatch("unban", user, chatroom, unbanned_by)
            case "App\\Events\\ChatroomClearEvent":
                chatroom = self.http.client.get_chatroom(int(raw_data['channel'].lstrip('chatrooms.').rstrip('.v2')))
                self.http.client.dispatch("chatroom_clear", chatroom, datetime.now())
    async def start(self) -> None:
        while not self.ws.closed:
            await self.poll_event()

    async def subscribe_to_chatroom(self, chatroom_id: int) -> None:
        await self.send_json(
            {
                "event": "pusher:subscribe",
                "data": {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"},
            }
        )

    async def unsubscribe_to_chatroom(self, chatroom_id: int) -> None:
        await self.send_json(
            {
                "event": "pusher:unsubscribe",
                "data": {"auth": "", "channel": f"chatrooms.{chatroom_id}.v2"},
            }
        )

    async def watch_channel(self, channel_id: int) -> None:
        await self.send_json(
            {
                "event": "pusher:subscribe",
                "data": {"auth": "", "channel": f"channel.{channel_id}"},
            }
        )

    async def unwatch_channel(self, channel_id: int) -> None:
        await self.send_json(
            {
                "event": "pusher:subscribe",
                "data": {"auth": "", "channel": f"channel.{channel_id}"},
            }
        )
