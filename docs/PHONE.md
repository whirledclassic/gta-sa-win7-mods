# GroveLink phone

## Keys

| Key | Action |
|-----|--------|
| **K** | Open / close. Cellphone animation on foot. |
| **Up / Down** | Move highlight |
| **Enter** | Select / call / snap / send reply |
| **Backspace** | Back one screen, hang up a live call, or close from Home |

## Screens

**Home** — Contacts, Messages, Camera, Close. Green highlight bar follows the cursor. Soft keys: SELECT / BACK.

**Contacts** — Sweet, Smoke, Ryder, Cesar, OG Loc, Kendl. Enter starts a real SCRIPT-SFX call (ring + voice + subtitles). The ON CALL screen stays up for the whole conversation.

**Messages** — Shows the last SMS from the browser. Enter opens CJ reply presets. A `* NEW TEXT *` line appears when a message is waiting.

**Reply** — On my way / Meet at Grove / Can't talk busy / Where you at? Those lines appear in the browser as CJ.

**Camera** — Enter takes a snapshot. Photos show on the browser PHOTOS tab if the bridge is running.

**Call** — Contact name + ON CALL. Backspace hangs up immediately. When the last voice line ends the phone returns to Contacts.

## Incoming text

If the bridge is running and someone sends a chat message, the phone beeps and shows **1 NEW TEXT**. A green dot sits on the header until you open Messages.

## Visuals

Dark handset on the right of the HUD:

- speaker grill
- green LCD
- signal bars + battery
- GROVELINK title
- home button
- SELECT / BACK labels

Missing labels almost always means `GroveLink.fxt` is not in `[GTA]\\CLEO\\`. Run **PATCH.bat**.

The player uses the stock SA cellphone animation (`0729`) on foot. Driving skips the hand anim so the camera does not fight the car.

## Bridge

Desktop **START_GROVELINK.bat** must stay open. It serves `index.html` on port 8088 and syncs `CLEO\\GroveLink\\link.ini` both ways.

Type in the browser → CJ sees a pager + Messages.  
Pick a reply in-game → the browser shows a CJ bubble.
