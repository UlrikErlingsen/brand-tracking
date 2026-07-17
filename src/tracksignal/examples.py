"""Original fictional tracking data for demonstrations and tests."""

from __future__ import annotations

import numpy as np
import pandas as pd


METRICS = (
    ("Awareness", "Funnel", "binary", 0.03, "Single tracker item; fictional wording owned by the example author"),
    ("Familiarity", "Funnel", "rating", 0.20, "Single 1–7 tracker item; fictional wording owned by the example author"),
    ("Consideration", "Funnel", "binary", 0.03, "Single tracker item; fictional wording owned by the example author"),
    ("Recent usage", "Funnel", "binary", 0.03, "Single tracker item; fictional wording owned by the example author"),
    ("First-choice loyalty", "Funnel", "binary", 0.03, "Single tracker item; fictional wording owned by the example author"),
    ("Innovative attribute ownership", "Associations", "binary", 0.03, "Single tracker item; fictional wording owned by the example author"),
    ("Association favourability", "Associations", "rating", 0.20, "Single 1–7 tracker item; fictional wording owned by the example author"),
    ("Perceived uniqueness", "Associations", "rating", 0.20, "Single 1–7 tracker item; fictional wording owned by the example author"),
    ("Trust", "Relationship", "rating", 0.20, "Single 1–7 tracker item; fictional wording owned by the example author"),
    ("Perceived quality", "Relationship", "rating", 0.20, "Single 1–7 tracker item; fictional wording owned by the example author"),
    (
        "Attachment construct",
        "Relationship",
        "construct",
        0.20,
        "MeasureSignal evidence pack MS-DEMO-001; synthetic demonstration only",
    ),
    ("Reputation", "Relationship", "rating", 0.20, "Single 1–7 tracker item; fictional wording owned by the example author"),
)


def make_demo_data(seed: int = 24052026, respondents_per_wave: int = 180) -> pd.DataFrame:
    """Create an entirely fictional repeated-cross-section tracker with within-wave brand ratings."""
    rng = np.random.default_rng(seed)
    waves = ("2025 Q3", "2025 Q4", "2026 Q1")
    brands = ("Northstar", "Harbor", "Lumen")
    segments = ("Core category buyers", "Light category buyers")
    brand_base = {"Northstar": 0.35, "Harbor": 0.05, "Lumen": -0.20}
    wave_shift = {"2025 Q3": 0.00, "2025 Q4": 0.08, "2026 Q1": 0.16}
    rows: list[dict[str, object]] = []
    for wave_index, wave in enumerate(waves):
        for respondent_index in range(respondents_per_wave):
            respondent_id = f"W{wave_index + 1}-{respondent_index + 1:04d}"
            segment = rng.choice(segments, p=[0.58, 0.42])
            segment_shift = 0.18 if segment == "Core category buyers" else -0.12
            weight = float(np.clip(rng.lognormal(mean=0, sigma=0.16), 0.65, 1.55))
            person = rng.normal(0, 0.35)
            for brand in brands:
                latent = brand_base[brand] + segment_shift + person
                if brand == "Northstar":
                    latent += wave_shift[wave]
                elif brand == "Lumen":
                    latent -= wave_shift[wave] * 0.25
                for metric_index, (metric, family, kind, threshold, source) in enumerate(METRICS):
                    metric_shift = (metric_index % 4 - 1.5) * 0.06
                    if kind == "binary":
                        logit = -0.25 + latent + metric_shift
                        probability = 1 / (1 + np.exp(-logit))
                        value = float(rng.binomial(1, probability))
                    else:
                        value = float(np.clip(4.0 + 1.05 * latent + metric_shift + rng.normal(0, 1.0), 1, 7))
                    rows.append(
                        {
                            "respondent_id": respondent_id,
                            "wave": wave,
                            "segment": segment,
                            "brand": brand,
                            "metric": metric,
                            "metric_kind": kind,
                            "family": family,
                            "value": round(value, 4),
                            "weight": round(weight, 5),
                            "practical_threshold": threshold,
                            "measurement_source": source,
                        }
                    )
    return pd.DataFrame(rows)


def make_starter_template() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "respondent_id": "R001",
                "wave": "Wave 1",
                "segment": "Segment A",
                "brand": "Brand A",
                "metric": "Awareness",
                "metric_kind": "binary",
                "family": "Funnel",
                "value": 1,
                "weight": 1.0,
                "practical_threshold": 0.03,
                "measurement_source": "Single survey item; add the questionnaire/item reference",
            },
            {
                "respondent_id": "R001",
                "wave": "Wave 1",
                "segment": "Segment A",
                "brand": "Brand B",
                "metric": "Awareness",
                "metric_kind": "binary",
                "family": "Funnel",
                "value": 0,
                "weight": 1.0,
                "practical_threshold": 0.03,
                "measurement_source": "Single survey item; add the questionnaire/item reference",
            },
        ]
    )
