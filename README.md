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

## One-time GitHub setup

1. Create a **public** GitHub repository and upload every file in this folder.
2. Open **Settings → Pages**. Under **Build and deployment**, choose
   **Deploy from a branch**, then select `main` and `/ (root)`.
3. Open **Actions → Update RSS feed → Run workflow**.
4. Confirm this URL loads XML:
   `https://YOUR-USERNAME.github.io/YOUR-REPO/feed.xml`
5. In Futuri, edit **Pensacola News** and replace the PolitePaul URL with the
   new `feed.xml` URL.

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
