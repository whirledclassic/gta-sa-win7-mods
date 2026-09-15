# GroveLink phone

## Keys

| Key | Action |
|-----|--------|
| **K** | Open / close. Cellphone animation on foot. |
| **Up / Down** | Move highlight |
| **Enter** | Select / call / snap / send reply |
| **Backspace** | Back one screen, or close from Home |

## Screens

**Home** — Contacts, Messages, Camera, Close

**Contacts** — Sweet, Smoke, Ryder, Cesar, OG Loc, Kendl. Enter starts a real SCRIPT-SFX call (ring + voice + subtitles).

**Messages** — Shows the last SMS from the browser. Enter opens CJ reply presets.

**Reply** — On my way / Meet at Grove / Can't talk busy / Where you at? Those lines appear in the browser as CJ.

**Camera** — Enter takes a snapshot. Photos show on the browser PHOTOS tab if the bridge is running.

**Call** — In-call label. Backspace hangs up when the line ends.

## Incoming text

If the bridge is running and someone sends a chat message, the phone beeps and shows **1 NEW TEXT**. A green dot sits on the header until you open Messages.

## Visuals

The HUD is a dark handset on the right: speaker grill, LCD, signal bars, home button, green title. Missing labels almost always means `GroveLink.fxt` is not in `[GTA]\CLEO\`.

## Bridge

`grovelink\bridge\START_GROVELINK.bat` must stay open. It serves `index.html` on port 8088 and syncs `CLEO\GroveLink\link.ini` both ways.
