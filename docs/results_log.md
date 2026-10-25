# Results log

## Phase 1: Baseline (no watermark)
- Model: SmallCNN, width 32, ~160k parameters
- Hardware: Colab GPU (TESLA T4 GPU name)
- Training: 30 epochs, SGD (lr 0.05, momentum 0.9, nesterov), cosine schedule,
  weight decay 5e-4, batch 128, crop+flip augmentation
- Seeds: 0, 1, 2
- Test accuracy (final epoch): 0.8507 +/- 0.0119
- Seconds per run: 589
