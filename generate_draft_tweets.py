#!/usr/bin/env python3
"""
generate_draft_tweets.py

Fetches trending headlines from Google News RSS and writes a batch of ready-to-copy
draft tweets to draft_output.md. Does NOT post anything anywhere - purely generates
content for you to review and post yourself.

Keeps track of already-drafted stories in seen_ids.json so it never repeats one.

Optional environment variables:
  NEWS_TOPIC       - a search term, e.g. "technology". If unset, uses general top stories.
  NEWS_COUNTRY     - 2-letter country code for the feed, default "US"
  NEWS_LANG        - language code, default "en"
  NUM_DRAFTS       - how many draft tweets to generate per run, default 3
"""

import os
import json
import hashlib
from datetime import date
from pathlib import Path

import feedparser

HERE = Path(__file__).parent
STATE_FILE = HERE / "seen_ids.json"
OUTPUT_FILE = HERE / "draft_output.md"


def load_seen_ids() -> set:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_seen_ids(ids: set) -> None:
    trimmed = list(ids)[-500:]  # keep the file from growing forever
    STATE_FILE.write_text(json.dumps(trimmed, indent=2))


def build_feed_url() -> str:
    # GitHub Actions passes unset repo variables through as an empty string,
    # not as a missing key - so fall back to defaults on empty too.
    lang = os.environ.get("NEWS_LANG", "").strip() or "en"
    country = os.environ.get("NEWS_COUNTRY", "").strip() or "US"
    topic = os.environ.get("NEWS_TOPIC", "").strip()

    if topic:
        query = topic.replace(" ", "+")
        return (
            f"https://news.google.com/rss/search?q={query}"
            f"&hl={lang}-{country}&gl={country}&ceid={country}:{lang}"
        )
    return f"https://news.google.com/rss?hl={lang}-{country}&gl={country}&ceid={country}:{lang}"


def entry_id(entry) -> str:
    raw = getattr(entry, "id", None) or entry.link
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def format_tweet(title: str, link: str) -> str:
    max_title_len = 280 - 24  # reserve room for the link (X shortens links to 23 chars) + space
    if len(title) > max_title_len:
        title = title[: max_title_len - 1].rstrip() + "…"
    return f"{title} {link}"


def pick_new_stories(seen_ids: set, count: int):
    feed = feedparser.parse(build_feed_url())
    picked = []
    for entry in feed.entries:
        eid = entry_id(entry)
        if eid in seen_ids:
            continue
        picked.append((entry, eid))
        if len(picked) >= count:
            break
    return picked


def main():
    num_drafts_raw = os.environ.get("NUM_DRAFTS", "").strip()
    num_drafts = int(num_drafts_raw) if num_drafts_raw else 3
    seen_ids = load_seen_ids()
    picked = pick_new_stories(seen_ids, num_drafts)

    if not picked:
        OUTPUT_FILE.write_text(
            f"## Draft tweets for {date.today().isoformat()}\n\n"
            "No new trending stories found this run.\n"
        )
        print("No new stories to draft.")
        return

    lines = [f"## Draft tweets for {date.today().isoformat()}\n"]
    for entry, _ in picked:
        tweet = format_tweet(entry.title, entry.link)
        lines.append(f"- [ ] {tweet}")
    lines.append("\nCopy any of these you like and post them on X yourself.")
    OUTPUT_FILE.write_text("\n".join(lines) + "\n")

    for _, eid in picked:
        seen_ids.add(eid)
    save_seen_ids(seen_ids)

    print(f"Wrote {len(picked)} draft tweet(s) to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
