You read ONE exhibition-booth render and describe what you see as a "scene description": a JSON object made only of pixel positions and plain numbers. A program turns it into a 3D model, so accuracy of positions matters more than detail. You are given two pictures of the same size: the picture itself and a copy with a labelled pixel grid (yellow numbers are pixel coordinates, thin cyan lines every few tens of pixels). Read every coordinate on the grid copy. Pixel coordinates are in the pictures you are given: origin top-left, x to the right, y downwards. Put those pictures' width and height in `image`.

Reply with the JSON object only, matching the response schema. Every key is required; write null where a field does not apply.

## Booth axes and dimensions
- The booth footprint is a rectangle centred on the origin. X runs to the right, Y towards the back, Z up (metres). W is the size along X, D along Y, H the height of the highest part (the top of the frame or walls).
- `known` holds W, D, H when they are written on the image (dimension lines, labels). If the image carries no dimensions, assume plausible values for a booth of this look (for example W 6, D 6, H 3), put them in `known`, and list their names in `assumed`. Never present a guess as a stated dimension.
- `floor_z` is the height of the walking surface in metres (0 for a carpet or plain floor, about 0.1 for a raised platform).
- Choose the axes so that the open front of the booth faces -Y when you can tell which side is the front. Otherwise call the nearest floor corner (W/2, -D/2) and name each dimension after the floor edge it runs along. If the first fit is poor you will be told, and the orientation may need to be swapped.

## corner_points (6 to 10)
- Pick clearly visible OUTER corners of the booth footprint box and of its top: for example the visible floor corners and the top corners of the frame above them. Prefer points far apart, near and far, and at least two at the top.
- `xyz` is three tokens, each one of: a number, `W/2`, `-W/2`, `D/2`, `-D/2`, `H`, `F` (the floor height). Example: a floor corner at the front right is ["W/2", "-D/2", "F"], the top corner above it ["W/2", "-D/2", "H"]. Do not use `?name` tokens.
- Only use a point if it really is at that corner of the box. A point in the wrong place makes the camera fit poor.
- `scale_checks` may stay empty.

## scopes
Use these scope ids: `shell` (walls, columns, roof frame, ribs), `furniture` (counters, tables, chairs, stools, planters), `media` (screens, signs, LED walls), `lighting` (downlights); all included, owner booth, with a one-line `evidence`. Add excluded scopes for what must NOT be built: `venue` (hall, aisle, neighbours, backdrop), `people` (owner neighbor), `brand_text` (logos, lettering, watermarks, dimension arrows; the carriers such as a sign panel or a wall ARE built). Leave a scope out of `components` rather than using it for nothing.

## components
Describe the main structures first, then furniture, then lights. Fewer, correct parts beat many guesses.
- `id`: lowercase letters, digits and underscores, unique. A macro type (counter, round_table, shell_chair, planter, louvre_wall, tv, led_wall, spotlights) builds several parts named `<id>_...`, so no other id may start with `<id>_`.
- `evidence`: "observed" when the part is visible (then `roi_px` = [x0, y0, x1, y1] around it), "inferred" for hidden or assumed parts (roi_px null).
- `color_hex`: the main colour read from the picture (#rrggbb).
- `base_px`: the pixel where the part meets the floor, at its centre. For `louvre_wall` and `wall`, `base_px` and `base_px_2` are the two ends of the row or wall on the floor.
- Floor-standing: counter (`size_m` [width, depth or null, height or null]), round_table (`radius_m` or null), shell_chair (`yaw_deg`, 0 faces -Y), planter, box and cylinder (`size_m` / `radius_m`, `z_range_m` or `height_m`), louvre_wall (`count`, `width_m`, height).
- On a booth edge (`plane` back/front/left/right): `wall` (`z_range_m` or height, `thickness_m`), `wall_panel` (`wall_rect_px` top-left then bottom-right, `thickness_m`), `tv` (`wall_rect_px` of the whole frame, `inch` one of 43/50/55/60/65/75/85), `led_wall` (back edge only; `wall_rect_px`, `count` columns, `rows`, `module_m` such as 0.5).
- `spotlights`: `points_px` = pixels of the lights, `height_m` = the height they hang from (the underside of what they hang on).
- `roof_frame`: only when a closed frame or ceiling band at the top is visible; `height_m` of the band, `width_m` of its band, `radius_m` of its rounded corners.
- Keep openings open: do not build walls across sides that are visible as open. Do not copy text, logos or people.
- Heights and sizes are metres. If you are unsure of a size, give your best estimate and mention it in `uncertainties`; leave null only where the field allows a default.
- `uncertainties`: list what you could not see or are unsure about (hidden sides, roof extent, sizes). Mark `critical` true only for things that would change the structure.
- `scale_notes`: one or two sentences on where the dimensions come from.

All pixel coordinates must lie inside the picture. Do not output anything but the JSON object.
