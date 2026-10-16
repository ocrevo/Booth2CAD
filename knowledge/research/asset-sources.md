# 3D asset and PBR material sources for booth renders (Blender)

> **Unreviewed reference notes.** Collected from public sources on the access date given below and not reviewed by a booth designer. They are not defaults of the tool, not facts about any client project and not legal advice; check the linked source before relying on a value.

- Purpose: choose model and material sources for exhibition-stand renders made in Blender that are **delivered to paying clients**.
- Access date for every URL below: **2026-10-14**, unless a row says otherwise.
- Method: official licence and terms pages first, then official docs and API listings. Third-party or forum sources are marked as such. Nothing was downloaded.
- Not legal advice. Before relying on any row for a large job, re-read the linked licence. Get written confirmation wherever a row says "unclear".

## 1. Key findings

1. **CC0 sources cover most soft furnishings and surfaces.** Poly Haven and ambientCG are CC0: commercial use, no credit, and no redistribution limits on the assets. Poly Haven also publishes real-world dimensions per asset.
2. **Build the booth-specific items in-house.** No CC0 source has good modern truss, LED walls, flat TVs, track spots, lightbox frames or counters. These are simple parametric shapes, and they fit the existing `booth-image-to-model` primitives.
3. **Royalty-free marketplaces allow renders but not handing over files.** This covers Blendkit, Fab, CGTrader and TurboSquid. All allow commercial renders. None lets you pass the model files on as standalone files. Delivering `.blend` source files to a client is the main licence trap.
4. **Avoid CC BY in client-facing renders.** A render is arguably "Adapted Material", so the credit must travel with it, and clients rarely keep credits. Never use NC, ND or SA.
5. **Manufacturer data is for planning, not marketing images.** This covers Vitra, MillerKnoll, HAY, BIMobject and IKEA. Their terms are restrictive or silent about commercial renders. Use their data only when the client specifies that genuine product, and get written permission.
6. **Use "front faces −Y", not "+Y forward".** Blender's Front view, the glTF importer and Blendkit's upload rules all put an asset's front on −Y. The brief's "+Y forward" matches Blender's axis-conversion wording ("Y Forward"), but read literally it would flip every asset. Write the rule as "front face points to −Y".
7. **Things changed in 2025–2026.**
   - BlenderKit is now **Blendkit** (blendkit.com, operating under the new name since 23 June 2026).
   - Megascans moved to Fab with paid tiers (from 2025).
   - The Sketchfab Store has been replaced by Fab. CC0, SA, NC and ND models cannot migrate to Fab.
   - Blender **5.2 LTS** (14 July 2026) added remote asset libraries, a dedicated Asset Libraries preferences page and a per-asset preferred import method.

## 2. Licence comparison

Legend: **Y** = allowed, **N** = not allowed, **?** = unclear or not stated.

| Source | Licence | Commercial client renders? | Redistribution limits | Attribution? | Typical formats | Real-world scale reliability | URL |
|---|---|---|---|---|---|---|---|
| **Poly Haven** | CC0 1.0 ("Our assets are all licensed as CC0") | **Y** | None for assets. Logos, renders and site text are excluded. The live API needs a unique User-Agent and a credit to Poly Haven *for the API service* | No | Models: .blend, glTF, FBX, USD, with 1k–8k textures. Textures: 1k–8k | **High.** The API `dimensions` field is apparently in mm (armchair 820×987×1023; plank floors 2000×2000) | polyhaven.com/license; polyhaven.com/our-api |
| **ambientCG** | CC0 1.0 | **Y** ("even for commercial purposes") | None | No (appreciated) | Materials: JPG/PNG 1K–8K. Few models | **Medium.** `dimensionsData` is often 0 (unknown). When set it appears to be cm (WoodFloor051 = 180). Set tile size yourself | docs.ambientcg.com/license/ |
| **Blender official** | Essentials library: CC0. Demo files and bundles: per file (CC0, CC-BY, CC-BY-SA, some unlabelled) | Essentials and CC0 bundles: **Y**. Others: per file | CC-BY-SA forces share-alike on adaptations. Avoid unlabelled files | CC-BY: yes | .blend asset bundles (with catalogue file) | Not a furniture source. Human Base Meshes (CC0) are useful as a 1:1 scale reference | blender.org/download/demo-files/; projects.blender.org/blender/blender-assets |
| **Blendkit** (formerly BlenderKit) | Per asset: **Royalty Free** or **CC0**. The licence does not depend on the Free or Full plan (T&C Art. 2.4) and lasts "for the duration of the author's property rights" (Art. 5.3) | **Y** ("Everything you download is available for commercial use") | RF "doesn't allow for re-sale of the asset in the same form". No distribution to third parties "other than as part of your project", and the product must be secured so it can't be separated (Art. 5.4) | RF: no | .blend via add-on | **Medium-high.** Upload rules require 1 BU = 1 m, front facing −Y and scale applied. Still user-uploaded, so verify | blendkit.com/docs/licenses/; blendkit.com/terms-and-conditions-2021/ |
| **Fab** (Epic), incl. **Quixel Megascans** | Fab **Standard License**: Personal tier if gross revenue ≤ US$100k in the last 12 months, Professional tier above that. Some listings are **CC-BY 4.0**. Legacy UE Marketplace licence is being phased out | **Y** per Epic's summary: commercial use "with any compatible tools", not only Unreal | No standalone resale or free redistribution. Sharing with collaborators on the same project is OK. Assets tagged NoAI must not be used for generative-AI data collection | Standard: no. CC-BY: yes | FBX/OBJ/glTF; Megascans surfaces and scans | **High** for Megascans scans. Other sellers vary | dev.epicgames.com/documentation/en-us/fab/licenses-and-pricing-in-fab; fab.com/eula (**403 to automated fetch; read the binding EULA manually**) |
| **Sketchfab** (free downloads) | Per model: CC0, CC BY, CC BY-SA, CC BY-ND, CC BY-NC (+SA/ND). The Store (Standard/Editorial) has been replaced by Fab | CC0 and CC BY: **Y**. BY-SA/BY-ND: Y with conditions. **NC: N** | CC terms. ND bans edits; SA forces share-alike | CC BY: yes. You must name the creator, link the licence and "indicate if changes were made" | Auto-converted glTF/GLB/USDZ, plus the original upload when the creator allows it (website only; the API serves only glTF/GLB/USDZ) | **Low.** User uploads with arbitrary units | sketchfab.com/licenses; help.sketchfab.com/en/articles/16152669-gltf-glb-and-usdz |
| **CGTrader** | **Royalty Free** (standard, or "No AI" variant) / **Editorial** | RF: **Y** as an "Incorporated Product", rendered stills included. No stock-clearinghouse imagery. **Editorial: N** | Not to be sold or given away in downloaded form. Sharing within the buyer entity is OK | No | .max, FBX, OBJ, sometimes .blend | **Varies by seller** | cgtrader.com/pages/terms-and-conditions |
| **TurboSquid** | **Royalty Free** (effective from 3 Feb 2020) / **Editorial** | RF: **Y** (ads, print, web). No stock clearinghouses. Editorial items "may not be used as part of billboard, trade show or exhibit display" | Model files must stay non-extractable inside a larger creation. "Each entity that is making a Creation… must Purchase its own license" | Generally no | .max, FBX, OBJ, C4D | CheckMate Pro requires real-world scale. Other models vary | blog.turbosquid.com/royalty-free-license/ |
| **Vitra** (manufacturer) | Product CAD data: "2D & 3D CAD Data" downloads. OFML (via pCon) only for registered dealers and architects. pCon.planner ME (free) exports 3ds/SKP/DXF/SAT | **?** No public licence covers marketing renders. Intended for planning | ? (assume no redistribution) | ? | DWG, 3DS, SKP, OFML | Dimensions are accurate. Mesh and material quality is planning-grade | vitra.com/en-us/professionals/downloads (403 to fetch); vcs.vitra.com |
| **Herman Miller / MillerKnoll** | Downloadable .rfa, .skp and .dwg. Site Terms of Use: "personal, non-commercial use only" and must not "Modify copies" | **? / N** without written permission (legal_inbox@millerknoll.com) | No commercial use of site content | Keep notices | RFA, SKP, DWG | Dimensions are accurate. Planning-grade geometry | hermanmiller.com/resources/3d-models-and-planning-tools/; millerknoll.com/legal/terms-of-use/ |
| **HAY** | Via pCon.catalog and plug-ins for AutoCAD, SketchUp and Revit. No licence text on the planning page | **?** | ? | ? | pCon/OFML, DWG, SKP, RFA | Planning-grade | hay.com/professionals/planning |
| **IKEA** | No official public 3D licence. The site's GLBs can only be pulled with unofficial scripts. The official research dataset is CC BY-NC-SA 4.0 | **N** | — | — | GLB (unofficial) | Good dimensions, but not licensable | github.com/IKEA/IKEA3DAssemblyDataset |
| **BIMobject** | Terms of service (page shows a 24 Jun 2025 version). Objects are for personal non-commercial use. Building professionals may put them in "any drawing, material(s) or project documents" for projects they advise on. **No AI training** | **?** Marketing renders are not clearly covered | No distribution, sublicensing or transfer | Keep proprietary notices | RFA, DWG, IFC, SKP, 3DS (per manufacturer) | Manufacturer dimensions. Low visual quality | business.bimobject.com/terms-of-service-eula |
| **3D Warehouse** (Trimble) | General Model License (last updated 18 Mar 2015; Terms of Use 1 Apr 2017) | **Y** as a "Combined Work" with "substantial additional content". The FAQ allows work-for-hire deliverables | No standalone sale or distribution, no aggregation. Uploaders give **no IP warranty** | Not required, but keep notices | SKP (needs conversion for Blender) | **Low-medium.** User uploads, often modelled in inches | 3dwarehouse.sketchup.com/tos/; help.sketchup.com/3d-warehouse/3d-warehouse-terms-use-faq |

Notes on the table:

- **Megascans.**
  - Claiming legacy Quixel assets ended on 31 Dec 2024. Claimed assets stay usable.
  - Paid pricing on Fab started in 2025. A free starter set of more than 1,500 assets was announced.
  - Current 2026 prices could not be confirmed from Epic sources.
- **Blendkit terms.**
  - The user Terms & Conditions found are the 2021 version. The June 2026 rename notice mentions no licence change.
  - Pricing reported by CG Channel for small studios (under US$100k revenue) rose from US$14.90/month in Sep 2025 to US$17.90/month in Jan 2026.
- **AI/ML clauses matter for this repo's AI comparison workflow.**
  - BIMobject bans AI training.
  - TurboSquid bans ML/AI use of imagery without written authorisation.
  - CGTrader free downloads and "No AI" licences ban ML training.
  - Fab NoAI-tagged assets are excluded from generative-AI data collection.
  - Only CC0 assets are safe for building any dataset.

## 3. Recommended starter set (about 30 asset types)

Priority order:

1. **CC0 from Poly Haven or ambientCG.**
2. **In-house parametric or procedural builds** (also CC0-equivalent, because the studio owns them).
3. **Blendkit RF/CC0** for gaps.
4. **Fab Standard or CGTrader/TurboSquid RF** only for hero pieces. Render-only; never hand over these files.

Poly Haven IDs below come from the live API listing. Check style and dimensions before you approve each one.

### Models

| # | Asset type | Source (first choice → fallback) | Notes |
|---|---|---|---|
| 1 | Bar stool, round metal | Poly Haven `bar_chair_round_01`, `metal_stool_01/02/03` → Blendkit | Seat height 650–800 mm |
| 2 | Side / visitor chair | Poly Haven `dining_chair_02`, `plastic_monobloc_chair_01` → Blendkit | Generic designs only |
| 3 | Lounge armchair | Poly Haven `modern_arm_chair_01`, `ArmChair_01` → Blendkit | Check `mid_century_lounge_chair` for resemblance to the Eames Lounge before using it (see §6) |
| 4 | Sofa (2–3 seat) | Poly Haven `sofa_02`, `sofa_03`, `Sofa_01` | Re-texture with the booth fabrics (M8) |
| 5 | Ottoman / pouf | Poly Haven `Ottoman_01` | |
| 6 | Coffee table | Poly Haven `modern_coffee_table_01/02`, `coffee_table_round_01` | |
| 7 | Side table | Poly Haven `side_table_01`, `side_table_tall_01` | |
| 8 | Bistro / high table (Ø600–700, H 1100 mm) | **In-house parametric** (disc top + column + base) | Needed on almost every booth |
| 9 | Meeting table | **In-house parametric** → Poly Haven `round_wooden_table_01`, `dining_table` | |
| 10 | Shelving / product display | Poly Haven `steel_frame_shelves_01..03`, `wooden_display_shelves_01` → in-house | |
| 11 | Reception / info counter | **In-house** (existing `box` / `profile_extrusion` recipes) | Client-specific every time |
| 12 | Plinth / product podium | **In-house** | |
| 13 | Brochure stand | **In-house** → Blendkit | |
| 14 | Potted plant, small/medium | Poly Haven `potted_plant_01/02/04` | Weathered pots: re-material them |
| 15 | Floor plant, large (ficus, olive, monstera) | Blendkit (CC0/RF) → Fab | Poly Haven has no large indoor plants |
| 16 | Vases / books / frames | Poly Haven `ceramic_vase_01..04`, `decorative_book_set_01`, `standing_picture_frame_01` | |
| 17 | Pendant light | Poly Haven `modern_ceiling_lamp_01`, `hanging_industrial_lamp` | |
| 18 | Track spotlight / truss spot | **In-house** (housing + Spot light, optional IES) | No CC0 source found |
| 19 | Truss, square and triangular, 290 mm | **In-house parametric** (generic, no brand names) | Lengths 0.5, 1, 2, 3 m, plus corners |
| 20 | Flat TV / monitor on stand or wall mount | **In-house parametric** (43/55/65/75/86″, 16:9, emissive screen UV 0–1) | Poly Haven TVs are retro |
| 21 | LED wall | **In-house parametric** (500×500 / 500×1000 mm cabinets, emissive) | |
| 22 | Fabric lightbox (SEG frame) | **In-house parametric** + M5 material | |
| 23 | Laptop / tablet props | Blendkit | Remove any brand logos |
| 24 | Coffee machine / bar back props | Blendkit → Poly Haven `CoffeeCart_01` | |
| 25 | Human scale figure | Blender Human Base Meshes (CC0) | Scale check only; not for final renders |

### Materials

| # | Material | Source | Notes |
|---|---|---|---|
| M1 | Wood floor (plank, herringbone) | Poly Haven `laminate_floor*`, `plank_flooring*`, `herringbone_parquet` (real size in mm) → ambientCG `WoodFloor0xx` | Map with the real tile size |
| M2 | Exhibition carpet (needle-punch / velour) | **In-house procedural** (fine noise bump, colour variants) → ambientCG `Carpet0xx` | Poly Haven only has `dirty_carpet` |
| M3 | Lacquer / painted MDF (gloss, satin, matt) | **In-house procedural** (Principled + Coat) | No textures needed |
| M4 | Acrylic (clear, opal, coloured) | **In-house procedural** (transmission) | |
| M5 | Fabric lightbox (backlit SEG print) | **In-house** (translucent + emission, print image slot) | |
| M6 | Brushed aluminium / stainless | ambientCG `Metal009–012`, `Metal051A–C` → procedural anisotropic | |
| M7 | Glass (clear, frosted, low-iron edge) | **In-house procedural** | |
| M8 | Upholstery | Poly Haven `velour_velvet`, `wool_boucle`, `poly_wool_herringbone`, `rough_linen`, `leather_white` | Real size in mm via API |
| M9 | HPL / laminate white, oak veneer | Poly Haven wood textures, ambientCG `Wood0xx` | |
| M10 | Hall concrete floor (outside the booth) | Poly Haven concrete | |
| M11 | Matt wall paint, chrome, matte plastic | **In-house procedural** | |

## 4. Library layout and naming

### Folder layout

```
<library>/StudioLibrary/             <- registered in Preferences > Asset Libraries (5.2: its own page)
  blender_assets.cats.txt            <- catalogue definitions (UUID:path:simple name)
  manifest.csv                       <- one row per asset (generated by script)
  _incoming/                         <- quarantine for raw downloads; NOT registered as a library
    2026-10-14_polyhaven_modern_arm_chair_01/   (untouched archive + licence snapshot)
  _licences/                         <- dated PDF/HTML snapshots of each source's licence page
    polyhaven_2026-10-14.pdf
    blendkit-terms-2021_2026-10-14.pdf
  models/
    seat/
      seat-barstool_round-metal-01_400x400x770mm/
        seat-barstool_round-metal-01_400x400x770mm.blend
        asset.json                   <- sidecar metadata (see below)
        preview.png
        textures/
    table/  counter/  display/  screen/  light/  truss/  plant/  decor/  ref/
  materials/
    floor/  carpet/  wood/  metal/  glass/  acrylic/  lacquer/  lightbox/  fabric/
  nodegroups/                        <- procedural generators (truss, LED wall, TV, lightbox)
```

### Catalogues

Use paths like these (use `/` as separator; `:` and `\` are not allowed):

- `Booth/Seating/Bar Stool`
- `Booth/Tables/High Table`
- `Booth/Display/Screen`
- `Booth/Structure/Truss`
- `Booth/Lighting/Spot`
- `Booth/Greenery/Plant`
- `Materials/Floor/Carpet`

Catalogues are identified by UUID, so they can be renamed without editing the asset files. Keep `blender_assets.cats.txt` in git, or back it up.

### Naming

- Pattern: `<category>-<subtype>_<descriptor>-<variant>_<W>x<D>x<H>mm`, in lowercase ASCII.
- Use `_` between fields and `-` inside a field.
- Use `x`, not `×`, so names are safe on every file system and in scripts.
- W is along X, D along Y and H along Z. Measure the world bounding box after applying transforms and round to the nearest mm. Example: `seat-barstool_round-metal-01_400x400x770mm`.
- Category vocabulary: `seat, table, counter, display, screen, light, truss, plant, decor, structure, ref`.
- Materials: `mat_<family>_<descriptor>_<finish>`, for example `mat_carpet_needlepunch_anthracite` or `mat_metal_alu-brushed_satin`. Store the real tile size as a custom property, `tile_mm = [2000, 2000]`.
- The object, mesh, collection, folder and `.blend` all share the asset name. This lets a script round-trip between them.

### Geometry contract (validated by script before an asset is marked)

- **Units:** metres, 1 BU = 1 m. Scale = 1 and rotation = 0 are applied, on child objects too.
- **Origin:** at the **base centre** (bounding-box XY centre, lowest Z = 0). Wall-mounted items (TV mount, wall lamp) use the back-centre of the mounting face, and their local +Z points away from the wall, as in Blendkit's convention.
- **Front:** faces **−Y**, so it is visible in Front view (Numpad 1). Blendkit's upload rules use the same convention, and so does what the glTF importer produces (glTF front is +Z, which maps to Blender −Y).
- **Z up**, and the asset sits on the ground (no floating).
- One top-level collection per model. Mark the collection as the asset, so it can be instanced.
- **Pipeline note:** `booth-image-to-model` places primitives at their *local geometric centre* (data-contract.md). When the builder places a library asset, add `H/2` to the spec's Z, or set the spec placement to the floor point.

### Metadata

Use Blender's asset fields plus a sidecar file:

- **Blender asset fields:**
  - `license`: SPDX ID, e.g. `CC0-1.0`, `CC-BY-4.0`, `LicenseRef-Blendkit-RF`, `LicenseRef-Fab-Standard`, `LicenseRef-TurboSquid-RF`, `LicenseRef-InHouse`
  - `author`
  - `copyright`
  - `description` (include the source URL)
  - `tags`: category, style, colour, `src:polyhaven`, `lic:cc0`
  - catalogue
- **Custom properties and `asset.json` sidecar:**
  - `source`, `source_id`, `source_url`, `retrieved` (date), `licence_snapshot` (path in `_licences/`)
  - `attribution_text` (empty for CC0)
  - `redistribution` (`source_ok` | `render_only`)
  - `brand_design` (`generic` | `branded:<maker model>`)
  - `dims_mm` (W, D, H)
  - `expected_dims_mm` (from the source or a spec sheet)
  - `polycount`, `sha256` (of the original archive)
  - `reviewed_by` and `review_date`
- **`manifest.csv`** is generated from the sidecars. The pipeline filters on `redistribution` and `licence` before writing any client deliverable.

## 5. Practical Blender notes (Blender 5.2 LTS)

### Importing at metre scale

- **glTF/GLB.**
  - The glTF spec is metres, +Y up, front = +Z. Blender's importer converts this to Z up, so the front lands on **−Y** with no fixes needed.
  - The "+Y Up" option is an *export* setting.
  - Use **Merge Vertices** for split meshes, and set **Shading** to control normals.
- **FBX.**
  - Since 4.5 there is a C++ (ufbx) importer. A third-party guide says it is the default in 5.x; the 5.x manual lists a separate "FBX (Legacy)" page.
  - The new importer **dropped Manual Orientation and Forward/Up Axis**, because the file specifies its own axes. Only a global **Scale** remains.
  - Files from 3ds Max are usually in cm, and Design Connected states "Files units are centimeters". Always check dimensions after import, and look for factors of 0.01, 100, 0.0254 or 39.37.
- **OBJ.**
  - OBJ is unitless. Set **Scale** yourself (0.01 for cm, 0.001 for mm, 0.0254 for inches).
  - The axes default to a Y-up source ("-Z Forward, Y Up").
  - Enable **Validate Meshes**.
- **Automated normalisation script.** Run it on every import:
  1. Apply all transforms.
  2. Compute world-bbox W×D×H.
  3. Compare against the expected dimensions (Poly Haven `dimensions` from the API, mm; the manufacturer spec sheet; or the category plausibility ranges below). Reject if the ratio is outside 0.9–1.1.
  4. Set the origin to the base centre and rotate so the front faces −Y.
  5. Rename the asset, then `asset_mark()` and `asset_generate_preview()`.
  6. Write `asset_data.license`, `author`, `copyright`, `description`, tags and `catalog_id`.
- **Category plausibility ranges (mm):**

  | Item | Range |
  |---|---|
  | Chair seat height | 420–480 |
  | Bar stool seat height | 650–800 |
  | Dining/meeting table height | 720–760 |
  | High table height | 1050–1150 |
  | Counter height | 900–1100 |
  | Sofa seat height | 380–450 |
  | Door height | ≥ 2000 |

### Asset library setup

- **Register the library.** In Preferences > **Asset Libraries** (its own page since 5.2), add `StudioLibrary` with a fixed path: a mapped drive letter or UNC path that is identical on every workstation and render node.
- **Mark assets.** Assets must be marked inside `.blend` files under the library folder.
- **Catalogues.** They live in `blender_assets.cats.txt` at the library root. Blender writes a `~` backup when it changes.
- **Metadata editing.** The Asset Details fields (Name, Source, License, Copyright, Description, Author, Tags, Preview) can only be edited for assets in the current file. Do metadata edits by script inside each asset `.blend`.
- **Remote libraries (optional).** Blender 5.2 can register **remote asset libraries**, which a static web server can host using an OpenAPI listing. This needs "Allow Internet Access". It is an option for a later studio-wide library server; keep the local library authoritative.

### Linking vs appending

- **Link.** Read-only, and source changes reach every file. Use it for stable, high-count models (chairs, stools, plants).
  - Enable "Instance Collections" so each placement is one empty.
  - Use library overrides only when one instance needs different settings.
  - Linking keeps scene files small, but the library path must resolve at render time.
- **Append / Append (Reuse Data).** Copies the asset into the file. Reuse Data avoids duplicate materials. Use it for materials and for anything recoloured per project. Make it the library default.
- **Pack** (link, then pack into the file). Gives a self-contained file for archiving or farm submission. **Do not send packed files to clients** if they contain non-CC0 assets (see §6).
- **Per-asset preferred import method (5.2).** Set it to Link for models and Append (Reuse Data) for materials. Then the browser's "Follow Asset or Preferences" setting does the right thing.

### Hygiene

- Open downloaded `.blend` files with **Auto Run Python Scripts** turned off.
- Keep raw downloads in `_incoming/` until they have been reviewed.

## 6. Risks and mitigations

| Risk | Detail | Mitigation |
|---|---|---|
| **Licence or terms change** | Recent examples: Blendkit renamed (Jun 2026; its user terms are dated 2021); Megascans moved to paid Fab tiers (2025); Sketchfab free CC library shrinking (the Store has moved to Fab; CC0/SA/NC/ND cannot migrate). The binding Fab EULA was not readable automatically | Save a dated licence snapshot in `_licences/` at acquisition. Store the licence ID per asset. CC0 grants are irrevocable for copies you hold. RF licences follow the terms in force at acquisition, so keep the receipts |
| **Handing source files to clients** | Blendkit (Art. 5.4), Fab, CGTrader and TurboSquid forbid passing on model files outside the project. TurboSquid says each entity making a Creation "must Purchase its own license". Manufacturer data is planning-only | Deliver renders. If a contract demands `.blend` or `.fbx` handover, filter `redistribution=source_ok` (CC0 and in-house only) and replace or strip everything else automatically |
| **CC BY attribution in client renders** | A render is arguably "Adapted Material". Credit can be given "in any reasonable manner based on the medium", but clients publishing renders won't carry it | Keep CC BY out of client-facing renders. If one is unavoidable, add a credits line to the delivery note and the image metadata. Never use NC, ND or SA |
| **Scale errors** | OBJ is unitless; FBX cm/inch mix-ups; Sketchfab and 3D Warehouse uploads have arbitrary scale; ambientCG size metadata is often missing | Run the import-normalisation script with dimension checks and plausibility ranges. Use the human base mesh as a visual check. Store `expected_dims_mm` |
| **Brand, trademark and design rights (Eames, Panton, Barcelona, USM…)** | CC0 does not waive trademark or patent rights (§4.1), and CC BY 4.0 does not license them (§2(b)(2)). **EU:** after CJEU *Mio/konektra* (4 Dec 2025), applied art needs no higher threshold for copyright; BGH (2 Jul 2026, I ZR 96/22) overturned the ruling that denied USM Haller protection. **US:** Herman Miller's Eames trade dress infringement verdict was upheld (9th Cir. 2020). Marketplace designer replicas are often "Editorial use only", and TurboSquid editorial items are barred from "trade show or exhibit display" | Default library = **generic designs only** (`brand_design=generic`). Use a branded designer piece only when the client specifies the genuine product to be supplied, sourced from the manufacturer or a licensed model, with written permission. Never label a generic piece with a brand or designer name. Review CC0 "mid-century" pieces for close resemblance |
| **Visible third-party logos** | TVs, laptops and coffee machines often carry brand logos | Strip logos when ingesting assets. Use only client-supplied branding |
| **Manufacturer terms** | MillerKnoll's site terms say "personal, non-commercial use only". BIMobject allows professional use in project documents, but marketing renders are unclear, and AI training is banned. IKEA has no licence | Treat as **planning data only** unless there is written permission |
| **AI/ML use** | BIMobject, TurboSquid, CGTrader (free / No AI) and Fab NoAI all restrict ML or AI use | Only CC0 and in-house assets may feed training sets or AI datasets. Comparing renders with a vision model is not training, but log which assets appear in any image you share with a third-party AI service |
| **Poly Haven API terms** | The live API needs a unique User-Agent and a credit to Poly Haven for the API service | Prefer a one-off manual or scripted ingest with a proper User-Agent. Credit Poly Haven in internal tooling if it calls the API live |
| **Malicious or heavy downloads** | `.blend` files can carry auto-run Python. Some files are huge | Quarantine in `_incoming/`. Keep auto-run off. Check poly count and texture budget before marking an asset |

## 7. Sources (all accessed 2026-10-14)

### Licences

- Poly Haven: https://polyhaven.com/license · API terms https://polyhaven.com/our-api · API listings https://api.polyhaven.com/assets?type=models&categories=furniture (also `plants`, `lighting`, `electronics`, `decorative`, textures `floor,wood` and `fabric`) · asset info https://api.polyhaven.com/info/modern_arm_chair_01
- ambientCG: https://docs.ambientcg.com/license/ · API https://docs.ambientcg.com/api/v2/full_json/
- Blendkit:
  - https://www.blendkit.com/docs/licenses/
  - https://www.blendkit.com/faq-frequently-asked-questions/
  - https://www.blendkit.com/terms-and-conditions-2021/
  - https://www.blendkit.com/docs/upload/
  - Rename notice: https://www.blendkit.com/articles/goodbye-blenderkit-hello-blendkit/
- Fab / Epic:
  - https://dev.epicgames.com/documentation/en-us/fab/licenses-and-pricing-in-fab
  - https://www.fab.com/eula (not fetchable)
  - Forum (tiers): https://forums.unrealengine.com/t/fab-license/2693908
  - Legacy Megascans: https://forums.unrealengine.com/t/access-legacy-megascans-on-bridge-and-quixel-com/2142664
  - Third-party summary: https://www.cgchannel.com/2024/10/epic-games-has-made-megascans-free-to-all-but-only-until-the-end-of-2024/
- Sketchfab:
  - https://sketchfab.com/licenses
  - https://sketchfab.com/blogs/community/refine-downloadable-model-searches-with-new-license-filters
  - https://sketchfab.com/blogs/community/sketchfab-update-what-you-need-to-know-now-that-fabs-live/
  - https://help.sketchfab.com/en/articles/16152669-gltf-glb-and-usdz
- Creative Commons:
  - CC BY 4.0 legal code https://creativecommons.org/licenses/by/4.0/legalcode.en
  - CC0 legal code https://creativecommons.org/publicdomain/zero/1.0/legalcode.en
- CGTrader: https://www.cgtrader.com/pages/terms-and-conditions
- TurboSquid: https://blog.turbosquid.com/royalty-free-license/ · CheckMate Pro https://resources.turbosquid.com/?p=18647
- Vitra:
  - https://www.vitra.com/en-us/professionals/downloads (403)
  - https://vcs.vitra.com/downloads/
  - https://www.vitra.com/en-us/office/tools/pcon
- MillerKnoll:
  - https://www.hermanmiller.com/resources/3d-models-and-planning-tools/
  - https://www.millerknoll.com/legal/terms-of-use/
- HAY: https://hay.com/professionals/planning
- IKEA: https://github.com/IKEA/IKEA3DAssemblyDataset
- BIMobject: https://business.bimobject.com/terms-of-service-eula
- 3D Warehouse:
  - https://embed-3dwarehouse-classic.sketchup.com/tos/
  - https://help.sketchup.com/3d-warehouse/3d-warehouse-terms-use-faq

### Blender

- Demo files and asset bundles: https://www.blender.org/download/demo-files/
- Essentials assets (CC0): https://projects.blender.org/blender/blender-assets
- 5.2 asset release notes: https://developer.blender.org/docs/release_notes/5.2/assets/ · https://www.blender.org/releases/5-2/
- Manual:
  - Asset Browser: https://docs.blender.org/manual/en/latest/editors/asset_browser.html
  - Catalogues: https://docs.blender.org/manual/en/latest/files/asset_libraries/catalogs.html
  - OBJ: https://docs.blender.org/manual/en/latest/files/import_export/obj.html
  - FBX: https://docs.blender.org/manual/en/5.2/files/import_export/fbx.html
  - glTF: https://docs.blender.org/manual/en/5.1/addons/import_export/scene_gltf2.html
- 4.5 FBX importer notes: https://developer.blender.org/docs/release_notes/4.5/pipeline_assets_io/
- glTF 2.0 spec (axes): https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html
- Remote libraries: https://developer.blender.org/docs/features/asset_system/remote_asset_libraries/

### Design rights (law-firm commentary, not primary judgments)

- CJEU Mio/konektra: https://www.gtlaw.com/en/insights/2025/12/cjeu-clarifies-scope-of-protection-for-works-of-applied-art
- BGH USM Haller follow-up: https://www.taylorwessing.com/en/insights-and-events/insights/2026/07/copyright-after-mio-and-konektra
- Herman Miller v. Blumenthal (9th Cir. 2020): https://www.hoganlovells.com/en/publications/9th-circuit-swivels-on-trade-dress-functionality-doctrine-in-favor-of-iconic-herman-miller-office-chairs
- Panton chair shape mark (Switzerland): https://www.worldtrademarkreview.com/article/acquired-distinctiveness-of-panton-chair-must-be-proven-says-supreme-court
- Design Connected units ("centimeters"): https://www.designconnected.com/Seating/Bar-stools/Hee-Stool_p1013
