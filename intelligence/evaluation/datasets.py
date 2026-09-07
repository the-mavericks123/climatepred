"""
Dataset repository, benchmark generator, and split manager for Phase 10 Evaluation.
Guarantees clean, non-leaking train/calibration/test separation and immutable dataset storage.
"""

import hashlib
import json
import math
from typing import Dict, List, Optional, Tuple
from intelligence.evaluation.types import (
    DatasetType,
    EvaluationDataset,
    EvaluationObservation,
    GroundTruthRecord,
)


class DatasetRegistry:
    """
    In-memory registry and builder for versioned benchmark datasets.
    """

    _datasets: Dict[str, EvaluationDataset] = {}

    @classmethod
    def register_dataset(cls, dataset: EvaluationDataset) -> None:
        """Stores a dataset and computes its canonical provenance hash."""
        if not dataset.provenance_hash:
            payload = {
                "dataset_id": dataset.dataset_id,
                "version": dataset.version,
                "domain": dataset.domain,
                "dataset_type": dataset.dataset_type.value,
                "sample_count": len(dataset.observations),
                "obs_ids": [o.sample_id for o in sorted(dataset.observations, key=lambda x: x.sample_id)],
            }
            dataset.provenance_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        cls._datasets[dataset.dataset_id] = dataset

    @classmethod
    def get_dataset(cls, dataset_id: str) -> Optional[EvaluationDataset]:
        """Retrieves a dataset by ID, lazily initializing built-in benchmarks if needed."""
        if dataset_id not in cls._datasets:
            cls._ensure_default_benchmarks()
        return cls._datasets.get(dataset_id)

    @classmethod
    def split_dataset(
        cls,
        dataset: EvaluationDataset,
        train_ratio: float = 0.50,
        cal_ratio: float = 0.25,
        test_ratio: float = 0.25,
    ) -> Tuple[EvaluationDataset, EvaluationDataset, EvaluationDataset]:
        """
        Deterministically partitions observations and ground truth into Train, Calibration, and Test splits.
        Enforces strict zero-leakage separation.
        """
        assert math.isclose(train_ratio + cal_ratio + test_ratio, 1.0, rel_tol=1e-3), "Split ratios must sum to 1.0"

        # Pair observations with matching ground truth
        gt_map = {gt.sample_id: gt for gt in dataset.ground_truth}
        paired = [(obs, gt_map.get(obs.sample_id)) for obs in dataset.observations]

        # Deterministic sorting by sample_id
        paired.sort(key=lambda x: x[0].sample_id)

        n = len(paired)
        n_train = int(n * train_ratio)
        n_cal = int(n * cal_ratio)

        train_pairs = paired[:n_train]
        cal_pairs = paired[n_train:n_train + n_cal]
        test_pairs = paired[n_train + n_cal:]

        def _build_split(pairs, split_name: str) -> EvaluationDataset:
            obs_list = [p[0] for p in pairs]
            gt_list = [p[1] for p in pairs if p[1] is not None]
            split_ds = EvaluationDataset(
                dataset_id=f"{dataset.dataset_id}-{split_name}",
                version=dataset.version,
                dataset_type=dataset.dataset_type,
                description=f"{split_name.upper()} split of {dataset.dataset_id}",
                domain=dataset.domain,
                observations=obs_list,
                ground_truth=gt_list,
            )
            payload = {
                "parent_id": dataset.dataset_id,
                "split": split_name,
                "sample_count": len(obs_list),
                "obs_ids": [o.sample_id for o in obs_list],
            }
            split_ds.provenance_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
            return split_ds

        return _build_split(train_pairs, "train"), _build_split(cal_pairs, "calibration"), _build_split(test_pairs, "test")

    @classmethod
    def _ensure_default_benchmarks(cls) -> None:
        """Initializes standard synthetic evaluation benchmarks."""
        if "EVAL-FLOOD-SYNTHETIC-001" not in cls._datasets:
            cls.register_dataset(cls._build_synthetic_flood_benchmark())
        if "EVAL-HEAT-SYNTHETIC-001" not in cls._datasets:
            cls.register_dataset(cls._build_synthetic_heat_benchmark())
        if "EVAL-PRED-SYNTHETIC-001" not in cls._datasets:
            cls.register_dataset(cls._build_synthetic_prediction_benchmark())

    @classmethod
    def _build_synthetic_flood_benchmark(cls) -> EvaluationDataset:
        """Builds a deterministic 100-sample synthetic flood evaluation dataset."""
        observations = []
        ground_truth = []
        for i in range(100):
            sample_id = f"SAMP-FLOOD-{i:03d}"
            # Linear ramp across inputs
            rain = round(i * 1.0, 1)        # 0.0 to 99.0 mm/hr
            water = round(i * 0.15, 2)      # 0.0 to 14.85 m
            soil = round(30.0 + i * 0.6, 1) # 30.0 to 89.4 %

            # Ground truth: flood event triggers if rain > 50 and water > 7.0
            is_flood = 1 if (rain >= 50.0 and water >= 7.0) else 0
            true_severity = round(min(1.0, (rain / 100.0) * 0.4 + (water / 15.0) * 0.35 + ((soil - 30.0) / 70.0) * 0.25), 4)

            observations.append(EvaluationObservation(
                sample_id=sample_id,
                features={"rainfall_mmhr": rain, "water_level_m": water, "soil_moisture_pct": soil},
                metadata={"synthetic_index": i},
            ))
            ground_truth.append(GroundTruthRecord(
                sample_id=sample_id,
                binary_label=is_flood,
                continuous_target=true_severity,
                categorical_class="HIGH" if is_flood else "NORMAL",
            ))

        return EvaluationDataset(
            dataset_id="EVAL-FLOOD-SYNTHETIC-001",
            version="1.0",
            dataset_type=DatasetType.SYNTHETIC,
            description="Synthetic 100-sample flood benchmark spanning nominal to critical hydrological parameters.",
            domain="flood",
            observations=observations,
            ground_truth=ground_truth,
        )

    @classmethod
    def _build_synthetic_heat_benchmark(cls) -> EvaluationDataset:
        """Builds a deterministic 100-sample synthetic heat evaluation dataset."""
        observations = []
        ground_truth = []
        for i in range(100):
            sample_id = f"SAMP-HEAT-{i:03d}"
            temp = round(20.0 + i * 0.3, 1)  # 20.0 to 49.7 C
            rh = round(30.0 + (i % 50) * 1.0, 1)
            is_heat = 1 if temp >= 38.0 and rh >= 45.0 else 0

            observations.append(EvaluationObservation(
                sample_id=sample_id,
                features={"temperature_c": temp, "humidity_pct": rh},
            ))
            ground_truth.append(GroundTruthRecord(
                sample_id=sample_id,
                binary_label=is_heat,
                continuous_target=round(max(0.0, min(1.0, (temp - 25.0) / 25.0)), 4),
            ))

        return EvaluationDataset(
            dataset_id="EVAL-HEAT-SYNTHETIC-001",
            version="1.0",
            dataset_type=DatasetType.SYNTHETIC,
            description="Synthetic 100-sample heat benchmark.",
            domain="heat",
            observations=observations,
            ground_truth=ground_truth,
        )

    @classmethod
    def _build_synthetic_prediction_benchmark(cls) -> EvaluationDataset:
        """Builds a deterministic 60-sample prediction benchmark with horizon targets."""
        observations = []
        ground_truth = []
        for i in range(60):
            sample_id = f"SAMP-PRED-{i:03d}"
            base_val = round(0.20 + i * 0.01, 3)
            # Simulated history of 6 points
            history = [round(base_val - j * 0.02, 3) for j in range(6, 0, -1)]

            # Target at +30m, +60m, +360m
            gt_30m = round(min(1.0, base_val + 0.05), 3)
            gt_60m = round(min(1.0, base_val + 0.10), 3)
            gt_360m = round(min(1.0, base_val + 0.20), 3)

            observations.append(EvaluationObservation(
                sample_id=sample_id,
                features={"history": history, "current": base_val, "hazard": "flood"},
            ))
            ground_truth.append(GroundTruthRecord(
                sample_id=sample_id,
                continuous_target=gt_60m,
                metadata={"horizon_targets": {"30": gt_30m, "60": gt_60m, "360": gt_360m}},
            ))

        return EvaluationDataset(
            dataset_id="EVAL-PRED-SYNTHETIC-001",
            version="1.0",
            dataset_type=DatasetType.SYNTHETIC,
            description="Synthetic 60-sample prediction benchmark evaluating +30m, +60m, +360m horizons.",
            domain="prediction",
            observations=observations,
            ground_truth=ground_truth,
        )
