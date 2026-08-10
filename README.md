# Childsafe Inbox

Childsafe Inbox converts teacher- and parent-shared web content into safer,
focused content that children can access without navigating the original
websites or platforms.

The project currently targets the practical flow:

```text
Teacher / WhatsApp
        |
        v
Parent Childsafe Inbox
        |
        v
URL resolver and content adapters
        |
        +-- YouTube --------> local video / Jellyfin
        +-- Wordwall -------> clean embed
        +-- native exercise -> isolated original application
        +-- document -------> document pipeline (planned)
        +-- unknown --------> review / unsupported
        |
        v
Child-facing safe content
Design principles
Do not expose children to unnecessary source-site navigation.
Preserve interactive applications when their JavaScript depends on the
original DOM.
Prefer clean provider embeds when available.
Use explicit adapter fingerprints rather than broad page scraping.
Fail closed when content cannot be identified safely.
Keep media acquisition separate from presentation.
Use the real teacher-shared URL corpus as the compatibility benchmark.
Render modes
embed

Used when the activity already has a clean provider URL, such as Wordwall or
a trusted standalone exercise.

source page
    -> adapter discovers provider URL
    -> Childsafe embeds only the activity
isolate

Used for interactive applications implemented directly inside the source page.

The original HTML, CSS and JavaScript remain intact. Childsafe visually isolates
the activity DOM root instead of extracting or moving it.

source page
    -> adapter identifies application fingerprint
    -> selector is returned
    -> renderer hides unrelated page content

This avoids breaking applications whose JavaScript was initialized against the
original DOM.

Current adapters

The current proof of concept includes support for:

YouTube
Wordwall embeds
Wordwall activities embedded in supported education sites
TestSaati Zombify quizzes
İlkokul Akademi native interactive exercises
İlkokul Akademi trusted GitHub Pages exercise embeds

Additional providers are added based on URLs observed in the real corpus.

Important files
app.py
    Childsafe Inbox web service

adapters.py
    URL matching, content resolution and adapter implementations

test-adapter
    Resolve and inspect a single URL

analyze-corpus
    Analyze a WhatsApp/chat URL corpus against all adapters

inspect-native-page
    Inspect DOM and JavaScript fingerprints of native exercises

classify-ilkokulakademi
    Discovery tool used while developing İlkokul Akademi support
Adapter result model

Adapters return a ResolvedContent object describing what was found.

Important fields include:

kind
provider
source_url
title
content_url
adapter
render_mode
selector

Typical native exercise:

kind        = native-exercise
provider    = ilkokulakademi-native
render_mode = isolate
selector    = #game-container

Typical provider exercise:

kind        = embed
provider    = wordwall
render_mode = embed
Testing a URL
cd /opt/childsafe-inbox

./test-adapter \
  'https://example.com/activity'
Corpus analysis

The corpus analyzer maintains a local cache under:

.cache/analyze-corpus.json

The cache is intentionally not committed.

Full analysis

Recheck every URL:

./analyze-corpus \
  --full \
  /home/humit/1-A-chat.txt

Use this periodically as the authoritative regression run.

Incremental analysis

During adapter development:

./analyze-corpus \
  --incremental \
  /home/humit/1-A-chat.txt

Incremental mode:

reuses cached successful results;
retries known-but-unresolved URLs;
retries previous errors;
detects when a new adapter claims a previously unsupported URL;
rechecks one known-good URL per adapter as a regression probe.
Focus on one domain
./analyze-corpus \
  --incremental \
  --domain ogretmeninihtiyaci.com \
  /home/humit/1-A-chat.txt

Bare and www hostnames are treated as the same domain for this option.

Reset the cache
./analyze-corpus \
  --reset-cache \
  /home/humit/1-A-chat.txt
Development workflow

A typical adapter-development cycle is:

1. Identify a high-frequency unresolved domain.
2. Inspect representative real URLs.
3. Find stable content/application fingerprints.
4. Implement a conservative adapter.
5. Test representative URLs with test-adapter.
6. Run incremental corpus analysis.
7. Verify one or more activities in the renderer.
8. Run a full corpus regression before a milestone/release.
Repository workflow

main contains the stable Childsafe Inbox and adapter work.

Experimental features should use focused branches, for example:

feature/clean-youtube

This allows content-adapter work and playback experiments to evolve
independently.

Current roadmap

Near-term areas include:

additional high-frequency educational sites;
generic document/PDF handling;
Instagram educational image/post extraction;
child-facing activity rendering;
clean YouTube playback;
parent-to-child content handoff and library management.
Security model

Childsafe is designed around content minimization rather than unrestricted web
access.

A resolved activity should expose only what is required for the child to use the
material. Unknown or unsupported content remains unresolved until a suitable
adapter or controlled fallback exists.

The Inbox service should remain restricted to trusted LAN/VPN access unless an
explicit authenticated public deployment is implemented.
