import re
import json
import argparse
from pathlib import Path

try:
    import yt_dlp
except ImportError:
    raise ImportError("Zainstaluj yt-dlp:  pip install yt-dlp")

SOUNDCLOUD_URL = "https://soundcloud.com/europeancentralbank"

PRESS_CONF_PATTERNS = [
    r"president lagarde presents",
    r"press conference",
    r"monetary policy decisions",
    r"governing council",
    r"draghi.*press",
    r"press.*conference",
]
PRESS_CONF_RE = re.compile("|".join(PRESS_CONF_PATTERNS), re.IGNORECASE)

SKIP_PATTERNS = [
    r"podcast",
    r"what's up with",
    r"how safe is",
    r"euro matters",
    r"interview",
    r"seminar",
    r"speech",
    r"lecture",
]
SKIP_RE = re.compile("|".join(SKIP_PATTERNS), re.IGNORECASE)


def fetch_channel_metadata(channel_url: str) -> list[dict]:
    """Pobiera metadane wszystkich nagrań z kanału SoundCloud."""
    print("Pobieranie metadanych kanału SoundCloud EBC...")
    ydl_opts = {
        "quiet":         True,
        "extract_flat":  True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)

    entries = info.get("entries", [])
    print(f"   Znaleziono łącznie: {len(entries)} nagrań na kanale")
    return entries


def filter_press_conferences(entries: list[dict]) -> list[dict]:
    """Wybiera tylko konferencje prasowe, pomija podcasty i inne materiały."""
    selected = []
    skipped  = []

    for e in entries:
        title = e.get("title", "")
        if SKIP_RE.search(title):
            skipped.append(title)
            continue
        if PRESS_CONF_RE.search(title):
            selected.append({
                "id":    e.get("id"),
                "title": title,
                "url":   e.get("url") or e.get("webpage_url", ""),
            })

    print(f"  Konferencje prasowe:    {len(selected)}")
    print(f"   Pominięte (inne treści): {len(skipped)}")
    return selected


def download_audio(
    tracks:     list[dict],
    output_dir: Path,
    dry_run:    bool = False,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"DRY RUN — lista {len(tracks)} konferencji:")
        for t in tracks:
            print(f"   {t['title']}")
        return

    print(f"Pobieranie {len(tracks)} konferencji do: {output_dir.resolve()}")

    ydl_opts = {
        "format":       "bestaudio/best",
        "outtmpl":      str(output_dir / "%(upload_date)s_%(title)s.%(ext)s"),
        "postprocessors": [{
            "key":              "FFmpegExtractAudio",
            "preferredcodec":   "wav",
            "preferredquality": "192",
        }],
        "quiet":        False,
        "no_warnings":  False,
        "writeinfojson": True,
        "sleep_interval": 1,
    }

    urls = [t["url"] for t in tracks]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download(urls)

    manifest = output_dir / "manifest.json"
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"Manifest: {manifest}")
    print(f"Pobrano {len(tracks)} konferencji do {output_dir.resolve()}")


def main():
    parser = argparse.ArgumentParser(
        description="Pobierz konferencje prasowe EBC z SoundCloud"
    )
    parser.add_argument(
        "--output", default="sample_data/",
        help="Folder docelowy (domyślnie: sample_data/)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Wyświetl listę bez pobierania",
    )
    parser.add_argument(
        "--channel", default=SOUNDCLOUD_URL,
        help="URL kanału SoundCloud",
    )
    args = parser.parse_args()

    entries = fetch_channel_metadata(args.channel)

    conferences = filter_press_conferences(entries)

    if not conferences:
        print("Nie znaleziono konferencji prasowych. Sprawdź wzorce filtrowania.")
        return

    download_audio(
        conferences,
        output_dir=Path(args.output),
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
