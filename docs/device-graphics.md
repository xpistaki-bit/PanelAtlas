# Device graphics in PanelAtlas

PanelAtlas draws every device true to scale. There are three ways to control how a device looks, from quick
to exact. They can be combined: the category sets the basic drawing, the designer refines it, and an image
replaces the drawing completely.

| Way | Effort | Result |
|---|---|---|
| 1. Category | none | generic drawing for the device type |
| 2. Designer | a minute per article | drawn front with the right actuator, symbol and print |
| 3. Image | find or take a photo | the real front of the device |

All three are set per catalog article under **Catalog → Edit**. A change applies to every configuration that
uses the article, including devices that are already placed and the PDF.

## 1. Category

The field **Type** decides the default drawing.

| Type | Drawing |
|---|---|
| MCB, RCBO, AFDD | black toggle lever, characteristic and rated current (for example B16) |
| RCD | blue lever, yellow test button, residual current and type |
| Switch | red lever, rated current |
| Switching device | grey lever, rated current |
| Surge protection | plug-in modules with a green indicator |
| Terminal block, main-line branch terminal | coloured block with screws |
| Meter | meter housing with display or register |

Width and height come from the fields **Width mm** and **Height mm** (1 module = 17.5 mm). The manufacturer
name is printed at the top of the device, the article number at the bottom.

## 2. Designer

For modular devices the section **Appearance (drawn front)** replaces the default details. A preview next to
the fields updates while you change them.

| Field | Options | Use |
|---|---|---|
| Actuator | default for the type, toggle lever, small slide switch, push button, rotary switch, none | the operating element on the front |
| Position | middle, left, right | where the actuator sits |
| Actuator colour | grey, black, white, red, blue, green, yellow, orange | |
| Circuit symbol | relay, contactor, time switch, bell, transformer, socket, lamp | printed symbol; sits beside a left or right actuator, below a centred one |
| Indicator LED | none, green, red, orange | small LED at the top right |
| Print line 1 / 2 | free text | for example `16 AX` and `250 V~` |
| Label window | on/off | the transparent labelling flap many devices have at the bottom |
| Show rated current large | on/off | the large `16 A` in the middle |

Choose **default for the type** as actuator to switch the designer off and return to the category drawing.

### Example: Hager EPN510 latching relay

The real device has a small slide switch on the left, the relay symbol on the right and a bluish label window.
The starter catalog already contains these settings:

| Field | Value |
|---|---|
| Actuator | small slide switch |
| Position | left |
| Actuator colour | white |
| Circuit symbol | relay / latching relay |
| Print line 1 | `16 AX` |
| Print line 2 | `250 V~` |
| Label window | on |
| Show rated current large | off |

## 3. Image

An image replaces the drawing. Upload a file in the section **Manufacturer image (front view)**, or paste an
image address and press **Load**. PNG, JPEG, WebP and GIF are accepted, up to 8 MB.

The image is stretched to the device's real width and height, so its proportions must match the front:

1. Use a straight front view. A perspective product photo (seen from the side) will look distorted.
2. Crop the image to the edges of the device, without margin or shadow.
3. Check the proportions: a one-module MCB is 17.5 mm wide and about 85 mm high, so the image should be about
   five times as high as it is wide.
4. If no front view is available, photograph the installed device straight on and crop it.

Manufacturer photos are protected by copyright. Use them for your own documentation, and do not add them to a
public repository.

To go back to the drawing, press **Remove image**.

## Marking placed devices

These settings belong to a placed device, not to the catalog article. They are in the **Device** tab of the
editor.

| Setting | Effect |
|---|---|
| Marker (signal colour) | bright frame in red, yellow, magenta or cyan, for devices that need attention |
| Label colour | background of the label field, twelve colours |
| Wires connected at the outgoing terminal | with two wires an orange `2×` marker appears on the breaker |

Markers, label colours and the `2×` marker appear in the view and in the PDF. Label colours are also used on
the label strips. The marker and the wire count are columns in the CSV export.
