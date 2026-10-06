# The mark

`yoneda-mark.svg` (stroke 9) and `yoneda-mark-bold.svg` (stroke 12, for small sizes).

Two cubic Bezier paths in a 100-unit em. Not a font. No font is required to
render it, and nothing here is licensed from anyone.

## Where the curve came from

The shape of よ is thousand-year-old calligraphy and belongs to nobody. The
*outlines* in any given typeface belong to its foundry. So the curve here was
fitted to the **skeleton**, which is the letter, and drawn with our own weight
and terminals, which is the typography.

1. Rendered よ (U+3088) from **14 SIL OFL-licensed Japanese faces** spanning
   gothic, mincho, rounded and Klee's handwriting flavour. Yu Gothic and MS
   Gothic were deliberately EXCLUDED: they are proprietary, and this becomes
   merch.
2. Normalised each to a common box. Bounding-box fitting was tried first and
   failed: it aligns the extremes but not the features, and only 11.5% of ink
   pixels were agreed by 80% of faces. Stretching to a common box aligns
   features onto features and lifts majority agreement to 50.5%.
3. Averaged into a field, took the >=50% consensus core (one connected piece),
   and skeletonised it. The mean field is worth looking at: the blur IS the
   disagreement between foundries, and the dark core is what they all agree the
   letter is.
4. Fitted the anchors to the skeleton by optimisation. Mean deviation 1.37
   em-units. An earlier unconstrained fit reached 0.22 but was overfit: it flung
   control points to (112, 90), left a nub on the tail, and broke the loop
   closure. Lower error, worse letter.
5. Repaired two structural defects by hand: the loop now closes ON the node
   (よ crosses itself, and that is not negotiable), and the tail departs from
   the same node instead of doubling back.

## Measured features (100-unit em)

    aspect w/h    0.995        essentially square
    stem top      (46.0,  0.5)
    bar           y 26.5, x 45.6 -> 96.5
    node          (50.7, 83.1)  stem, loop-in, loop-out and tail all meet here
    loop centre   (28.1, 83.9)  hole 35 x 16
    tail tip      (99.3, 88.8)

## Known imperfection

A slight kink at the loop's lower-left, where the handles are not quite
collinear. A G1 pass was tried and made it worse: the tangent average is
degenerate where both handles point the same way, and it produced a spike and a
control point at y=112. The kink is invisible at every size the mark is used
at. The spike was not. Reverted.

## Before printing

These are STROKED paths. For embroidery, screen printing, and some cutters,
convert stroke to outline first (Inkscape: Path > Stroke to Path). Do that on a
copy; the stroked version stays editable.
