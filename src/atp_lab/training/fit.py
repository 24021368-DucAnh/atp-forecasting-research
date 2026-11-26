"""Fixed synthetic logistic fit and disjoint mirrored Platt calibration."""
from dataclasses import asdict, replace
import warnings

from .artifact import (LogisticParameters, logit, parameters_from_payload, swap)
from .dataset import TrainingDataset, _validate_example, feature_vector


def fit_logistic(data: TrainingDataset) -> LogisticParameters:
    """Low-level fit of already verified synthetic dataset, not an import API.

    The registry is the only supported training entrypoint: it builds
    and revalidates the dataset from immutable S5 records.
    """
    import numpy as np
    from sklearn.exceptions import ConvergenceWarning
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from threadpoolctl import threadpool_limits

    if type(data) is not TrainingDataset:
        raise ValueError("typed synthetic dataset required")
    for rows in (data.fit, data.calibration):
        if not rows or {x.outcome_a for x in rows} != {0, 1}:
            raise ValueError("both canonical classes required")
        for row in rows:
            _validate_example(row)
    if ({x.match_id for x in data.fit} & {x.match_id for x in data.calibration}
            or {x.event_id for x in data.fit} & {x.event_id for x in data.calibration}):
        raise ValueError("fit/calibration overlap")
    x = [feature_vector(row.values) for row in data.fit]
    y = [row.outcome_a for row in data.fit]
    xx = np.asarray(x + [swap(v) for v in x], dtype=float)
    yy = np.asarray(y + [1 - v for v in y], dtype=int)

    def estimator():
        return LogisticRegression(C=1., solver="lbfgs", max_iter=2000, random_state=29)

    with warnings.catch_warnings(), threadpool_limits(limits=1):
        warnings.simplefilter("error", ConvergenceWarning)
        scaler = StandardScaler().fit(xx)
        model = estimator().fit(scaler.transform(xx), yy)
        if list(model.classes_) != [0, 1]:
            raise ValueError("invalid fitted class order")
        provisional = LogisticParameters(tuple(map(float, scaler.mean_)),
            tuple(map(float, scaler.scale_)), tuple(map(float, model.coef_[0])),
            float(model.intercept_[0]), 1., 0.)
        provisional = parameters_from_payload(asdict(provisional))
        p = [provisional.raw_probability(row.values) for row in data.calibration]
        labels = [row.outcome_a for row in data.calibration]
        logits = np.asarray([logit(v) for v in p] + [logit(1. - v) for v in p],
                            dtype=float).reshape(-1, 1)
        platt = estimator().fit(logits, np.asarray(labels + [1 - v for v in labels], dtype=int))
        if list(platt.classes_) != [0, 1]:
            raise ValueError("invalid calibration class order")
        return parameters_from_payload(asdict(replace(provisional,
            platt_slope=float(platt.coef_[0, 0]), platt_intercept=float(platt.intercept_[0]))))
