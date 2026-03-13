"""Retrain regime classifier with multi-scale zigzag labels.

Uses TrainingPipeline static methods for indicators, then
builds fuzzy features using FuzzySetDefinition directly.
"""
import asyncio
from pathlib import Path

import numpy as np


async def train():
    import datetime
    import json
    import shutil

    import torch
    import yaml

    from ktrdr.config.models import FuzzySetDefinition
    from ktrdr.data.repository import DataRepository
    from ktrdr.fuzzy.engine import FuzzyEngine
    from ktrdr.neural.models.mlp import MLPTradingModel
    from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
    from ktrdr.training.multi_scale_regime_labeler import MultiScaleRegimeLabeler
    from ktrdr.training.training_pipeline import TrainingPipeline

    # Load raw config
    config_path = Path("/app/strategies/regime_classifier_seed_v1.yaml")
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    labels_cfg = raw["training"]["labels"]
    print(f"Strategy: {raw['name']}", flush=True)
    print(
        f"macro_atr_mult={labels_cfg.get('macro_atr_mult', 3.0)}, "
        f"micro_atr_mult={labels_cfg.get('micro_atr_mult', 1.0)}, "
        f"atr_period={labels_cfg.get('atr_period', 14)}",
        flush=True,
    )

    # Load data
    repo = DataRepository()
    data = repo.load_from_cache(
        symbol="EURUSD", timeframe="1h",
        start_date="2019-01-01", end_date="2024-01-01",
    )
    print(f"Data: {len(data)} bars", flush=True)

    # Generate labels using multi-scale zigzag
    labeler = MultiScaleRegimeLabeler(
        macro_atr_mult=labels_cfg.get("macro_atr_mult", 3.0),
        micro_atr_mult=labels_cfg.get("micro_atr_mult", 1.0),
        atr_period=labels_cfg.get("atr_period", 14),
        vol_lookback=labels_cfg.get("vol_lookback", 120),
        vol_crisis_threshold=labels_cfg.get("vol_crisis_threshold", 2.0),
        progression_tolerance=labels_cfg.get("progression_tolerance", 0.5),
    )
    labels = labeler.generate_labels(data)
    valid_labels = labels.dropna()
    names = ["TRENDING_UP", "TRENDING_DOWN", "RANGING", "VOLATILE"]

    print(f"\nLabel distribution ({len(valid_labels)} valid bars):", flush=True)
    for i, name in enumerate(names):
        count = (valid_labels == i).sum()
        pct = 100 * count / len(valid_labels)
        print(f"  {name}: {count} ({pct:.1f}%)", flush=True)

    # Step 1: Compute indicators
    multi_tf_data = {"1h": data}
    indicator_results = TrainingPipeline.calculate_indicators(
        price_data=multi_tf_data,
        indicator_configs=raw["indicators"],
    )
    print(f"Indicators computed: {indicator_results['1h'].shape}", flush=True)

    # Step 2: Generate fuzzy memberships using v3 FuzzySetDefinition
    v3_config = {}
    for fs_id, fs_cfg in raw["fuzzy_sets"].items():
        v3_config[fs_id] = FuzzySetDefinition(**fs_cfg)

    fuzzy_engine = FuzzyEngine(v3_config)
    fuzzy_results = fuzzy_engine.generate_multi_timeframe_memberships(
        indicator_results, v3_config
    )
    print(f"Fuzzy features: {fuzzy_results['1h'].shape}", flush=True)

    # Step 3: Prepare features using FuzzyNeuralProcessor
    processor = FuzzyNeuralProcessor(raw)
    features_tensor, feature_names_list = processor.prepare_multi_timeframe_input(
        fuzzy_results
    )
    print(f"Features tensor: {features_tensor.shape}", flush=True)
    print(f"Feature names: {len(feature_names_list)}", flush=True)

    # Align labels with features
    label_arr = labels.values
    n_features = len(features_tensor)
    n_labels = len(label_arr)

    if n_features < n_labels:
        label_arr = label_arr[n_labels - n_features:]
    elif n_labels < n_features:
        features_tensor = features_tensor[:n_labels]

    valid_mask = ~np.isnan(label_arr[:len(features_tensor)])
    X = features_tensor[valid_mask]
    y_np = label_arr[:len(features_tensor)][valid_mask].astype(np.int64)
    y = torch.tensor(y_np)
    print(f"Valid samples: {len(X)}", flush=True)

    # Split
    n = len(X)
    train_n = int(0.7 * n)
    val_n = int(0.15 * n)
    X_train, y_train = X[:train_n], y[:train_n]
    X_val, y_val = X[train_n:train_n + val_n], y[train_n:train_n + val_n]
    X_test, y_test = X[train_n + val_n:], y[train_n + val_n:]
    print(f"Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}", flush=True)

    # Create model
    input_size = X.shape[1]
    model_cfg = raw.get("model", {}).get("architecture", {})
    hidden_layers = model_cfg.get("hidden_layers", [64, 32])
    dropout = model_cfg.get("dropout", 0.2)
    config = {
        "architecture": {
            "hidden_layers": hidden_layers,
            "dropout": dropout,
            "activation": "relu",
        },
        "num_classes": 4,
    }
    model_wrapper = MLPTradingModel(config)
    nn_model = model_wrapper.build_model(input_size)
    print(f"Model: in={input_size}, hidden={hidden_layers}, out=4", flush=True)

    # Compute class weights for balanced training
    class_counts = np.bincount(y_np, minlength=4)
    total_samples = len(y_np)
    # Inverse frequency weighting: rare classes get higher weight
    class_weights = total_samples / (4.0 * class_counts.astype(np.float64))
    # Cap extreme weights (VOLATILE is very rare)
    class_weights = np.minimum(class_weights, 10.0)
    weights_tensor = torch.tensor(class_weights, dtype=torch.float32)
    print(f"Class weights: {dict(zip(names, class_weights.tolist()))}", flush=True)

    # Train with class-weighted loss
    import torch.nn as tnn
    optimizer = torch.optim.Adam(nn_model.parameters(), lr=0.001)
    criterion = tnn.CrossEntropyLoss(weight=weights_tensor)

    best_val_acc = 0.0
    best_state = None
    for epoch in range(150):
        nn_model.train()
        # Mini-batch training
        batch_size = 64
        indices = torch.randperm(len(X_train))
        epoch_loss = 0.0
        correct = 0
        total = 0

        for start in range(0, len(X_train), batch_size):
            batch_idx = indices[start:start + batch_size]
            X_batch = X_train[batch_idx]
            y_batch = y_train[batch_idx]

            optimizer.zero_grad()
            outputs = nn_model(X_batch)
            loss = criterion(outputs, y_batch)
            loss.backward()
            optimizer.step()

            epoch_loss += loss.item() * len(X_batch)
            _, predicted = torch.max(outputs, 1)
            correct += (predicted == y_batch).sum().item()
            total += len(y_batch)

        # Validation
        nn_model.eval()
        with torch.no_grad():
            val_out = nn_model(X_val)
            criterion(val_out, y_val).item()  # compute for gradient check only
            _, val_pred = torch.max(val_out, 1)
            val_acc = (val_pred == y_val).float().mean().item()

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_state = {k: v.clone() for k, v in nn_model.state_dict().items()}

        if epoch % 30 == 0 or epoch == 149:
            train_acc = correct / total
            print(f"Epoch {epoch}: loss={epoch_loss/total:.4f} train_acc={train_acc:.4f} val_acc={val_acc:.4f}", flush=True)

    # Restore best model
    if best_state is not None:
        nn_model.load_state_dict(best_state)
    print(f"\nTraining complete! Best val accuracy: {best_val_acc:.4f}", flush=True)

    # Evaluate
    nn_model.eval()
    with torch.no_grad():
        outputs = nn_model(X_test)
        _, predicted = torch.max(outputs, 1)
        accuracy = (predicted == y_test).float().mean().item()
        print(f"Test accuracy: {accuracy:.4f}", flush=True)

        unique_pred, pred_counts = np.unique(predicted.numpy(), return_counts=True)
        total_pred = pred_counts.sum()
        print("Prediction distribution on test set:", flush=True)
        for u, c in zip(unique_pred, pred_counts):
            print(f"  {names[int(u)]}: {c} ({100*c/total_pred:.1f}%)", flush=True)

    # Save model — remove old symlink and create real directory
    model_base = Path("/app/models/regime_classifier_seed")
    model_dir = model_base / "1h_v1"
    # Clean up old symlink if present
    latest_link = model_base / "1h_latest"
    if latest_link.is_symlink():
        latest_link.unlink()
    if model_dir.exists():
        shutil.rmtree(model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)

    torch.save(nn_model.state_dict(), model_dir / "model.pt")
    torch.save(nn_model, model_dir / "model_full.pt")

    # metadata.json (legacy format for backward compatibility)
    metadata = {
        "strategy_name": "regime_classifier_seed",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "created_at": datetime.datetime.now().isoformat(),
        "is_trained": True,
        "model_type": "Sequential",
        "model_version": "pure_fuzzy_v1",
        "architecture_type": "pure_fuzzy",
        "input_size": input_size,
        "pytorch_version": torch.__version__,
        "output_type": "regime_classification",
        "training_summary": {
            "epochs": 150,
            "final_accuracy": accuracy,
            "best_val_accuracy": best_val_acc,
            "labeler": "multi_scale_zigzag",
            "macro_atr_mult": labels_cfg.get("macro_atr_mult", 3.0),
            "micro_atr_mult": labels_cfg.get("micro_atr_mult", 1.0),
        },
        "feature_engineering": {
            "removed": True,
            "scaler_required": False,
            "fuzzy_only": True,
        },
    }
    with open(model_dir / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)

    # metadata_v3.json (v3 format for ModelMetadata.from_dict)
    metadata_v3 = {
        "model_name": "regime_classifier_seed",
        "strategy_name": "regime_classifier_seed",
        "strategy_version": "3.0",
        "created_at": datetime.datetime.now().isoformat(),
        "indicators": raw.get("indicators", {}),
        "fuzzy_sets": raw.get("fuzzy_sets", {}),
        "nn_inputs": raw.get("nn_inputs", []),
        "resolved_features": feature_names_list,
        "training_symbols": ["EURUSD"],
        "training_timeframes": ["1h"],
        "training_metrics": {"accuracy": accuracy, "best_val_accuracy": best_val_acc},
        "output_type": "regime_classification",
    }
    with open(model_dir / "metadata_v3.json", "w") as f:
        json.dump(metadata_v3, f, indent=2)
    with open(model_dir / "features.json", "w") as f:
        json.dump({"feature_names": feature_names_list}, f, indent=2)
    with open(model_dir / "config.json", "w") as f:
        json.dump({
            "input_size": input_size, "hidden_layers": hidden_layers,
            "dropout": dropout, "num_classes": 4, "activation": "relu",
        }, f, indent=2)
    with open(model_dir / "metrics.json", "w") as f:
        json.dump({"accuracy": accuracy}, f, indent=2)

    # Create 1h_latest symlink pointing to 1h_v1
    latest_link = model_base / "1h_latest"
    if not latest_link.exists():
        latest_link.symlink_to("1h_v1")

    print(f"\nModel saved to {model_dir}", flush=True)
    print("Done!", flush=True)


if __name__ == "__main__":
    asyncio.run(train())
