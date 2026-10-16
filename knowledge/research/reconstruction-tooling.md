# Reconstruction tooling for single-image booth rebuilds (CPU-only laptop)

> **Unreviewed reference notes.** Collected from public sources on the access date given below and not reviewed by a booth designer. They are not defaults of the tool, not facts about any client project and not legal advice; check the linked source before relying on a value.

- **Purpose:** pick tools that speed up the slow steps of the single-image workflow (`booth-image-to-model`):
  1. reading corner pixels by eye
  2. deciding which surfaces are walls or floor
  3. finding the depth of interior objects
  4. render time
- **Target machine:** a Windows 10 laptop with a 4-core / 8-thread Intel 8th-generation mobile CPU, 16 GB RAM, Intel UHD 620 integrated graphics and no CUDA; Python 3.12 and Blender 5.2.2 LTS. Timings below are from that machine.
- **Access date** for every URL: **2026-10-14**.
- **Method:**
  - Official repos, papers, model cards and docs first. GitHub and Hugging Face metadata (licence, dates, file sizes) were read through their APIs.
  - Some things were measured on this laptop with packages already installed. Nothing was installed. For the timing test only, two ONNX model files were downloaded to a temp folder and then deleted.
- **Commercial context:** the studio sells renders, so licences matter. NC = non-commercial. Not legal advice.

**Evidence tags used below**

| Tag | Meaning |
|---|---|
| **[V]** | Verified in an official source (repo, paper, model card, manual, PyPI/HF metadata) |
| **[M]** | Measured on this laptop on 2026-10-14 |
| **[C]** | Community or third-party report; not official |
| **[E]** | My estimate. Treat it as a guess until measured |

---

## 1. Ranked recommendation

### Adopt now (works on this CPU-only laptop)

| # | What | Fixes which slow step | Why | Cost to adopt |
|---|---|---|---|---|
| 1 | **Keep one Blender process alive, preview with EEVEE or Workbench, and use cheap Cycles settings** (section 3.5, sketch 5.3) | Render time | **[M]** EEVEE in a warm process: **3.5–4 s** per 1.44 MP frame at 16 samples. A new process costs **37–54 s** of shader compilation every time. Workbench warm: **0.8 s**. For Cycles at 32 spp, the OIDN setting alone is worth about 26 s per frame: about 34 s total with *Fast/Balanced*, about 60 s with *Accurate/High*. | No install. About 60 lines of Python (tested) |
| 2 | **MoGe-2 ViT-B (normal) via ONNX Runtime** (sketch 5.1) | Walls vs floor (normals), interior-object depth, FOV prior | **[V]** Outputs a point map, depth, normals, a validity mask, intrinsics/FOV and a metric scale. MIT code and weights. Accepts a known FOV, so the least-squares camera fit can be fed in. **[M]** 7–12 s per 1.5 MP image on this CPU. | `onnxruntime` is already installed. 419 MB model. No MoGe or PyTorch install needed |
| 3 | **OpenCV LSD → 3 vanishing points → closed-form focal and principal point** (sketch 5.2) | Reading pixels by eye: auto camera initialisation; corners snap to line intersections | **[V]** LSD is in OpenCV core again (licence issue resolved). **[M]** 0.13–0.16 s per 1.5 MP image. The whole sketch, Python RANSAC included, ran in 2.8 s. | No install (`cv2` 4.13 is present). About 70 lines (tested) |
| 4 | **Click-to-mask segmentation: SAM 2.1 tiny** (Apache-2.0) **or MobileSAM** (Apache-2.0) | Separating counters, furniture and screens. Masks for IoU checks against Workbench object-colour renders | **[V]** Small (39 M / 9.7 M params) with permissive licences. **[C]/[E]** About 3–6 s encoder time per image on this CPU, then under 0.2 s per click. | Fresh venv: `transformers` 5.x plus torch CPU. 156 MB or 41 MB of weights |
| 5 | **GeoCalib** (optional cross-check) | FOV, roll and pitch prior when few lines are visible | **[V]** Single-image intrinsics plus gravity. Apache-2.0 code, CC BY 4.0 weights, 116 MB, resizes input to 320 px. **[E]** Under 2 s on CPU. | Git install. Watch the duplicate-OpenCV trap (section 4.0) |

**How these fit the current pipeline:**

- LSD/VP (3) and GeoCalib (5) give the initial camera.
- Corner candidates come from line intersections, replacing reading by eye. The existing least-squares fit stays the authority (about 2 px RMS).
- MoGe-2 (2) then runs **with the fitted FOV passed in**.
- Its normals, rotated into the fitted world frame, label floor and wall pixels.
- Its depth is **rescaled to agree with the fitted floor and wall planes**, then used for interior objects.
- SAM (4) masks pick out which pixels belong to which object.
- Iteration renders go to the persistent Blender process (1).

### Only with an NVIDIA GPU (or for occasional overnight CPU runs)

| What | Why not on this laptop |
|---|---|
| **SAM 3 / SAM 3.1** (text prompts such as "counter", "chair", "wall") | Best semantic fit. But 848 M params, 3.44 GB of gated weights, and the official repo needs CUDA 12.6+. The `transformers` CPU path exists. **[E]** 30–120 s per image (vision embeddings once, then cheap per prompt). Custom "SAM License" with no NC clause, but with trade-control and military restrictions. |
| **Grounded-SAM-2 / Grounding DINO** (text → box → mask) | Apache-2.0, but the repos build CUDA ops. The `transformers` path runs on CPU. **[E]** 5–15 s per image for Grounding DINO tiny (689 MB). Usable for a batch, too slow inside a loop. |
| **MoGe-3** (Aug 2026, finer thin-structure geometry) | Hard dependency on FlexGEMM/Triton. ViT-L is 1.48 GB and ViT-G 5.0 GB. Use MoGe-2 on CPU. |
| **Depth Pro** (Apple) | 1.0 B params at a fixed 1536² input. **[C]** ">200 secs" on CPU. Licence is ambiguous: the HF card says `apple-amlr` (research-only). |
| **Depth Anything 3** | Main series predicts depth plus camera from one image, and Small/Base are Apache-2.0. Hard deps on `xformers`, `open3d`, `pycolmap` and `numpy<2`, and the examples are CUDA-only. |
| **ZeroPlane, PlaneRecTR** (single-image plane reconstruction) | Need detectron2 plus compiled CUDA deformable attention. |

### Skip

| What | Reason |
|---|---|
| UniDepth V1/V2 | CC BY-NC 4.0. Hard deps on `triton` and `xformers`, tested on Linux/CUDA only. |
| Depth Anything V2 Base/Large/Giant | CC BY-NC 4.0. Small (Apache-2.0) gives only relative disparity. Metric variants need you to supply the focal, and their licence is not stated. MoGe-2 covers all of this better. |
| Metric3D v2 | Needs the focal length as input. Old pins (torch 2.0.1, numpy 1.23.1, xformers 0.0.21). Weights licence not stated; "commercial inquiries" go to the authors. |
| pylsd / pylsd2 | Unmaintained (2017 / 2021). OpenCV's own LSD is back. |
| FastSAM, Ultralytics wrappers (YOLO-World, SAM via Ultralytics) | AGPL-3.0. |
| SpatialLM | Needs a point cloud (from video SLAM), not one image. CC BY-NC weights, CUDA build. |
| NonCuboidRoom, LayoutNet, SRW-Net | Research code, unmaintained since 2021–2023. See 3.4. |

---

## 2. Measured on this laptop (2026-10-14)

- **Setup:**
  - Blender 5.2.2 LTS (`-b --factory-startup`), GPU backend **OpenGL** (the 5.2 default here).
  - onnxruntime 1.28.0 CPU, OpenCV 4.13.0 headless, Python 3.12.3.
  - Test render scene: 13 boxes, Principled BSDF, one area light, one sun and a world colour, at 1600×900 (1.44 MP). It is simple, so **real booths with textures or glass will be slower**.
- **Variance:** run-to-run variance on this laptop is about ±10–20% (thermal throttling on a 15 W CPU).

### Rendering [M]

| Engine / settings | Time | Note |
|---|---|---|
| Workbench, first render in a new process | 2.9 s | |
| Workbench, warm process (socket server) | **0.8 s** | |
| EEVEE 16 spp, **cold** (new process) | 47.4 s / 53.6 s / 36.7 s (3 runs) | Almost all of it is GPU shader compilation; there is no cross-process speed-up |
| EEVEE 16 spp, warm, same process | **3.7 s**; 3.5 s; 4.0 s after moving an object | **Works headless on the UHD 620** |
| EEVEE 64 spp, warm | 11.4 s | |
| Cycles CPU, 32 spp, adaptive threshold 0.05, 4 bounces, no denoise | 32.1 s | |
| Same plus OIDN, prefilter **Fast**, quality **Balanced** | **34.0 s** | |
| Same plus OIDN, prefilter **Accurate**, quality **High**, albedo + normal | 60.5 s; 58.0 s | **OIDN Accurate/High costs about +26 s at 1.44 MP on this CPU** |
| Same, persistent data on, second render after an edit | 54.1 s (vs 58.0 s) | About −7% here; only helps inside a living process |
| Same Accurate/High, 50% resolution (800×450) | 14.6 s | |
| Cycles 8 spp plus OIDN Fast/Balanced | 12.0 s | |
| Cycles 16 spp, Fast GI approximation, OIDN Fast/Balanced | 16.4 s | |
| Cycles 128 spp, threshold 0.01, 12 bounces, OIDN Accurate/High | 149.4 s | |

Cycles printed `WARNING CUEW initialization failed`. This is harmless: there is no CUDA library.

### Vision [M]

| Tool | Input | Time |
|---|---|---|
| OpenCV LSD (`LSD_REFINE_STD`) | 4 booth images resized to about 1.5 MP | **134–164 ms** (1,100–1,280 segments). At native size (736–1200 px wide): 53–117 ms |
| MoGe-2 **ViT-S** normal ONNX (141 MB) | 1428×1036 (1.48 MP) | 4.7 s @1200 tokens · 7.5–9.6 s @1800 · 13–16 s @2500. Session load 2.3 s |
| MoGe-2 **ViT-B** normal ONNX (419 MB) | 1428×1036 | **7.0–8.2 s @1200 tokens · 12.0 s @1800**. Session load 3.1 s |
| MoGe-2 ViT-S / ViT-B ONNX | 738×415 | 6.9 s / 10.3 s @1800 tokens. Cost scales with token count, not image size |
| LSD + 3-VP RANSAC + closed-form calibration (sketch 5.2) | 738×415 | 2.8 s total (Python start-up and RANSAC included) |

### Accuracy anecdote: one image, no ground truth [M]

The image is one local 738×415 client render (not tracked). The existing least-squares fit used 8 eyeballed corners at 1.76 px RMS, **with booth depth assumed to be 4.5 m**. It gives f = 1034 px, which is a horizontal FOV of 39.2°.

| Method | Horizontal FOV | Principal point / other |
|---|---|---|
| LSD + VP (sketch 5.2) | f = 892 px → **44.9°** | Principal point within 2 px of the image centre |
| MoGe-2 ViT-B | **41.9°** | |
| MoGe-2 ViT-S | **48.1°** | |

- **Metric scale:** MoGe's depth was 5.6–8.5 m, while the fitted camera stands about 16 m from the booth. That is **about 2× off**. On booth images, especially rendered or elevated views, **do not trust MoGe's absolute scale**. Anchor the scale to the fitted shell (sketch 5.1).
- **Bias:** the FOV estimates scatter by ±10%, so use them as initial values only. The fit's own focal can be biased by its assumed depth.

### Environment findings [M]

These apply to the system Python.

- **OpenCV conflict:** both `opencv-contrib-python 4.10.0.84` and `opencv-python-headless 4.13.0.92` are installed. The headless build shadows contrib, so `cv2.ximgproc` is empty and **FLD (`createFastLineDetector`) is unavailable**. LSD still works because it lives in core `imgproc`. See 4.0.
- **Old transformers:** `transformers 4.41.1` is too old for the native DepthPro, SAM 2, SAM 3 and Florence-2 classes. They were added to Transformers on 2025-02-10, 2025-08-14, 2025-11-19 and 2025-08-20 respectively **[V]**.
- **torch:** `torch 2.13.0+cpu` and `onnxruntime 1.28.0` are present.

---

## 3. Per-tool tables

### 3.1 Line segments, vanishing points, calibration

| Tool | Version / date [V] | Licence [V] | Size | CPU feasibility / time | Notes |
|---|---|---|---|---|---|
| **OpenCV LSD** `cv2.createLineSegmentDetector` | In `imgproc` core. Present in 4.13 and in the 5.x source. OpenCV **5.0.0 released 2026-06-06**, 4.14.0 on 2026-07-19. pip `opencv-contrib-python` 4.14.0.94 (2026-07-29) / 5.0.0.93 (2026-07-02) | Apache-2.0 | Part of the 44–54 MB wheel | **[M]** 0.13–0.16 s at 1.5 MP | Header note: "removed from OpenCV version 3.4.6 to 3.4.15 and version 4.1.0 to 4.5.3 due original code license conflict", then restored after the NFA code was published under MIT. So any **≥4.5.4** works. |
| **OpenCV FLD** `cv2.ximgproc.createFastLineDetector` | opencv_contrib `ximgproc`, present in 5.x | Apache-2.0 | Contrib wheel, 53.8 MB | **[E]** 20–60 ms at 1.5 MP (Canny-based; usually faster than LSD) | Needs a **single** contrib OpenCV package (see 4.0). Not measured because of the broken environment. |
| **pytlsd** | 0.0.2 (2022-12-29) | MIT | Tiny | Fast | LSD bindings used by DeepLSD. **No cp312 Windows wheel**, so it needs a C++ build. Not needed. |
| **pylsd / pylsd2** | 0.0.2 (2017) / 0.0.3 (2021) | BSD | — | — | Unmaintained. Skip. |
| **ELSED** | Repo active (pushed 2026-07) | Apache-2.0 | — | **[E]** Very fast (paper targets real time) | Not on PyPI; build from source. Optional. |
| **DeepLSD** (CVPR 2023) | Repo active (pushed 2026-09) | MIT | Small CNN | **[E]** A few seconds on CPU | Tested by the authors with CUDA 11. VP refinement needs extra C++ deps (Ceres etc.). Optional upgrade for blurry or low-contrast edges. |
| **lu-vp-detect** (Lu et al., WACV 2017, Manhattan 3-VP) | 1.0.4 (2023-04-07). Repo last push 2023-06 | MIT | Pure Python | **[E]** About 1 s | Needs a focal guess (default 1500 px) and calls `cv2.createLineSegmentDetector(0)`. **`install_requires` pulls `opencv-contrib-python`**, so install with `--no-deps` or vendor the single file. |
| **GlobustVP** (CVPR 2025 oral, convex-relaxation Manhattan VP) | Repo pushed 2026-04 | Apache-2.0 | Python + `cvxpy` (SCS/MOSEK) | **[E]** Seconds (SDP per VP) | **Needs a known K**. Good as a robust refinement once the camera fit exists. Requirements list MOSEK, a commercial solver; SCS is the free alternative. |
| **GeoCalib** (ECCV 2024) | Weights v1.0 (2024-09-08). Repo pushed 2026-08 | Code Apache-2.0. **Weights CC BY 4.0** (commercial OK with attribution) | 116 MB | **[E]** Under 2 s (input resized to 320 px) | Outputs camera intrinsics plus **gravity (roll/pitch)**. Accepts priors (`priors={"focal": ...}`). requirements.txt includes `opencv-python`, so watch for duplicate OpenCV. |
| **fSpy** (desktop app) + Blender importer | Last tag 1.1.0-beta.3 (2020-04-14). Importer `perarnia/fSpy-Blender` pushed 2022 | GPL-3.0 | — | Manual GUI | Manual 2/3-VP camera matching. Blender 5.x compatibility **unverified**. Not automatable. |

**Calibration from three orthogonal VPs** (Caprile & Torre 1990; Hartley & Zisserman §8.8). Assumes square pixels and zero skew:

- **Principal point:** the **orthocenter** of the triangle formed by the three finite VPs v1, v2, v3.
- **Focal:** f² = −(vᵢ − p)·(vⱼ − p) for any orthogonal pair.
- **Rotation:** the columns of R are K⁻¹vᵢ, normalised, with signs fixed by the chosen world axes.
- **When the vertical VP is near infinity** (vertical lines stay parallel in the image), assume p = image centre and use the two horizontal VPs.

These formulas are standard. The two cited secondary sources confirm the orthocenter/tetrahedron construction but not the exact focal formula. Sources: Hunter College notes (`cs.hunter.cuny.edu/~ioannis/CalibrationFromParallelLines.pdf`); UMich EECS 442 single-view slides.

**Practical use:** VPs give the initial focal, pitch and roll. Line intersections give sub-pixel corner candidates. The existing least-squares fit (camera + box proportions) remains the final step. VP-only calibration is fragile when one VP is far away: here the vertical VP was at y ≈ 1920 for a 415 px tall image.

### 3.2 Monocular geometry and depth

| Model | Version / date [V] | Licence (code / weights) [V] | Params · download [V] | Point map? | FOV / intrinsics? | Metric? | CPU on this laptop |
|---|---|---|---|---|---|---|---|
| **MoGe-2** (Microsoft) — **recommended** | Weights 2025-06-10. Paper arXiv 2507.02546. Package v2.0.0 at commit `b942f00` (2025-10-16) | MIT / **MIT** (HF tag) | ViT-S 35 M · 141 MB; **ViT-B 104 M · 419 MB**; ViT-L 326–331 M · 1.32 GB. Official ONNX: `moge-2-vit{s,b,l}-normal-onnx` | **Yes**, (H,W,3) in OpenCV camera coordinates | **Yes**: normalised intrinsics. `infer(fov_x=...)` accepts a known FOV | Yes, but see the 2× anecdote in §2 | **[M]** ViT-B 7–12 s, ViT-S 4.7–9.6 s at 1.5 MP (1200–1800 tokens). **[E]** ViT-L 25–60 s |
| MoGe-1 | Paper arXiv 2410.19115 (CVPR'25 oral) | MIT / MIT | 314 M · 1.26 GB | Yes (affine-invariant) | Yes | No | **[E]** 25–60 s |
| MoGe-3 | Weights **2026-08-18**. Paper arXiv 2607.17967 | MIT / MIT | ViT-L 370 M · 1.48 GB; ViT-G 1.25 B · 5.0 GB | Yes, finer thin structures | Yes | Yes | Not on this laptop: package 3.0.0 hard-requires `flex-gemm` (Triton) |
| **Depth Pro** (Apple) | Weights 2024-10-02. arXiv 2410.02073 (ICLR 2025). In `transformers` since 2025-02-10 | GitHub `LICENSE` is Apple's sample-code licence; the README says weights fall under it too. But **HF lists `apple-amlr` (research only)**. Conflicting, so treat as **not cleared for commercial use** | 1.0 B · 1.90 GB | No; depth plus focal, so you can back-project | **Yes**: `focallength_px`, `field_of_view` | Yes | **[C]** ">200 secs" on CPU (HF Space discussion; CPU unknown). **[E]** 2–5 min, 6–10 GB RAM |
| Depth Anything V2 (relative) | 2024-06-14. In `transformers` since 2024-07-05 | Small **Apache-2.0**. Base/Large/Giant **CC BY-NC 4.0** | S 24.8 M · 99 MB; B 97.5 M; L 335 M | No (disparity) | No | No | **[E]** Small: 0.5–2 s at 518 px |
| Depth Anything V2 metric (Hypersim indoor, max 20 m) | 2024-06-22 / HF 2024-07-26 | **Not stated** on the HF cards | S 99 MB; B 390 MB; L 1.34 GB | Only by script, with a **user-supplied focal** (default 470.4 px) | No | Yes | **[E]** Small: 0.5–2 s |
| **Depth Anything 3** | 2025-11-14 | DA3-Small (0.08 B) / Base (0.12 B) / Metric-L / Mono-L: **Apache-2.0**. Large/Giant/Nested: **CC BY-NC** | Small · 137 MB; Base · 542 MB; Metric-L · 1.34 GB | Depth plus rays | **Yes**: "intrinsics from one or more images" (main series) | Metric-L needs the focal; Nested is metric | **[E]** Small 2–6 s, but deps (`xformers`, `open3d`, `pycolmap`, `evo`, `numpy<2`) are a Windows-CPU headache |
| Metric3D v2 | Models 2024-03-18; ONNX 2024-06-03. Repo last push 2025-03 | Code BSD-2-Clause. Weights **not stated** ("commercial inquiries" to authors). The community ONNX `onnx-community/metric3d-vit-small` is tagged CC0, but the upstream licence still governs | ViT-S · 150 MB; ViT-L · 1.65 GB; giant2 · 5.5 GB | No (depth + normals) | **No**: in-the-wild mode tries "nine default focal-length settings"; users must set the focal | Yes, if the focal is right | **[E]** ViT-S ONNX 2–5 s |
| UniDepth V2 | 2025-02-28. Repo last push 2025-05 | **CC BY-NC 4.0** | V2-S 34 M · 137 MB; V2-L · 1.4 GB | **Yes** (`points`) | **Yes** (`intrinsics`) | Yes | Possible in principle, but `triton` and `xformers` are hard requirements, and it is tested only on Linux with CUDA ≥11.8 |

**Which output a point map and FOV/intrinsics:**

- **Point map plus intrinsics:** MoGe-1/2/3, UniDepth, Depth Anything 3 (depth + rays → points + K).
- **Depth plus focal:** Depth Pro.
- **Depth only, focal needed from you:** Depth Anything V2 metric, Metric3D v2.

**Commercially clean and CPU-friendly:** MoGe-2 (MIT/MIT). Then DA3-Small/Base (Apache-2.0, heavy deps). Then DAv2-Small (Apache-2.0, relative depth only).

### 3.3 Segmentation

| Model | Version / date [V] | Licence [V] | Params · download [V] | Prompting | CPU on this laptop | Verdict |
|---|---|---|---|---|---|---|
| **SAM 2.1** tiny / small | SAM 2: 2024-07-29. SAM 2.1: 2024-09-29/30. Repo pushed 2026-05. In `transformers` since 2025-08-14 | **Apache-2.0** (code and checkpoints) | tiny 38.9 M · 156 MB; small 46 M · 184 MB | Points, boxes, masks | **[V]** 91 / 85 FPS on A100 (GPU only). **[C]** Hiera-T full video pipeline: 1.96 s/frame (6 threads), 4.95 s (2 threads) on an i7-13620H. **[E]** 3–6 s encoder on the i7-8550U, then under 0.2 s per prompt | **Adopt** (click-to-mask). Repo install on Windows: the README says "strongly recommended to use WSL". Use the `transformers` or ONNX route instead |
| **MobileSAM** | 2023-06/07 (no newer dated news). Repo pushed 2026-05 | Apache-2.0 (GitHub). HF weights tagged MIT | 9.66 M total · 41 MB | Points, boxes (SAM API) | **[V]** "about 3 seconds" per run on the authors' Mac i5 CPU, demo included. GPU: 8 ms encoder + 4 ms decoder. **[E]** 0.5–2 s here | **Adopt** if SAM 2.1-tiny is too slow. ONNX export script included |
| EfficientSAM | 2023-12 (ONNX 2024-01-12). Repo last push 2024-12 | Apache-2.0 | ViT-Ti · 41 MB; ViT-S · 106 MB. Ships `efficientsam_s_cpu.jit` + ONNX | Points, boxes | **[E]** 1–3 s | Alternative to MobileSAM. Older |
| **SAM 3 / 3.1** | SAM 3: HF 2025-11-07, arXiv 2511.16719. SAM 3.1: **2026-03-27**. In `transformers` since 2025-11-19 | "SAM License" (custom, last updated 2025-11-19). No NC clause; trade-control, ITAR and military bans; indemnity | 848 M · **3.44 GB, gated** (manual approval) | **Text** ("counter"), image exemplars, points | Official repo: Python ≥3.12, torch ≥2.7, **CUDA ≥12.6**. `transformers` lets you compute vision embeddings once and loop prompts. **[E]** 30–120 s per image on this CPU, 4–6 GB RAM | **GPU** |
| Grounding DINO (tiny/base) | Paper 2023-03. Repo last push 2024-08. In `transformers` since 2024-04-11 | Apache-2.0 | tiny · 689 MB; base · 933 MB | Text → boxes | **[E]** 5–15 s per image. No reliable published CPU timing found | GPU, or batch-only on CPU |
| Grounded-SAM-2 | Repo last push 2025-11 | Apache-2.0 | Grounding DINO + SAM 2 | Text → box → mask | Repo setup compiles CUDA ops | GPU |
| Florence-2-base | HF 2024-06. In `transformers` since 2025-08-20 | MIT | 0.23 B · 463 MB | `<OD>`, `<CAPTION_TO_PHRASE_GROUNDING>`, etc. | **[E]** 2–6 s per task | Optional, CPU-friendly text→box. Then SAM 2.1 for masks |
| FastSAM | Repo last push 2024-07 | **AGPL-3.0** | — | — | — | Skip (licence) |

**Practical note for booths:** walls and floor are better separated by **MoGe normals plus the fitted Manhattan frame** (deterministic) than by text-prompted segmentation. SAM is most useful for **interior objects** (counter, stools, screens, plants), using one click per object.

### 3.4 Single-image room-layout estimation (perspective images)

**No maintained, CPU-ready option was found.** [V for repo states; E for the conclusion]

| Project | Venue / last activity [V] | Licence | Input → output | Status for us |
|---|---|---|---|---|
| NonCuboidRoom (Yang et al.) | WACV 2022. Last push 2022-09 | MIT | Perspective RGB → floor, ceiling, walls (non-cuboid) | Unmaintained, trained on ScanNet rooms (has ceiling). A booth has no ceiling and is seen from outside, so it is a poor fit |
| LayoutNet | CVPR 2018. Last push 2021-01 | MIT | Perspective or panorama → cuboid layout | Torch7 (Lua). Obsolete |
| SRW-Net | 2023-03 | MIT | Perspective → semantic room wireframe | Unmaintained |
| PlaneRecTR | ICCV 2023. Last push 2024-09 | Apache-2.0 | RGB → plane instances + parameters | detectron2, GPU |
| ZeroPlane | CVPR 2025 (highlight). Last push 2025-10 | MIT | RGB → planar depth + segmentation + mesh | PyTorch 2.1 + detectron2 + compiled MSDeformAttn. GPU |
| Plane-DUSt3R | ICLR 2025 | MIT | **Multiple** unposed views → room planes | Not single-image |
| SpatialLM 1.1 | NeurIPS 2025. Last push 2026-06 | Weights **CC BY-NC 4.0** | **Point cloud** (from video SLAM) → walls, doors, windows, boxes | Not single-image. CUDA |
| HorizonNet, LGT-Net | Active | MIT | **Panoramas only** | Not applicable |

**Recommended substitute:** **MoGe-2 normals + VP/fit Manhattan frame + plane RANSAC**.

1. Rotate the normals to world coordinates.
2. Label pixels: floor = normal·up > 0.9; wall = |normal·up| < 0.2 and aligned with one of the two horizontal axes.
3. Fit planes with RANSAC on the rescaled points.
4. Intersect the planes with the existing box fit.

This is about 100–150 lines of numpy and handles the open, ceiling-less booth case. **[E]**

### 3.5 Blender 5.2 CPU rendering and iteration speed

Docs: Blender **5.2 LTS** manual (manual source branch `blender-v5.2-release`) and the 5.2 Python API.

| Topic | What the docs say [V] | What to do here |
|---|---|---|
| Adaptive sampling | Noise Threshold: "Typical values are in the range from 0.1 to 0.001". Min Samples 0 = automatic | Iterations: 0.05 with 16–32 max samples. Finals: 0.01 |
| Time limit | "Stops rendering if the time exceeds the limit" (excludes pre-render) | Optional hard cap for iteration renders |
| Denoiser | OIDN prefilter *None / Fast / Accurate*: "Accurate … usually produces more detailed results than Fast, but with increased processing time". Quality *High / Balanced / Fast*. Use at least *Albedo* passes | **[M]** On this CPU, Accurate/High adds about 26 s at 1.44 MP; Fast/Balanced adds about 2 s. Use Fast/Balanced for iterations and Accurate/High only for the final |
| Light paths | Fewer bounces converge faster; caustics can be disabled. Fast GI approximation: "background tinted ambient occlusion" | Iterations: max 4 bounces (diffuse 2, glossy 2), caustics off. Fast GI gave no clear win in the test scene |
| Path guiding | "only available when rendering on a CPU". Helps when light enters through small openings | Not needed for open booths |
| Light tree | Less noise but "somewhat longer render time per sample" | With 1–3 big lights, try it off in iterations (not measured) |
| Tiles | Tiles exist to cut memory. "default 2048 pixels provides a good balance". Lowering it costs "a small performance" | Leave at 2048. A 1.44 MP frame is one tile |
| Persistent data | "Keep render data in memory after rendering for faster re-renders" | Only matters inside a long-lived process. **[M]** −7% in the simple scene; more with heavy textures **[E]** |
| Threads | Auto-detect = logical processors | Leave on auto (8). Use *Fixed* 6 if the laptop must stay responsive |
| Texture cache (new) | `.tx` tiled/mipmapped textures reduce memory and start-up "at the cost of a small rendering performance impact" | Only for texture-heavy finals |
| Workbench | "optimized for fast rendering during modeling and animation preview". No shader nodes. Random or object colours, X-ray, cavity | **[M]** 0.8 s warm. Use flat object-ID colours to produce **instant masks** for IoU against SAM masks or the photo |
| EEVEE headless on UHD 620 | Requirements: GPU with OpenGL 4.3 **and** Vulkan 1.3, 2 GB VRAM; Intel "Kaby Lake" and newer. `--gpu-backend` accepts `vulkan`, `metal`, `opengl` | **[M] Works in `-b` mode on this laptop** (OpenGL backend). Cold shader compilation is 37–54 s **per process**; warm frames take 3.5–4 s. Preferences offer a *Subprocess* shader-compilation method ("can be faster … consumes significantly more RAM"); not measured |
| Keep Blender alive | No built-in server. `-c help` lists only `asset_listing`, `extension`, `maketx` **[M]**. Docs: `--python-console` "Run Blender with an interactive console". **Threads:** "Python threads cause Blender to crash in hard to diagnose ways"; threads only work when they "finish up before the script does". `bpy.app.timers` runs callbacks on the main thread (UI sessions) | **[M]** A **blocking socket loop on the main thread** inside `blender -b --python server.py` works (sketch 5.3). The first EEVEE frame took 36.7 s, the next edit+render 3.5 s, Workbench 0.8 s. For a GUI session, use a timer-polled server (as the MIT `blender-mcp` add-on does) |
| `bpy` as a pip module | `bpy` 5.2.2 on PyPI: **`requires_python ==3.13.*`**, Windows wheel 338 MB | Not usable from the system Python 3.12. Would need a separate 3.13 venv. The socket server avoids this |

---

## 4. Install commands (not run; sizes from PyPI/HF metadata)

### 4.0 One-time hygiene: use a dedicated venv and exactly one OpenCV package

The OpenCV wheels share the `cv2` module, so two installed packages overwrite each other. This already happened in the system Python (§2).

```powershell
py -3.12 -m venv <venv>\booth-cv
<venv>\booth-cv\Scripts\Activate.ps1
python -m pip install --upgrade pip
# exactly ONE OpenCV build (contrib includes FLD/ximgproc; headless = no GUI deps)
pip install "opencv-contrib-python-headless==4.14.0.94"   # ~54 MB wheel; 4.x avoids OpenCV 5 API churn
pip install numpy scipy "onnxruntime==1.31.0"            # onnxruntime ~15 MB (needs Python >=3.11)
pip install huggingface_hub                               # model downloads
```

To repair the **system** Python instead (affects other tools there):

```powershell
pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python opencv-contrib-python-headless
pip install "opencv-contrib-python-headless==4.14.0.94"
```

### 4.1 MoGe-2 on CPU via ONNX (recommended path; no MoGe or PyTorch install)

```powershell
python -c "from huggingface_hub import hf_hub_download as d; print(d('Ruicheng/moge-2-vitb-normal-onnx','model.onnx',local_dir=r'<models>\moge2-vitb-onnx'))"   # 419 MB
# smaller/faster: Ruicheng/moge-2-vits-normal-onnx (141 MB); larger: Ruicheng/moge-2-vitl-normal-onnx
```

The ONNX graph is the raw `forward()`. Focal and shift recovery is not included, so sketch 5.1 re-implements it in numpy, following MoGe's `geometry_numpy.py` (MIT).

**Alternative: full PyTorch MoGe-2** (gives `infer(fov_x=...)`, masks and utilities). **Pin the pre-MoGe-3 commit**, because `main` (3.0.0) hard-requires `flex-gemm`/Triton and `numpy>=2`:

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu      # torch CPU wheel ~120-200 MB
pip install "git+https://github.com/microsoft/MoGe.git@b942f00bdc"                  # MoGe 2.0.0; needs git
# pulls gradio (~31 MB wheel + deps), opencv-python (!), utils3d and pipeline from git.
# Afterwards re-check: only one OpenCV package may remain (see 4.0).
```

### 4.2 LSD / VP / calibration

```powershell
# nothing beyond 4.0 for LSD + sketch 5.2
pip install --no-deps "lu-vp-detect==1.0.4"                 # optional; --no-deps avoids a 2nd OpenCV
pip install --no-deps "git+https://github.com/cvg/GeoCalib#egg=geocalib"; pip install kornia matplotlib
#   GeoCalib also needs torch CPU (4.1); weights 116 MB auto-download from its GitHub release on first use
```

### 4.3 Segmentation (CPU)

```powershell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install "transformers>=5.19"                              # 12.6 MB wheel; Sam2Model/Sam2Processor
# weights on first use: facebook/sam2.1-hiera-tiny 156 MB (Apache-2.0)
# MobileSAM alternative:
pip install timm "git+https://github.com/ChaoningZhang/MobileSAM.git"   # + mobile_sam.pt 41 MB (HF dhkim2810/MobileSAM)
# text->box on CPU (optional): IDEA-Research/grounding-dino-tiny 689 MB, or microsoft/Florence-2-base 463 MB
# GPU only: facebook/sam3 (3.44 GB, gated: request access, then `hf auth login`)
```

### 4.4 Blender

Nothing to install. Run the server script with the installed `blender.exe` (sketch 5.3).

---

## 5. Minimal usage sketches (all three were run on this laptop on 2026-10-14)

### 5.1 MoGe-2 (ONNX, CPU) → FOV, metric-ish points, normals; anchor scale to the fitted shell

```python
# moge2_onnx.py  -- tested with onnxruntime 1.28, MoGe-2 ViT-S/ViT-B normal ONNX
# focal/shift recovery ported from microsoft/MoGe @b942f00 moge/utils/geometry_numpy.py (MIT)
import numpy as np, cv2, onnxruntime as ort
from scipy.optimize import least_squares

def _uv(w, h):                       # MoGe's normalised view-plane grid (half-diagonal = 1)
    a = w / h; sx, sy = a / (1 + a*a) ** .5, 1 / (1 + a*a) ** .5
    u = np.linspace(-sx*(w-1)/w, sx*(w-1)/w, w, dtype=np.float32)
    v = np.linspace(-sy*(h-1)/h, sy*(h-1)/h, h, dtype=np.float32)
    return np.stack(np.meshgrid(u, v, indexing="xy"), -1)

def _focal_shift(points, mask, focal=None, n=64):
    h, w = points.shape[:2]; ys = np.linspace(0, h-1, n).astype(int); xs = np.linspace(0, w-1, n).astype(int)
    p = points[ys][:, xs].reshape(-1, 3); q = _uv(w, h)[ys][:, xs].reshape(-1, 2); m = mask[ys][:, xs].ravel()
    xy, z, q = p[m, :2], p[m, 2], q[m]
    def err(s):
        pr = xy / (z + s)[:, None]; f = focal if focal is not None else (pr*q).sum() / (pr*pr).sum()
        return (f*pr - q).ravel()
    s = float(least_squares(err, x0=0, ftol=1e-3, method="lm").x[0])
    pr = xy / (z + s)[:, None]
    return (focal if focal is not None else float((pr*q).sum() / (pr*pr).sum())), s

class MoGe2:
    def __init__(self, onnx_path):
        self.sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])   # load once (2-3 s)
    def __call__(self, rgb, num_tokens=1200, fov_x_deg=None):
        H, W = rgb.shape[:2]; a = W / H
        x = (rgb.astype(np.float32) / 255).transpose(2, 0, 1)[None]
        pts, nrm, msk, scale = self.sess.run(None, {"image": x, "num_tokens": np.array(num_tokens, np.int64)})
        pts, nrm, msk, scale = pts[0], nrm[0], msk[0] > .5, float(scale[0])
        f_known = None if fov_x_deg is None else a / (1 + a*a) ** .5 / np.tan(np.radians(fov_x_deg) / 2)
        f, shift = _focal_shift(pts, msk, f_known)
        fx = f / 2 * (1 + a*a) ** .5 / a * W                    # pixels
        depth = (pts[..., 2] + shift) * scale                   # OpenCV camera: x right, y down, z forward
        return dict(depth=depth, normal=nrm, mask=msk & (depth > 0), fx_px=fx,
                    fov_x_deg=np.degrees(2*np.arctan(W / 2 / fx)), metric_scale=scale)

# --- usage --------------------------------------------------------------------------
rgb = cv2.cvtColor(cv2.imread("input/booth.jpg"), cv2.COLOR_BGR2RGB)
moge = MoGe2(r"<models>\moge2-vitb-onnx\model.onnx")
out = moge(rgb, num_tokens=1200, fov_x_deg=39.2)               # pass the least-squares FOV when you have it

# 1) walls/floor: rotate normals to world. R_wc = camera->world rotation from the fit; OpenCV->Blender camera
#    axes differ by diag(1,-1,-1): n_world = R_wc_blender @ (np.diag([1,-1,-1]) @ n_cv)
# 2) scale anchor (MoGe metric scale was ~2x off on a test image): for floor-labelled pixels,
#    ray-cast the fitted camera onto z=0 (camera_math.floor_point) to get fitted depth d_fit, then
#    s = np.median(d_fit / out["depth"][floor_px]); depth_m = s * out["depth"]
# 3) interior object: depth at its SAM-mask footprint (lowest mask rows) -> unproject with the fitted camera
```

### 5.2 LSD → three vanishing points → focal and principal point

```python
# vp_calib.py -- tested on one local 738×415 client render: f=892 px, principal point within 2 px of centre, 2.8 s total
import numpy as np, cv2

def segments(gray, min_len_frac=0.03):
    s = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD).detect(gray)[0].reshape(-1, 4)
    L = np.hypot(s[:, 2] - s[:, 0], s[:, 3] - s[:, 1]); k = L > min_len_frac * np.hypot(*gray.shape)
    return s[k], L[k]

def ang_err(s, vp):                                  # deg between segment and midpoint->VP direction
    mid = (s[:, :2] + s[:, 2:]) / 2; d1 = s[:, 2:] - s[:, :2]; d2 = vp[:2] - mid * vp[2]
    c = np.abs((d1 * d2).sum(1)) / (np.linalg.norm(d1, axis=1) * np.linalg.norm(d2, axis=1) + 1e-12)
    return np.degrees(np.arccos(np.clip(c, 0, 1)))

def vps(s, L, n=3, iters=3000, thr=1.5, seed=0):
    rng = np.random.default_rng(seed)
    P1, P2 = np.c_[s[:, :2], np.ones(len(s))], np.c_[s[:, 2:], np.ones(len(s))]
    lines = np.cross(P1, P2); lines /= np.linalg.norm(lines[:, :2], axis=1, keepdims=True)
    rest, out = np.arange(len(s)), []
    for _ in range(n):
        best, score = None, -1
        for _ in range(iters):
            i, j = rng.choice(rest, 2, replace=False); vp = np.cross(lines[i], lines[j])
            inl = rest[ang_err(s[rest], vp) < thr]
            if L[inl].sum() > score: best, score = inl, L[inl].sum()
        out.append(np.linalg.svd(lines[best] * L[best, None])[2][-1])   # LS intersection of inliers
        rest = np.setdiff1d(rest, best)
    return out

def calibrate(vps_h, w, h, far=50):
    fin = [v[:2] / v[2] for v in vps_h if abs(v[2]) > 1e-9 and np.linalg.norm(v[:2] / v[2]) < far * max(w, h)]
    if len(fin) == 3:                                # principal point = orthocenter of the VP triangle
        a, b, c = fin; p = np.linalg.solve(np.array([c - b, c - a]), np.array([(c - b) @ a, (c - a) @ b]))
    else:                                            # vertical VP at infinity -> assume image centre
        p = np.array([w / 2, h / 2])
    f2 = -(fin[0] - p) @ (fin[1] - p)
    return np.sqrt(f2) if f2 > 0 else np.nan, p, fin

gray = cv2.imread("input/booth.jpg", cv2.IMREAD_GRAYSCALE); h, w = gray.shape
s, L = segments(gray); f, p, fin = calibrate(vps(s, L), w, h)
print(f"f={f:.0f}px  pp={p}  hFOV={np.degrees(2*np.arctan(w/2/f)):.1f}deg  lens36={36*f/w:.1f}mm")
# Next: feed f, p and R (columns = normalised K^-1 v_i) as the initial guess to box_fit/camera_fit,
# and offer intersections of long inlier segments as corner candidates instead of eyeballed pixels.
```

### 5.3 Keep one Blender alive (EEVEE warm frames in about 3.5 s instead of 37–54 s)

```python
# blender_server.py -- start: "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b --factory-startup --python blender_server.py -- 8765
# One JSON per line: {"code": "..."} -> {"ok":..., "out":..., "sec":...}; {"cmd":"quit"} stops.
# Runs everything on Blender's main thread (no Python threads -> safe per the API "Gotchas").
import bpy, sys, json, socket, time, traceback, io, contextlib
port = int(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else 8765
ns = {"bpy": bpy}                                   # namespace persists between requests
srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", port)); srv.listen(1)       # localhost only: this executes arbitrary code
running = True
while running:
    conn, _ = srv.accept()
    with conn, conn.makefile("rwb") as f:
        for line in f:
            req = json.loads(line)
            if req.get("cmd") == "quit":
                running = False; f.write(b'{"ok": true}\n'); f.flush(); break
            buf, t0 = io.StringIO(), time.perf_counter()
            try:
                with contextlib.redirect_stdout(buf): exec(req["code"], ns)
                r = {"ok": True, "out": buf.getvalue()}
            except Exception:
                r = {"ok": False, "out": buf.getvalue(), "err": traceback.format_exc()}
            r["sec"] = round(time.perf_counter() - t0, 3)
            f.write((json.dumps(r) + "\n").encode()); f.flush()
```

```python
# client side (any Python): send build/patch code, then render
import json, socket
s = socket.create_connection(("127.0.0.1", 8765)); f = s.makefile("rwb")
def call(code): f.write((json.dumps({"code": code}) + "\n").encode()); f.flush(); return json.loads(f.readline())
call("exec(open(r'<repo>/.../build_scene.py').read())")          # first build
call("""scn=bpy.context.scene; scn.render.engine='BLENDER_EEVEE'; scn.eevee.taa_render_samples=16
scn.render.filepath=r'<tmp>/it_001.png'; bpy.ops.render.render(write_still=True)""")
# iteration settings for Cycles when EEVEE is not enough:
call("""c=bpy.context.scene.cycles; c.device='CPU'; c.samples=32; c.use_adaptive_sampling=True
c.adaptive_threshold=0.05; c.max_bounces=4; c.diffuse_bounces=2; c.glossy_bounces=2
c.caustics_reflective=c.caustics_refractive=False; c.use_denoising=True; c.denoiser='OPENIMAGEDENOISE'
c.denoising_input_passes='RGB_ALBEDO_NORMAL'; c.denoising_prefilter='FAST'; c.denoising_quality='BALANCED'
bpy.context.scene.render.use_persistent_data=True""")
```

**Design notes:**

- **Patch, don't rebuild:** only the first frame per process pays for shader compilation, so send parameter patches (move or resize objects) instead of rebuilding the scene.
- **Ownership:** one process should own one scene.
- **Restart on crash:** use a watchdog, or `--python-exit-code`, to restart the process if it dies.
- **GUI alternative:** for a Blender session with a UI, register a socket poller with `bpy.app.timers.register(fn)`, which calls `fn` on the main thread. Do not use Python threads.

---

## 6. Caveats and open questions

- **Timings depend on this laptop and on a simple test scene.** Expect longer Cycles times with textures, glass and many lights. EEVEE warm times depend on the number of unique materials, because each new material compiles new shaders.
- **MoGe-2 on booth renders:** FOV within about 3° (ViT-B) on one image, but metric scale about 2× off. Always anchor the scale to the fitted shell. Test on 5–10 real photos and renders before trusting FOV priors.
- **VP calibration fails gracefully but silently** on images with strong non-Manhattan elements: curved walls, angled panels, truss. Check that the three VP clusters each have enough inlier length, and fall back to the least-squares fit.
- **Licence reminders for paid work:**
  - Avoid Depth Pro (HF `apple-amlr`), UniDepth, DAv2 Base/Large and DA3 Large/Giant (all NC).
  - SAM 3's custom licence has no NC clause but adds trade-control, military and indemnity terms; read it before use.
  - GeoCalib weights are CC BY 4.0. Credit them in internal tooling docs; renders are not adapted material of the model **[E]**.
- **Not verified here:**
  - FLD speed (environment broken).
  - SAM 2.1 / MobileSAM / Grounding DINO / SAM 3 CPU times (estimates from community data).
  - EEVEE with the Vulkan backend (`--gpu-backend vulkan`) on the UHD 620.
  - Whether the *Subprocess* shader compilation option shortens the cold start.
  - fSpy importer on Blender 5.x.

---

## 7. Sources (all accessed 2026-10-14)

**Lines, VPs and calibration**

- OpenCV LSD header note (5.x): https://github.com/opencv/opencv/blob/5.x/modules/imgproc/include/opencv2/imgproc.hpp
- OpenCV releases: https://github.com/opencv/opencv/releases
- FLD: https://github.com/opencv/opencv_contrib/blob/5.x/modules/ximgproc/include/opencv2/ximgproc/fast_line_detector.hpp
- PyPI: https://pypi.org/project/opencv-contrib-python/ · https://pypi.org/project/opencv-contrib-python-headless/ · https://pypi.org/project/lu-vp-detect/ · https://pypi.org/project/pytlsd/ · https://pypi.org/project/pylsd/ · https://pypi.org/project/onnxruntime/ · https://pypi.org/project/transformers/ · https://pypi.org/project/bpy/
- https://github.com/rayryeng/XiaohuLuVPDetection
- https://github.com/WU-CVGL/GlobustVP · https://arxiv.org/abs/2505.04788
- https://github.com/cvg/GeoCalib · https://github.com/cvg/DeepLSD · https://github.com/iago-suarez/ELSED · https://github.com/iago-suarez/pytlsd
- https://github.com/stuffmatic/fSpy · https://github.com/perarnia/fSpy-Blender
- https://www.cs.hunter.cuny.edu/~ioannis/CalibrationFromParallelLines.pdf · https://web.eecs.umich.edu/~justincj/slides/eecs442/WI2021/442_WI2021_singleview.pdf

**Monocular geometry and depth**

- MoGe:
  - https://github.com/microsoft/MoGe (README; `pyproject.toml` at `main` and at `b942f00bdc`; `docs/onnx.md`; `moge/model/v2.py`; `moge/utils/geometry_numpy.py`)
  - https://huggingface.co/Ruicheng/moge-2-vitb-normal-onnx · https://huggingface.co/Ruicheng/moge-2-vits-normal (licence via HF API)
  - https://www.microsoft.com/en-us/research/publication/moge-3-fine-detail-monocular-geometry-estimation-with-self-guided-sparse-volumetric-refinement/
  - [C] https://dev.to/kiarina/estimating-surface-orientation-and-3d-from-one-image-with-moge-2-on-apple-silicon-2n0h (ViT-S CPU 1.26 s on an M1 Max at 384 px)
- Depth Pro:
  - https://github.com/apple/ml-depth-pro (README, LICENSE, `get_pretrained_models.sh`)
  - https://huggingface.co/apple/DepthPro-hf · https://huggingface.co/apple/DepthPro
  - [C] https://huggingface.co/spaces/lightly-ai/ml-depth-pro/discussions/1
- Depth Anything: https://github.com/DepthAnything/Depth-Anything-V2 (+ `metric_depth/`) · https://github.com/ByteDance-Seed/Depth-Anything-3
- https://github.com/YvanYin/Metric3D · https://huggingface.co/onnx-community/metric3d-vit-small
- https://github.com/lpiccinelli-eth/UniDepth · https://huggingface.co/lpiccinelli/unidepth-v2-vits14

**Segmentation**

- SAM 2 / SAM 3: https://github.com/facebookresearch/sam2 · https://github.com/facebookresearch/sam3 (+ LICENSE) · https://huggingface.co/docs/transformers/model_doc/sam3
- [C] https://huggingface.co/Pablopigue/sam2-lite (SAM 2.1 Hiera-T CPU latency)
- https://github.com/ChaoningZhang/MobileSAM · https://github.com/yformer/EfficientSAM
- Grounding: https://github.com/IDEA-Research/GroundingDINO · https://github.com/IDEA-Research/Grounded-SAM-2
- https://huggingface.co/microsoft/Florence-2-base · https://github.com/CASIA-IVA-Lab/FastSAM
- `transformers` model-doc dates: https://github.com/huggingface/transformers/tree/main/docs/source/en/model_doc

**Room layout**

- https://github.com/CYang0515/NonCuboidRoom · https://github.com/zouchuhang/LayoutNet · https://github.com/DavidGillsjo/SRW-Net
- https://github.com/SJingjia/PlaneRecTR · https://github.com/jcliu0428/ZeroPlane · https://github.com/justacar/Plane-DUSt3R
- https://github.com/manycore-research/SpatialLM · https://github.com/sunset1995/HorizonNet · https://github.com/zhigangjiang/LGT-Net

**Blender**

- Manual 5.2: https://docs.blender.org/manual/en/5.2/render/cycles/render_settings/sampling.html · …/performance.html · …/light_paths.html
- Manual 5.2: https://docs.blender.org/manual/en/5.2/render/workbench/index.html · https://docs.blender.org/manual/en/5.2/render/eevee/index.html
- Manual 5.2: https://docs.blender.org/manual/en/5.2/advanced/command_line/arguments.html · https://docs.blender.org/manual/en/5.2/editors/preferences/system.html
- Manual source: https://projects.blender.org/blender/blender-manual (branch `blender-v5.2-release`)
- API 5.2: https://docs.blender.org/api/5.2/info_gotchas_threading.html · https://docs.blender.org/api/5.2/bpy.app.timers.html
- https://www.blender.org/download/requirements/ · https://github.com/ahujasid/blender-mcp
