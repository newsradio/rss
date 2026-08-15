# NewsRadio 92.3 Full-Story RSS Feed

This project replaces the PolitePaul feed used by Futuri. It reads the station's
native Wix RSS feed, retrieves the complete body of each local news article, and
publishes a clean RSS 2.0 feed with no third-party branding.

## What Futuri receives

- Headline, publication date, author, category and permanent story link
- Lead image in both RSS `enclosure` and Media RSS formats
- Plain-text preview in `description`
- Entire formatted story in `content:encoded`
- A station-branded link back to the original story

## Futuri feed URL

Use this URL in Futuri for the **Pensacola News** feed:

`https://newsradio.github.io/rss/feed.xml`

In **Settings → Pages**, set **Source** to **Deploy from a branch**, choose
`main` and `/ (root)`, then click **Save**. This makes Futuri receive the feed
with the correct XML-compatible web headers. The feed refreshes automatically
through GitHub Actions.

The scheduled workflow checks for stories every 15 minutes. GitHub schedules can
occasionally run late, but no manual updating is normally needed.

## Local test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python generate_feed.py
```

Open `feed.xml` and search for a full article paragraph that does not appear in
Wix's truncated `description` field.
