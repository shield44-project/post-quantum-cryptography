# Phase 6 results

Models: 216 attacked watermarked checkpoints (seeds [0, 1, 2]). A removal counts only if the verifier does not say VERIFIED and test accuracy stays within 5 points of the clean model.

## Per attack

| attack_id | family | runs | verified_rate | removal_success | mean_acc | mean_drop | mean_flip | mean_margin | mean_corrected |
|---|---|---|---|---|---|---|---|---|---|
| finetune_e10_lr0.001 | finetune | 3 | 1 | 0 | 0.8166 | 0.0032 | 0 | 2.23 | 0 |
| finetune_e10_lr0.01 | finetune | 3 | 1 | 0 | 0.7661 | 0.0537 | 0 | 2.17 | 0 |
| finetune_e10_lr0.05_full | finetune | 3 | 1 | 0 | 0.7642 | 0.0556 | 0 | 0.713 | 0 |
| finetune_e1_lr0.001 | finetune | 3 | 1 | 0 | 0.8173 | 0.0025 | 0 | 2.24 | 0 |
| finetune_e1_lr0.01 | finetune | 3 | 1 | 0 | 0.7843 | 0.0355 | 0 | 2.24 | 0 |
| finetune_e5_lr0.001 | finetune | 3 | 1 | 0 | 0.8182 | 0.0016 | 0 | 2.24 | 0 |
| finetune_e5_lr0.01 | finetune | 3 | 1 | 0 | 0.7915 | 0.0283 | 0 | 2.21 | 0 |
| half | quantize | 3 | 1 | 0 | 0.8197 | 0.0000 | 0 | 2.24 | 0 |
| noise_all_s0.01 | noise | 9 | 1 | 0 | 0.8199 | -0.0001 | 0 | 2.24 | 0 |
| noise_all_s0.05 | noise | 9 | 1 | 0 | 0.8160 | 0.0037 | 0 | 2.24 | 0 |
| noise_all_s0.1 | noise | 9 | 1 | 0 | 0.8006 | 0.0191 | 0 | 2.25 | 0 |
| noise_all_s0.2 | noise | 9 | 1 | 0 | 0.7584 | 0.0614 | 0 | 2.22 | 0 |
| noise_all_s0.5 | noise | 9 | 1 | 0 | 0.4437 | 0.3761 | 0 | 2.04 | 0 |
| noise_carrier_s0.1 | noise | 9 | 1 | 0 | 0.8180 | 0.0017 | 0 | 2.25 | 0 |
| noise_carrier_s0.5 | noise | 9 | 1 | 0 | 0.7435 | 0.0763 | 0 | 2 | 0 |
| noise_carrier_s1 | noise | 9 | 1 | 0 | 0.5592 | 0.2606 | 0 | 1.54 | 0 |
| none | control | 3 | 1 | 0 | 0.8198 | 0.0000 | 0 | 2.24 | 0 |
| overwrite_128bit | overwrite | 3 | 0 | 1 | 0.7828 | 0.0370 | 0.125 | 0.0133 | n/a |
| overwrite_512bit | overwrite | 3 | 0 | 0.333 | 0.7667 | 0.0531 | 0.23 | 0.00667 | n/a |
| permute_all | permute | 9 | 0 | 1 | 0.8198 | 0.0000 | 0.491 | 0.0167 | n/a |
| permute_in_carrier | permute | 9 | 0 | 1 | 0.8198 | 0.0000 | 0.498 | 0.00889 | n/a |
| permute_out_carrier | permute | 9 | 1 | 0 | 0.8198 | 0.0000 | 0 | 2.24 | 0 |
| prune_ft_0.5 | prune_ft | 3 | 1 | 0 | 0.7858 | 0.0340 | 0 | 1.99 | 0 |
| prune_ft_0.8 | prune_ft | 3 | 1 | 0 | 0.5047 | 0.3150 | 0.0234 | 0.00667 | 11.7 |
| prune_global_0.1 | prune_global | 3 | 1 | 0 | 0.8195 | 0.0003 | 0 | 2.24 | 0 |
| prune_global_0.3 | prune_global | 3 | 1 | 0 | 0.8098 | 0.0099 | 0 | 2.19 | 0 |
| prune_global_0.5 | prune_global | 3 | 1 | 0 | 0.6763 | 0.1435 | 0 | 2 | 0 |
| prune_global_0.7 | prune_global | 3 | 1 | 0 | 0.1648 | 0.6549 | 0.00195 | 0.197 | 1 |
| prune_global_0.9 | prune_global | 3 | 0 | 0 | 0.1008 | 0.7189 | 0.117 | 0.01 | n/a |
| prune_global_0.95 | prune_global | 3 | 0 | 0 | 0.1000 | 0.7198 | 0.225 | 0.00333 | n/a |
| prune_layer_0.3 | prune_layer | 3 | 1 | 0 | 0.8067 | 0.0130 | 0 | 0.993 | 0 |
| prune_layer_0.5 | prune_layer | 3 | 1 | 0 | 0.7400 | 0.0798 | 0.00195 | 0.14 | 1 |
| prune_layer_0.7 | prune_layer | 3 | 0 | 0 | 0.5126 | 0.3072 | 0.069 | 0.0133 | n/a |
| prune_layer_0.9 | prune_layer | 3 | 0 | 0 | 0.1412 | 0.6786 | 0.23 | 0.0167 | n/a |
| quant_pc_4 | quantize | 3 | 1 | 0 | 0.7639 | 0.0558 | 0 | 1.82 | 0 |
| quant_pc_8 | quantize | 3 | 1 | 0 | 0.8202 | -0.0004 | 0 | 2.24 | 0 |
| quant_pt_2 | quantize | 3 | 0 | 0 | 0.0953 | 0.7245 | 0.307 | 0.03 | n/a |
| quant_pt_3 | quantize | 3 | 1 | 0 | 0.2441 | 0.5757 | 0.0111 | 0.0433 | 5.33 |
| quant_pt_4 | quantize | 3 | 1 | 0 | 0.6757 | 0.1441 | 0 | 1.65 | 0 |
| quant_pt_6 | quantize | 3 | 1 | 0 | 0.8106 | 0.0092 | 0 | 2.23 | 0 |
| quant_pt_8 | quantize | 3 | 1 | 0 | 0.8192 | 0.0006 | 0 | 2.24 | 0 |
| rescale_all_x10 | rescale | 9 | 1 | 0 | 0.8200 | -0.0002 | 0 | 4.62 | 0 |
| rescale_carrier_x10 | rescale | 9 | 1 | 0 | 0.8197 | 0.0000 | 0 | 4.63 | 0 |
| rescale_carrier_x2 | rescale | 9 | 1 | 0 | 0.8198 | 0.0000 | 0 | 2.48 | 0 |

## Successful removals (watermark gone, model still useful)

| attack_id | family | runs | removal_success | mean_drop | mean_margin |
|---|---|---|---|---|---|
| overwrite_128bit | overwrite | 3 | 1 | 0.0370 | 0.0133 |
| overwrite_512bit | overwrite | 3 | 0.333 | 0.0531 | 0.00667 |
| permute_all | permute | 9 | 1 | 0.0000 | 0.0167 |
| permute_in_carrier | permute | 9 | 1 | 0.0000 | 0.00889 |

## Attacks that broke verification in at least one run

| attack_id | family | verified_rate | mean_drop | mean_flip | mean_margin | mean_corrected |
|---|---|---|---|---|---|---|
| overwrite_128bit | overwrite | 0 | 0.0370 | 0.125 | 0.0133 | n/a |
| overwrite_512bit | overwrite | 0 | 0.0531 | 0.23 | 0.00667 | n/a |
| permute_all | permute | 0 | 0.0000 | 0.491 | 0.0167 | n/a |
| permute_in_carrier | permute | 0 | 0.0000 | 0.498 | 0.00889 | n/a |
| prune_global_0.9 | prune_global | 0 | 0.7189 | 0.117 | 0.01 | n/a |
| prune_global_0.95 | prune_global | 0 | 0.7198 | 0.225 | 0.00333 | n/a |
| prune_layer_0.7 | prune_layer | 0 | 0.3072 | 0.069 | 0.0133 | n/a |
| prune_layer_0.9 | prune_layer | 0 | 0.6786 | 0.23 | 0.0167 | n/a |
| quant_pt_2 | quantize | 0 | 0.7245 | 0.307 | 0.03 | n/a |

## Sanity check: function-preserving attacks should not change accuracy

OK: permute and rescale attacks changed accuracy by less than 0.5 points.

## Control: attacks on the UNMARKED baseline models

False-accept rate (verifier says VERIFIED on a model that never had the watermark): **0.000** over 18 checkpoints.
