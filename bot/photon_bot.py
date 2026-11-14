"""The Photon connection: receive texts and photos, reply with the device's record.

Run:   python -m bot.photon_bot           live, needs PHOTON_API_KEY and PHOTON_PROJECT_ID in .env
       python -m bot.photon_bot --local   test in the terminal, no keys needed

It checks Photon for new messages every couple of seconds. All the conversation logic is in
bot/chat.py; this file only moves messages in and out.
"""
import argparse
import datetime as dt
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from . import alerts, chat, replies  # noqa: E402  (after load_dotenv so the settings are visible)

POLL_SECONDS = 2
ALERT_SECONDS = 600                     # check the watch list for new recalls every 10 minutes
LOOK_BACK = dt.timedelta(seconds=60)    # listing is eventually consistent, so re-check the last minute


def utc(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class Bot:
    def __init__(self):
        from photon_api import Photon
        key, self.project = os.environ.get("PHOTON_API_KEY", ""), os.environ.get("PHOTON_PROJECT_ID", "")
        if not key or not self.project:
            sys.exit("Add PHOTON_API_KEY and PHOTON_PROJECT_ID to .env first (or use --local to test).")
        self.photon = Photon(headers={"Authorization": f"Bearer {key}"})
        self.seen: set[str] = set()
        self.started = dt.datetime.now(dt.timezone.utc)     # ignore everything sent before the bot started
        self.newest = self.started

    def new_messages(self) -> list[dict]:
        from photon_api.rpc_generated import ListMessagesInput
        page = self.photon.projects.list_messages(ListMessagesInput(
            path={"id": self.project},
            query={"direction": "received", "createdSince": utc(self.newest - LOOK_BACK),
                   "order": "asc", "orderBy": "created_at", "pageSize": 50}))
        fresh = []
        for item in page.items:
            m = item.model_dump(mode="json", by_alias=True, exclude_unset=True)
            created = dt.datetime.fromisoformat(m["createdAt"].replace("Z", "+00:00"))
            if m["id"] in self.seen or created < self.started:
                continue
            self.seen.add(m["id"])
            self.newest = max(self.newest, created)
            fresh.append(m)
        return fresh

    def send(self, space_id: str, sender_id: str, text: str, reply_to: str) -> None:
        from photon_api.rpc_generated import SendMessageInput
        self.photon.projects.send_message(SendMessageInput(
            path={"id": self.project},
            headers={"idempotency-key": f"reply-{reply_to}"},     # a retry never sends the reply twice
            body={"spaceId": space_id, "senderId": sender_id,
                  "content": {"type": "text", "format": "plain", "text": text}}))

    def photo(self, attachment_id: str) -> bytes:
        from photon_api.rpc_generated import DownloadAttachmentInput
        return self.photon.projects.download_attachment(DownloadAttachmentInput(
            path={"id": self.project, "attachmentId": attachment_id}))

    def answer(self, m: dict) -> None:
        content, agent = m.get("content", {}), m.get("receivedBy") or {}
        kind = content.get("type")
        if kind not in ("text", "attachment") or not agent.get("id"):
            return                                           # typing, read receipts and the like
        space_id = m["space"]["id"]
        contact = f"{space_id}|{agent['id']}"                # enough to text this person again later
        who = (m.get("sentBy") or {}).get("handle", "?")
        try:
            if kind == "text":
                print(f"<- {who[-4:]}: {content.get('text', '')[:80]}")
                reply = chat.handle(contact, text=content.get("text", ""))
            else:
                print(f"<- {who[-4:]}: [photo]")
                # Reading a label takes several seconds, so say so at once instead of going quiet.
                self.send_new(space_id, agent["id"], replies.READING_PHOTO, key=f"ack-{m['id']}")
                reply = chat.handle(contact, image=self.photo(content["attachmentId"]))
        except Exception as e:
            print(f"  error: {type(e).__name__}: {e}")
            reply = replies.ERROR
        self.send(space_id, agent["id"], reply, reply_to=m["id"])
        print(f"-> {reply[:80].replace(chr(10), ' ')}")

    def send_new(self, space_id: str, sender_id: str, text: str, key: str) -> None:
        """A message that is not a reply (an alert). `key` stops the same alert going out twice."""
        from photon_api.rpc_generated import SendMessageInput
        self.photon.projects.send_message(SendMessageInput(
            path={"id": self.project}, headers={"idempotency-key": key},
            body={"spaceId": space_id, "senderId": sender_id,
                  "content": {"type": "text", "format": "plain", "text": text}}))

    def run(self) -> None:
        print("Rap Sheet bot is running. Text the Photon number. Ctrl+C to stop.")
        last_alert_check = 0.0
        while True:
            try:
                for m in self.new_messages():
                    self.answer(m)
                if time.time() - last_alert_check > ALERT_SECONDS:
                    last_alert_check = time.time()
                    alerts.check(self.send_new)
            except KeyboardInterrupt:
                raise
            except Exception as e:                           # a network blip must not stop the bot
                print(f"  poll failed: {type(e).__name__}: {e}")
            time.sleep(POLL_SECONDS)


def local() -> None:
    """Type messages in the terminal. To test a photo, type:  photo path/to/label.jpg"""
    print("Local test. Type a device name, YES, MORE, SAVE gym AED, STOP. Ctrl+C to quit.")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if line.lower().startswith("photo "):
            with open(line[6:].strip().strip('"'), "rb") as f:
                print(chat.handle("local", image=f.read()), "\n")
        else:
            print(chat.handle("local", text=line), "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true", help="test in the terminal without Photon")
    if ap.parse_args().local:
        local()
    else:
        try:
            Bot().run()
        except KeyboardInterrupt:
            print("\nStopped.")
