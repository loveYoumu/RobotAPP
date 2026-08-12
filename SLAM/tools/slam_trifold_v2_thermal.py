#!/usr/bin/env python3
"""Build three-active-tier HotSpot inputs for the TriFold-3D v2 SLAM run."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path


CPU_ACTIVE_W = {"t2_cpu_cluster": 12.85, "t1_cpu_llc": 7.42,
                "t0_hbm_system": 4.36, "t0_system": 0.03}
CPU_IDLE_W = {"t2_cpu_cluster": 2.10, "t1_cpu_llc": 2.40,
              "t0_hbm_system": 3.40, "t0_system": 0.03}
BACKGROUND_W = {"t0_dma_iommu": 0.50, "t0_io_phy": 0.50,
                "t0_pmu_ras": 1.00, "t1_shared_sram": 0.20}


def read_gpu_trace(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as stream:
        raw = [row for row in csv.reader(stream) if any(x.strip() for x in row)]
    header = [x.strip() for x in raw[0] if x.strip()]
    rows = []
    for row in raw[1:]:
        values = [x.strip() for x in row]
        while values and not values[-1]:
            values.pop()
        rows.append([float(x) for x in values[:len(header)]])
    if header[0].lower() != "power":
        raise ValueError("GPUWattch trace must start with a total-power column")
    return header[1:], [row[1:] for row in rows]


def aggregate_gpu(units, row):
    power = dict(zip(units, row))

    def total(names):
        return sum(power.get(name, 0.0) for name in names)

    return {
        "t2_gpu_compute": total(["SPP", "SFUP", "FPUP"]),
        "t2_gpu_control": total(["IBP", "SCHEDP", "PIPEP", "IDLE_COREP",
                                 "CONST_DYNAMICP", "CONSTP", "STATICP"]),
        "t2_gpu_local_mem": total(["ICP", "DCP", "TCP", "CCP", "SHRDP", "RFP"]),
        "t1_gpu_l2": total(["L2CP"]),
        "t1_noc": total(["NOCP"]),
        "t0_hbm_system": total(["MCP", "DRAMP"]),
    }


def write_flp(path: Path, blocks):
    with path.open("w", encoding="utf-8") as stream:
        for name, width_mm, height_mm, x_mm, y_mm in blocks:
            stream.write(f"{name}\t{width_mm/1000:.6f}\t{height_mm/1000:.6f}"
                         f"\t{x_mm/1000:.6f}\t{y_mm/1000:.6f}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gpu-trace", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--gpu-cycles", type=int, default=4_583_843)
    parser.add_argument("--cpu-cycles", type=int, default=36_017_916)
    args = parser.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    units, gpu_rows = read_gpu_trace(Path(args.gpu_trace))
    gpu_agg = [aggregate_gpu(units, row) for row in gpu_rows]
    cpu_repeat = max(1, round(args.cpu_cycles / args.gpu_cycles))
    idle_gpu = {key: min(row[key] for row in gpu_agg) for key in gpu_agg[0]}

    t0 = [
        ("t0_hbm_system", 8, 8, 0, 0),
        ("t0_dma_iommu", 8, 8, 0, 8),
        ("t0_io_phy", 4, 8, 8, 0),
        ("t0_pmu_ras", 4, 8, 12, 0),
        ("t0_system", 8, 8, 8, 8),
    ]
    t1 = [
        ("t1_cpu_llc", 6, 8, 0, 0),
        ("t1_npu_sram", 6, 8, 0, 8),
        ("t1_gpu_l2", 6, 8, 6, 0),
        ("t1_shared_sram", 6, 8, 6, 8),
        ("t1_noc", 4, 16, 12, 0),
    ]
    t2 = [
        ("t2_cpu_cluster", 6, 8, 0, 0),
        ("t2_npu_cluster", 6, 8, 0, 8),
        ("t2_gpu_compute", 10, 8, 6, 0),
        ("t2_gpu_control", 5, 8, 6, 8),
        ("t2_gpu_local_mem", 5, 8, 11, 8),
    ]
    tim = [("tim", 16, 16, 0, 0)]
    write_flp(out / "tier0_base.flp", t0)
    write_flp(out / "tier1_memory.flp", t1)
    write_flp(out / "tier2_compute.flp", t2)
    write_flp(out / "tim.flp", tim)

    headers = [x[0] for x in t0 + t1 + t2]
    rows = []
    phases = []

    def emit(gpu, cpu, phase):
        values = {
            "t0_hbm_system": gpu["t0_hbm_system"] + cpu["t0_hbm_system"],
            "t0_dma_iommu": BACKGROUND_W["t0_dma_iommu"],
            "t0_io_phy": BACKGROUND_W["t0_io_phy"],
            "t0_pmu_ras": BACKGROUND_W["t0_pmu_ras"],
            "t0_system": cpu["t0_system"],
            "t1_cpu_llc": cpu["t1_cpu_llc"],
            "t1_npu_sram": 0.0,
            "t1_gpu_l2": gpu["t1_gpu_l2"],
            "t1_shared_sram": BACKGROUND_W["t1_shared_sram"],
            "t1_noc": gpu["t1_noc"],
            "t2_cpu_cluster": cpu["t2_cpu_cluster"],
            "t2_npu_cluster": 0.0,
            "t2_gpu_compute": gpu["t2_gpu_compute"],
            "t2_gpu_control": gpu["t2_gpu_control"],
            "t2_gpu_local_mem": gpu["t2_gpu_local_mem"],
        }
        rows.append([values[name] for name in headers])
        phases.append((len(rows) - 1, phase, sum(values.values())))

    for gpu in gpu_agg:
        emit(gpu, CPU_IDLE_W, "gpu_orb")
    for _ in range(cpu_repeat):
        for _sample in gpu_agg:
            emit(idle_gpu, CPU_ACTIVE_W, "cpu_tracking_lba")

    with (out / "trifold_v2_3d.ptrace").open("w", encoding="utf-8") as stream:
        stream.write("\t".join(headers) + "\n")
        for row in rows:
            stream.write("\t".join(f"{value:.6f}" for value in row) + "\n")

    lcf = """# TriFold-3D v2: package side (T0) to heat-sink side (T2)
0
Y
Y
1.75e6
0.01
0.000100
tier0_base.flp

1
Y
N
4e6
0.25
0.000020
tim.flp

2
Y
Y
1.75e6
0.01
0.000050
tier1_memory.flp

3
Y
N
4e6
0.25
0.000020
tim.flp

4
Y
Y
1.75e6
0.01
0.000050
tier2_compute.flp

5
Y
N
4e6
0.25
0.000020
tim.flp
"""
    (out / "trifold_v2_3d.lcf").write_text(lcf, encoding="utf-8")

    with (out / "power_summary.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["sample", "phase", "package_power_w"])
        writer.writerows(phases)

    package = [sum(row) for row in rows]
    meta = {
        "run_location": "cluster",
        "architecture": "TriFold-3D v2",
        "gpu_trace": str(Path(args.gpu_trace).resolve()),
        "gpu_trace_samples": len(gpu_rows),
        "cpu_repeat": cpu_repeat,
        "combined_samples": len(rows),
        "cycles": {"gpu_orb": args.gpu_cycles, "slam_converged": args.cpu_cycles},
        "measured_inputs": ["GPUWattch component trace", "Sniper/McPAT CPU totals"],
        "engineering_assumptions": {
            "npu_dynamic_w": 0.0,
            "reason": "classic ORB-SLAM3 has no neural-network operator",
            "background_power_w": BACKGROUND_W,
            "floorplan": "three 16x16 mm active tiers with two 20um TIM layers and top TIM",
        },
        "average_package_power_w": sum(package) / len(package),
        "peak_package_power_w": max(package),
    }
    (out / "model_assumptions.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
