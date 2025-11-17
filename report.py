# report.py - batch scanning and report generation (Markdown + JSON)

import os
from concurrent.futures import ProcessPoolExecutor
from typing import Any, Dict, List

from tqdm import tqdm

from analysis import _analyze_path, analyze_file, load_thresholds, is_near_silence, verdict_from_marks, format_marks
from utils import VERSION, fmt, json_dump


def cmd_batch(args):
    thresholds = load_thresholds(args.thresholds) if args.thresholds else {}

    rows: List[Dict[str, Any]] = []
    exts = (".wav", ".aiff", ".aif", ".flac", ".m4a", ".mp3")
    files = [
        os.path.join(args.dir, fn)
        for fn in sorted(os.listdir(args.dir))
        if fn.lower().endswith(exts)
    ]

    if getattr(args, "jobs", 1) > 1 and len(files) > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            for r in tqdm(ex.map(_analyze_path, files), total=len(files)):
                rows.append(r)
    else:
        for p in tqdm(files):
            rows.append(analyze_file(p))

    # Ensure output directory exists
    out_dir = os.path.dirname(args.out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Write Markdown report (including optional per-channel tables)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("# Audio QA Report\n\n")
        f.write("| file | sr | peak(dBFS) | TP(dBFS) | rms(dBFS) | crest(dB) | "
                "LUFS | LUFS-S | LUFS-M | LRA | SNR(dB) | verdict | reason |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|\n")

        pass_n = fail_n = warn_n = 0
        for r in rows:
            marks = format_marks(r, thresholds)

            if is_near_silence(r):
                verdict = "FAIL"
                reason = "near-silence"
            else:
                reason = ""
                fails = [k for k, v in marks.items() if v == "FAIL"]
                warns = [k for k, v in marks.items() if v == "WARN"]
                if fails:
                    reason = ",".join(fails)
                elif warns:
                    reason = ",".join(warns)
                verdict = verdict_from_marks(marks)

            if verdict == "PASS":
                pass_n += 1
            elif verdict == "FAIL":
                fail_n += 1
            else:
                warn_n += 1

            lufs_str = fmt(r.get("lufs"))
            lufs_s_str = fmt(r.get("lufs_s"))
            lufs_m_str = fmt(r.get("lufs_m"))
            lra_str = fmt(r.get("lra"))
            snr_str = fmt(r.get("snr_db"))
            tp_str = fmt(r.get("true_peak_dbfs"))
            crest_str = fmt(r.get("crest_db"))
            peak_str = fmt(r.get("peak_dbfs"))
            rms_str = fmt(r.get("rms_dbfs"))

            f.write(
                f"| {r['file']} | {r['sr']} | {peak_str} | {tp_str} | {rms_str} | "
                f"{crest_str} | {lufs_str} | {lufs_s_str} | {lufs_m_str} | "
                f"{lra_str} | {snr_str} | {verdict} | {reason} |\n"
            )

        # Summary + Notes
        f.write(f"\n**Summary**: PASS {pass_n} / FAIL {fail_n} / WARN {warn_n}\n\n")
        f.write("## Notes & Assumptions\n")
        f.write("- dBFS uses 1.0 as full scale; the main table down-mixes multi-channel audio, with per-channel details in the section below.\n")
        f.write("- LUFS is computed via pyloudnorm (R128/BS.1770); the report includes Integrated, Short-term, Momentary and LRA where available.\n")
        f.write("- True Peak is approximated via 4× oversampling to highlight potential inter-sample clipping.\n")
        f.write("- SNR uses a hybrid estimator: time-domain percentile noise when clear silences exist, otherwise a narrow-band spectral estimate; non-applicable cases show NA.\n")
        f.write("- A “silence gate” enforces RMS < -80 dBFS or Peak < -60 dBFS as an immediate FAIL (missing or extremely low-level content).\n")
        f.write("- Rough intuition: louder → LUFS closer to 0; cleaner → higher SNR; more squashed → smaller crest factor.\n")

        # Per-channel tables (for multi-channel content)
        has_multi = any(r.get("channels") for r in rows)
        if has_multi:
            f.write("\n## Per-channel metrics (if multi-channel)\n")
            for r in rows:
                chans = r.get("channels")
                if not chans:
                    continue
                f.write(f"\n**{r['file']}** (channels={len(chans)})\n\n")
                f.write("| ch | peak(dBFS) | rms(dBFS) | crest(dB) | LUFS | LRA |\n")
                f.write("|---:|---:|---:|---:|---:|---:|\n")
                for ch in chans:
                    f.write(
                        f"| {ch['ch']} | {fmt(ch.get('peak_dbfs'))} | {fmt(ch.get('rms_dbfs'))} | "
                        f"{fmt(ch.get('crest_db'))} | {fmt(ch.get('lufs'))} | {fmt(ch.get('lra'))} |\n"
                    )
                lr_corr = fmt(r.get("lr_corr"))
                imb = fmt(r.get("channel_imbalance_db"))
                silent = r.get("silent_channels", [])
                f.write(f"\n- LR correlation: {lr_corr}\n- Channel imbalance (dB): {imb}\n- Silent channels: {silent}\n")

    # Optional JSON export (once per batch)
    if getattr(args, "out_json", None):
        try:
            jdir = os.path.dirname(args.out_json)
            if jdir:
                os.makedirs(jdir, exist_ok=True)
            payload = {
                "version": VERSION,
                "dir": args.dir,
                "thresholds": args.thresholds,
                "summary": {"pass": pass_n, "fail": fail_n, "warn": warn_n},
                "rows": rows,
            }
            with open(args.out_json, "w", encoding="utf-8") as jf:
                jf.write(json_dump(payload))
        except Exception as e:
            print(f"[WARN] failed to write JSON report: {e}")

    # Exit with non-zero status if any file FAILs (for CI)
    if fail_n > 0:
        import sys
        sys.exit(1)

def run_batch(args):
    """CLI-friendly entry point used by main.py."""
    return cmd_batch(args)